from datetime import timedelta
import uuid

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.device_gateway import resolve_device, valid_device_token
from apps.audit.models import AuditLog
from apps.audit.services import record_audit
from apps.devices.models import Device, DeviceCommand, Sensor
from apps.devices.permissions import CanSendDeviceCommand
from apps.devices.serializers import (
    DeviceCommandAckSerializer,
    DeviceBulkCommandSerializer,
    DeviceCommandCreateSerializer,
    DeviceCommandPullSerializer,
    DeviceCommandSerializer,
    DeviceSerializer,
    RuleSerializer,
)


BULK_COMMAND_CONTROLLABLE_STATUSES = [Device.Status.ONLINE, Device.Status.WARNING]


def filter_bulk_command_devices(target, device_ids=None):
    cutoff = timezone.now() - timedelta(seconds=settings.DEVICE_ACTIVE_TTL_SECONDS)
    queryset = Device.objects.all()
    if target == "online":
        return queryset.filter(
            status__in=BULK_COMMAND_CONTROLLABLE_STATUSES,
            last_seen__gte=cutoff,
        )
    if target == "all":
        return queryset.exclude(status=Device.Status.OFFLINE).filter(last_seen__gte=cutoff)
    if target == "selected":
        return queryset.filter(
            id__in=device_ids or [],
            status__in=BULK_COMMAND_CONTROLLABLE_STATUSES,
            last_seen__gte=cutoff,
        )
    return queryset.none()


class DeviceListView(ListAPIView):
    serializer_class = DeviceSerializer

    def get_queryset(self):
        queryset = Device.objects.prefetch_related("sensors")
        include_inactive = self.request.query_params.get("include_inactive") == "true"
        if not include_inactive:
            cutoff = timezone.now() - timedelta(seconds=settings.DEVICE_ACTIVE_TTL_SECONDS)
            queryset = queryset.filter(last_seen__gte=cutoff)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        devices = list(queryset)
        return Response({
            "count": len(devices),
            "results": self.get_serializer(devices, many=True).data,
        })


class DeviceDetailView(RetrieveAPIView):
    serializer_class = DeviceSerializer
    queryset = Device.objects.prefetch_related("sensors")


class DeviceCommandView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [CanSendDeviceCommand()]
        return super().get_permissions()

    def get(self, request, device_id):
        device = get_object_or_404(Device, pk=device_id)
        commands = DeviceCommand.objects.filter(device=device)
        return Response(DeviceCommandSerializer(commands, many=True).data)

    def post(self, request, device_id):
        device = get_object_or_404(Device, pk=device_id)
        serializer = DeviceCommandCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        command_type = serializer.validated_data["type"]
        labels = {
            DeviceCommand.Command.REBOOT: "重启",
            DeviceCommand.Command.UPGRADE: "固件升级",
            DeviceCommand.Command.SET_PARAM: "参数设置",
        }
        message = f"{labels[command_type]}指令已进入队列，等待设备 ACK"
        params = serializer.validated_data.get("params", {})
        if command_type == DeviceCommand.Command.SET_PARAM and any(
            key in params for key in ("motor_override", "light_override")
        ):
            message = "远程执行器控制指令已进入队列，等待设备 ACK"
        command = DeviceCommand.objects.create(
            device=device,
            command=command_type,
            params=params,
            message=message,
        )
        record_audit(
            request,
            AuditLog.Action.COMMAND_CREATE,
            device.sn,
            f"下发{labels[command_type]}指令",
            {"deviceId": command.device_id, "commandId": command.id, "params": params},
        )
        return Response(DeviceCommandSerializer(command).data, status=201)


def bulk_command_labels(actuator, mode):
    actuator_label = "电机" if actuator == "motor" else "补光灯"
    mode_label = {"auto": "自动", "on": "强制开", "off": "强制关"}[mode]
    return actuator_label, mode_label


def create_bulk_commands(devices, actuator, mode, sync_delay_ms, retry_of=None):
    param_key = "motor_override" if actuator == "motor" else "light_override"
    actuator_label, mode_label = bulk_command_labels(actuator, mode)
    execute_at = timezone.now() + timedelta(milliseconds=sync_delay_ms)
    batch_id = f"bulk-{execute_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    command_params = {
        param_key: mode,
        "batch_id": batch_id,
        "execute_at": execute_at.isoformat(),
        "sync_delay_ms": sync_delay_ms,
        "sync": True,
    }
    if retry_of:
        command_params["retry_of"] = retry_of
    commands = [
        DeviceCommand.objects.create(
            device=device,
            command=DeviceCommand.Command.SET_PARAM,
            params=command_params,
            message=f"批量{actuator_label}{mode_label}同步指令已进入队列，预计{execute_at.isoformat()}同时执行",
        )
        for device in devices
    ]
    return batch_id, execute_at, commands


def command_batch_id(command):
    params = command.params if isinstance(command.params, dict) else {}
    batch_id = params.get("batch_id")
    return str(batch_id) if batch_id else ""


def infer_actuator_and_mode(params):
    if params.get("motor_override") in ("auto", "on", "off"):
        return "motor", params["motor_override"]
    if params.get("light_override") in ("auto", "on", "off"):
        return "light", params["light_override"]
    return "unknown", "unknown"


def serialize_bulk_task(batch_id, commands):
    commands = sorted(commands, key=lambda command: (command.device.slot_no, command.id))
    first = min(commands, key=lambda command: command.created_at)
    latest = max(commands, key=lambda command: command.ack_at or command.created_at)
    params = first.params if isinstance(first.params, dict) else {}
    actuator, mode = infer_actuator_and_mode(params)
    actuator_label = "电机" if actuator == "motor" else "补光灯" if actuator == "light" else "执行器"
    mode_label = {"auto": "自动模式", "on": "打开", "off": "关闭"}.get(mode, mode)

    counts = {
        DeviceCommand.Status.QUEUED: 0,
        DeviceCommand.Status.SENT: 0,
        DeviceCommand.Status.ACKED: 0,
        DeviceCommand.Status.FAILED: 0,
    }
    for command in commands:
        counts[command.status] = counts.get(command.status, 0) + 1

    total = len(commands)
    finished = counts[DeviceCommand.Status.ACKED] + counts[DeviceCommand.Status.FAILED]
    if counts[DeviceCommand.Status.FAILED]:
        task_status = "failed" if finished == total else "partial"
    elif counts[DeviceCommand.Status.ACKED] == total:
        task_status = "completed"
    elif counts[DeviceCommand.Status.SENT]:
        task_status = "running"
    else:
        task_status = "queued"

    command_rows = [
        {
            "id": command.id,
            "deviceId": command.device_id,
            "slotNo": command.device.slot_no,
            "sn": command.device.sn,
            "status": command.status,
            "message": command.message,
            "createdAt": command.created_at.isoformat(),
            "ackAt": command.ack_at.isoformat() if command.ack_at else None,
        }
        for command in commands
    ]
    failed_devices = [row for row in command_rows if row["status"] == DeviceCommand.Status.FAILED]
    logs = []
    for command in commands:
        logs.append({
            "ts": command.created_at.isoformat(),
            "level": "info",
            "message": f"槽位{command.device.slot_no}{command.device.sn}指令已入队",
            "deviceId": command.device_id,
            "slotNo": command.device.slot_no,
            "sn": command.device.sn,
            "commandId": command.id,
            "status": DeviceCommand.Status.QUEUED,
        })
        if command.status in (DeviceCommand.Status.SENT, DeviceCommand.Status.ACKED, DeviceCommand.Status.FAILED):
            logs.append({
                "ts": command.created_at.isoformat(),
                "level": "info",
                "message": f"槽位{command.device.slot_no}{command.device.sn}已被设备拉取",
                "deviceId": command.device_id,
                "slotNo": command.device.slot_no,
                "sn": command.device.sn,
                "commandId": command.id,
                "status": DeviceCommand.Status.SENT,
            })
        if command.status in (DeviceCommand.Status.ACKED, DeviceCommand.Status.FAILED) and command.ack_at:
            logs.append({
                "ts": command.ack_at.isoformat(),
                "level": "error" if command.status == DeviceCommand.Status.FAILED else "success",
                "message": f"槽位{command.device.slot_no}{command.device.sn}{'执行失败' if command.status == DeviceCommand.Status.FAILED else '执行成功'}：{command.message}",
                "deviceId": command.device_id,
                "slotNo": command.device.slot_no,
                "sn": command.device.sn,
                "commandId": command.id,
                "status": command.status,
            })

    return {
        "batchId": batch_id,
        "title": f"{actuator_label}{mode_label}",
        "actuator": actuator,
        "mode": mode,
        "status": task_status,
        "total": total,
        "queued": counts[DeviceCommand.Status.QUEUED],
        "sent": counts[DeviceCommand.Status.SENT],
        "acked": counts[DeviceCommand.Status.ACKED],
        "failed": counts[DeviceCommand.Status.FAILED],
        "pending": total - finished,
        "progress": round((finished / total) * 100, 1) if total else 0,
        "executeAt": params.get("execute_at"),
        "syncDelayMs": params.get("sync_delay_ms"),
        "retryOf": params.get("retry_of"),
        "createdAt": first.created_at.isoformat(),
        "latestAt": (latest.ack_at or latest.created_at).isoformat(),
        "commands": command_rows,
        "failedDevices": failed_devices,
        "logs": sorted(logs, key=lambda item: item["ts"], reverse=True),
    }


def load_bulk_task_commands(batch_id=None, limit=200):
    base_queryset = DeviceCommand.objects.filter(
        command=DeviceCommand.Command.SET_PARAM,
    )
    if batch_id:
        batch_ids = [batch_id]
    else:
        recent_commands = (
            base_queryset.exclude(params__batch_id__isnull=True)
            .exclude(params__batch_id="")
            .order_by("-created_at")
            .values_list("params__batch_id", "created_at")[: limit * 200]
        )
        seen = []
        seen_set = set()
        for current_batch_id, _ in recent_commands:
            if not current_batch_id or current_batch_id in seen_set:
                continue
            seen.append(current_batch_id)
            seen_set.add(current_batch_id)
            if len(seen) >= limit:
                break
        batch_ids = seen

    if not batch_ids:
        return {}

    commands = list(
        base_queryset.select_related("device").filter(params__batch_id__in=batch_ids)
    )
    groups = {}
    for command in commands:
        current_batch_id = command_batch_id(command)
        if not current_batch_id:
            continue
        groups.setdefault(current_batch_id, []).append(command)
    return groups


class DeviceBulkCommandView(APIView):
    permission_classes = [CanSendDeviceCommand]

    def post(self, request):
        serializer = DeviceBulkCommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["target"]
        actuator = serializer.validated_data["actuator"]
        mode = serializer.validated_data["mode"]
        requested_sync_delay_ms = serializer.validated_data.get("sync_delay_ms")

        devices = list(
            filter_bulk_command_devices(
                target,
                serializer.validated_data.get("device_ids"),
            ).order_by("slot_no")
        )
        if not devices:
            raise ValidationError({"device_ids": "没有可下发的设备"})

        if requested_sync_delay_ms is None:
            sync_delay_ms = min(
                settings.DEVICE_BULK_SYNC_MAX_DELAY_MS,
                settings.DEVICE_BULK_SYNC_DELAY_MS + len(devices) * settings.DEVICE_BULK_SYNC_PER_DEVICE_MS,
            )
        else:
            sync_delay_ms = requested_sync_delay_ms

        batch_id, execute_at, commands = create_bulk_commands(devices, actuator, mode, sync_delay_ms)
        actuator_label, mode_label = bulk_command_labels(actuator, mode)
        record_audit(
            request,
            AuditLog.Action.COMMAND_CREATE,
            f"{len(devices)} 台设备",
            f"批量下发{actuator_label}{mode_label}",
            {
                "target": target,
                "actuator": actuator,
                "mode": mode,
                "batchId": batch_id,
                "executeAt": execute_at.isoformat(),
                "syncDelayMs": sync_delay_ms,
                "deviceIds": [device.id for device in devices],
            },
        )
        return Response(
            {
                "count": len(commands),
                "batchId": batch_id,
                "executeAt": execute_at.isoformat(),
                "serverTime": timezone.now().isoformat(),
                "commands": DeviceCommandSerializer(commands, many=True).data,
                "task": serialize_bulk_task(batch_id, commands),
            },
            status=201,
        )


class DeviceBulkTaskListView(APIView):
    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 100))
        except (TypeError, ValueError):
            limit = 100
        limit = max(1, min(limit, 500))
        groups = load_bulk_task_commands(limit=limit)
        tasks = [
            serialize_bulk_task(batch_id, commands)
            for batch_id, commands in groups.items()
        ]
        tasks.sort(key=lambda item: item["createdAt"], reverse=True)
        return Response({"count": len(tasks), "results": tasks})


class DeviceBulkTaskRetryView(APIView):
    permission_classes = [CanSendDeviceCommand]

    def post(self, request, batch_id):
        groups = load_bulk_task_commands(batch_id=batch_id)
        commands = groups.get(batch_id)
        if not commands:
            raise ValidationError({"batch_id": "批量任务不存在"})

        failed_commands = [command for command in commands if command.status == DeviceCommand.Status.FAILED]
        if not failed_commands:
            raise ValidationError({"batch_id": "没有失败板卡可重试"})

        first_params = failed_commands[0].params if isinstance(failed_commands[0].params, dict) else {}
        actuator, mode = infer_actuator_and_mode(first_params)
        if actuator not in ("motor", "light") or mode not in ("auto", "on", "off"):
            raise ValidationError({"batch_id": "无法识别原任务执行器参数"})

        requested_sync_delay_ms = request.data.get("sync_delay_ms")
        if requested_sync_delay_ms is None:
            sync_delay_ms = min(
                settings.DEVICE_BULK_SYNC_MAX_DELAY_MS,
                settings.DEVICE_BULK_SYNC_DELAY_MS + len(failed_commands) * settings.DEVICE_BULK_SYNC_PER_DEVICE_MS,
            )
        else:
            try:
                sync_delay_ms = int(requested_sync_delay_ms)
            except (TypeError, ValueError):
                raise ValidationError({"sync_delay_ms": "sync_delay_ms must be an integer"})
            if sync_delay_ms < 500 or sync_delay_ms > 30000:
                raise ValidationError({"sync_delay_ms": "sync_delay_ms must be between 500 and 30000"})

        devices = [command.device for command in failed_commands]
        retry_batch_id, execute_at, retry_commands = create_bulk_commands(
            devices,
            actuator,
            mode,
            sync_delay_ms,
            retry_of=batch_id,
        )
        actuator_label, mode_label = bulk_command_labels(actuator, mode)
        record_audit(
            request,
            AuditLog.Action.COMMAND_CREATE,
            f"{len(devices)} 台失败设备",
            f"重试批量{actuator_label}{mode_label}",
            {
                "retryOf": batch_id,
                "batchId": retry_batch_id,
                "executeAt": execute_at.isoformat(),
                "deviceIds": [device.id for device in devices],
            },
        )
        return Response(
            {
                "count": len(retry_commands),
                "batchId": retry_batch_id,
                "executeAt": execute_at.isoformat(),
                "serverTime": timezone.now().isoformat(),
                "commands": DeviceCommandSerializer(retry_commands, many=True).data,
                "task": serialize_bulk_task(retry_batch_id, retry_commands),
            },
            status=201,
        )


class DeviceCommandPullView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not valid_device_token(request, request.data):
            return Response({"detail": "invalid device ingest token"}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = DeviceCommandPullSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = resolve_device(serializer.validated_data)
        limit = serializer.validated_data["limit"]

        with transaction.atomic():
            commands = list(
                DeviceCommand.objects.select_for_update(skip_locked=True)
                .filter(device=device, status=DeviceCommand.Status.QUEUED)
                .order_by("created_at")[:limit]
            )
            if commands:
                command_ids = [command.id for command in commands]
                DeviceCommand.objects.filter(
                    id__in=command_ids,
                    status=DeviceCommand.Status.QUEUED,
                ).update(status=DeviceCommand.Status.SENT)
                for command in commands:
                    command.status = DeviceCommand.Status.SENT

        return Response({
            "deviceId": device.id,
            "sn": device.sn,
            "count": len(commands),
            "serverTime": timezone.now().isoformat(),
            "commands": DeviceCommandSerializer(commands, many=True).data,
        })


class DeviceCommandAckView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not valid_device_token(request, request.data):
            return Response({"detail": "invalid device ingest token"}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = DeviceCommandAckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = resolve_device(serializer.validated_data)
        command = DeviceCommand.objects.filter(
            id=serializer.validated_data["command_id"],
            device=device,
        ).first()
        if command is None:
            raise ValidationError({"command_id": "command not found on this device"})

        if command.status in [DeviceCommand.Status.ACKED, DeviceCommand.Status.FAILED]:
            return Response(DeviceCommandSerializer(command).data)

        command.status = serializer.validated_data["status"]
        command.ack_at = serializer.validated_data.get("ack_at", timezone.now())

        update_fields = ["status", "ack_at"]
        message = serializer.validated_data.get("message")
        if message is not None:
            command.message = message
            update_fields.append("message")
        elif command.status == DeviceCommand.Status.ACKED:
            command.message = "设备已确认执行"
            update_fields.append("message")
        elif command.status == DeviceCommand.Status.FAILED and command.message.endswith("等待设备 ACK"):
            command.message = "设备执行失败"
            update_fields.append("message")

        command.save(update_fields=update_fields)
        record_audit(
            request,
            AuditLog.Action.COMMAND_ACK,
            device.sn,
            f"设备回执指令：{command.status}",
            {"deviceId": device.id, "commandId": command.id, "status": command.status},
        )
        return Response(DeviceCommandSerializer(command).data)


RULE_ALLOWED_SENSOR_CODES = frozenset({"temp", "hum", "light", "voltage", "current", "power"})


class RuleListView(ListAPIView):
    serializer_class = RuleSerializer

    def get_queryset(self):
        queryset = Sensor.objects.select_related("device").filter(code__in=RULE_ALLOWED_SENSOR_CODES)
        include_inactive = self.request.query_params.get("include_inactive") == "true"
        if not include_inactive:
            cutoff = timezone.now() - timedelta(seconds=settings.DEVICE_ACTIVE_TTL_SECONDS)
            queryset = queryset.filter(device__last_seen__gte=cutoff)
        device_id = self.request.query_params.get("device_id")
        if device_id:
            queryset = queryset.filter(device_id=device_id)
        return queryset


class RuleDetailView(APIView):
    permission_classes = [CanSendDeviceCommand]

    def put(self, request, sensor_id):
        return self.patch(request, sensor_id)

    def patch(self, request, sensor_id):
        sensor = get_object_or_404(Sensor.objects.select_related("device"), pk=sensor_id)
        if sensor.code not in RULE_ALLOWED_SENSOR_CODES:
            raise ValidationError({"sensor": "该传感器不支持配置阈值规则"})
        before = {"min": sensor.min_value, "max": sensor.max_value}
        serializer = RuleSerializer(sensor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        sensor.refresh_from_db()
        record_audit(
            request,
            AuditLog.Action.RULE_UPDATE,
            f"{sensor.device.sn}/{sensor.code}",
            "更新传感器阈值规则",
            {"before": before, "after": {"min": sensor.min_value, "max": sensor.max_value}},
        )
        return Response(RuleSerializer(sensor).data)
