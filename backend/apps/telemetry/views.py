from collections import OrderedDict
from datetime import datetime, timedelta
import math
import random

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from apps.alarms.models import Alarm
from apps.cloud.models import CloudDeviceStatus
from apps.common.device_gateway import resolve_device, resolve_or_register_device, valid_device_token
from apps.devices.models import Device, Sensor
from apps.telemetry.models import RawPoint


INTERVALS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}

MAX_HISTORY_RANGE = timedelta(days=31)
EXECUTOR_SENSOR_CODES = frozenset({"motor", "fan", "ventilation", "lamp", "led", "fill_light"})


class SensorHistoryView(APIView):
    def get(self, request, sensor_id):
        sensor = get_object_or_404(Sensor.objects.select_related("device"), pk=sensor_id)
        start = parse_required_datetime(request.query_params.get("start"), "start")
        end = parse_required_datetime(request.query_params.get("end"), "end")
        interval = request.query_params.get("interval", "5m")
        if interval not in INTERVALS:
            raise ValidationError({"interval": "interval must be one of 1m, 5m, 1h, 1d"})
        if start >= end:
            raise ValidationError({"end": "end must be later than start"})
        if end - start > MAX_HISTORY_RANGE:
            raise ValidationError({"end": f"history range must be within {MAX_HISTORY_RANGE.days} days"})

        rows = (
            RawPoint.objects.filter(sensor=sensor, ts__gte=start, ts__lte=end)
            .order_by("ts")
            .values_list("ts", "value")
        )
        buckets = bucket_points(rows, start, INTERVALS[interval])
        return Response({
            "metric": sensor.name,
            "sensor_id": sensor.id,
            "device_id": sensor.device_id,
            "interval": interval,
            "points": [
                {"ts": bucket.isoformat(), "value": round(sum(values) / len(values), 3)}
                for bucket, values in buckets.items()
                if values
            ],
        })


class SimulateRealtimeView(APIView):
    def post(self, request):
        from django.conf import settings as _settings
        if not _settings.DEBUG:
            return Response({"detail": "模拟接口仅在开发环境可用"}, status=403)
        sensor_id = request.data.get("sensor_id")
        sensor = get_object_or_404(Sensor.objects.select_related("device"), pk=sensor_id)
        previous = sensor.latest_value if sensor.latest_value is not None else 1
        value = round(previous + random.uniform(-0.8, 0.8), 3)
        ts = timezone.now()

        payload = persist_and_publish(sensor, value, ts)
        return Response(payload)


class TelemetryIngestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "telemetry_ingest"

    def post(self, request):
        if not isinstance(request.data, dict):
            raise ValidationError({"detail": "JSON object body required"})
        if not valid_device_token(request, request.data):
            return Response({"detail": "invalid device ingest token"}, status=status.HTTP_401_UNAUTHORIZED)

        points = parse_ingest_points(request.data)
        # Validate each point has required fields; skip invalid ones instead of crashing
        valid_points = []
        for item in points:
            if not isinstance(item, dict):
                continue
            if "sensor_code" not in item or "value" not in item:
                continue
            if item.get("ts") is None:
                continue
            valid_points.append(item)
        points = valid_points
        if not points:
            raise ValidationError({"metrics": "at least one valid sensor data point is required (each needs sensor_code, value)"})
        if len(points) > 64:
            raise ValidationError({"metrics": "at most 64 sensor data points are allowed per request"})
        for item in points:
            if len(item["sensor_code"]) > 32:
                raise ValidationError({"sensor_code": "sensor_code must be at most 32 characters"})
        # token必须与payload解析出的目标设备绑定，防止用B设备token向A设备写入遥测
        try:
            bound_device = resolve_device(request.data)
        except ValidationError:
            bound_device = None
        if bound_device is not None and not valid_device_token(request, device=bound_device):
            return Response({"detail": "invalid device ingest token"}, status=status.HTTP_401_UNAUTHORIZED)
        device = resolve_or_register_device(request.data, [item["sensor_code"] for item in points])
        points = append_ia1_control_points(device, points)

        published = []
        # Batch: pre-fetch all sensors in one query
        codes = [item["sensor_code"] for item in points]
        sensor_map = {
            s.code: s
            for s in Sensor.objects.select_related("device").filter(device=device, code__in=codes)
        }
        raw_points = []
        update_sensors = []
        for item in points:
            sensor = sensor_map.get(item["sensor_code"])
            if sensor is None:
                raise ValidationError({"sensor_code": f"sensor {item['sensor_code']} does not exist on {device.sn}"})
            item_ts = item["ts"]
            raw_points.append(RawPoint(device=device, sensor=sensor, ts=item_ts, value=item["value"]))
            if sensor.latest_ts is None or item_ts >= sensor.latest_ts:
                sensor.latest_ts = item_ts
                sensor.latest_value = item["value"]
            update_sensors.append(sensor)

        with transaction.atomic():
            RawPoint.objects.bulk_create(raw_points)
            Sensor.objects.bulk_update(update_sensors, ["latest_ts", "latest_value"])
            new_alarms = []
            for item in points:
                sensor = sensor_map[item["sensor_code"]]
                item_ts = item["ts"]
                alarm = record_threshold_alarm(sensor, item["value"], item_ts)
                if alarm is not None:
                    new_alarms.append(alarm)
                payload = {
                    "deviceId": device.id, "sensorId": sensor.id, "code": sensor.code,
                    "name": sensor.name, "unit": sensor.unit,
                    "value": item["value"], "ts": item_ts.isoformat(), "status": device.status,
                }
                published.append(payload)

            has_open_alarm = Alarm.objects.filter(device=device, status=Alarm.Status.NEW).exists()
            if device.status != Device.Status.MAINTENANCE:
                device.status = Device.Status.WARNING if has_open_alarm else Device.Status.ONLINE
                if has_open_alarm:
                    first_alarm = Alarm.objects.filter(device=device, status=Alarm.Status.NEW).order_by("ts").first()
                    device.abnormal_reason = first_alarm.message if first_alarm else ""
                else:
                    device.abnormal_reason = ""
            latest_ts = max(item["ts"] for item in points)
            device.last_seen = timezone.now()
            device.save(update_fields=["status", "last_seen", "abnormal_reason"])
            for payload in published:
                payload["status"] = device.status

            cloud = getattr(device, "cloud", None)
            if cloud:
                cloud.mqtt_status = CloudDeviceStatus.MqttStatus.CONNECTED
                cloud.sync_status = CloudDeviceStatus.SyncStatus.SYNCED
                cloud.last_sync = latest_ts
                cloud.shadow_version += 1
                cloud.save(update_fields=["mqtt_status", "sync_status", "last_sync", "shadow_version"])

        # Publish WebSocket after transaction
        channel_layer = get_channel_layer()
        if channel_layer:
            group_name = getattr(settings, "REALTIME_GROUP_NAME", "realtime")
            for payload in published:
                async_to_sync(channel_layer.group_send)(group_name, {"type": "sensor.point", "payload": payload})
            for alarm in new_alarms:
                alarm_payload = {
                    "id": alarm.id,
                    "deviceId": device.id,
                    "sensorId": alarm.sensor_id,
                    "deviceName": device.sn,
                    "level": alarm.level,
                    "status": alarm.status,
                    "message": alarm.message,
                    "ts": alarm.ts.isoformat(),
                }
                async_to_sync(channel_layer.group_send)(
                    group_name, {"type": "alarm.event", "payload": alarm_payload}
                )

        return Response({"accepted": len(published), "points": published}, status=status.HTTP_201_CREATED)

def parse_ingest_points(data):
    ts = parse_optional_datetime(data.get("ts") or data.get("event_time"))

    if "sensor_code" in data and "value" in data:
        return [{
            "sensor_code": str(data["sensor_code"]),
            "value": parse_numeric(data["value"], "value"),
            "ts": ts,
        }]

    metrics = data.get("metrics")
    if isinstance(metrics, dict):
        return [
            {"sensor_code": str(code), "value": parse_numeric(value, str(code)), "ts": ts}
            for code, value in metrics.items()
        ]

    points = []
    services = data.get("services")
    if isinstance(services, list):
        for service in services:
            if not isinstance(service, dict):
                continue
            service_ts = parse_optional_datetime(service.get("event_time") or data.get("event_time"))
            properties = service.get("properties")
            if isinstance(properties, dict):
                points.extend(
                    {"sensor_code": str(code), "value": parse_numeric(value, str(code)), "ts": service_ts}
                    for code, value in properties.items()
                )
    return points


def append_ia1_control_points(device, points):
    if not points or any(item["sensor_code"] == "motor" for item in points):
        return points

    motor_sensor = Sensor.objects.filter(device=device, code="motor").first()
    if motor_sensor is None:
        return points

    values = {item["sensor_code"]: item["value"] for item in points}
    temp = values.get("temp")
    hum = values.get("hum")
    if temp is None and hum is None:
        return points

    thresholds = {
        sensor.code: sensor
        for sensor in Sensor.objects.filter(device=device, code__in=["temp", "hum"])
    }
    temp_sensor = thresholds.get("temp")
    hum_sensor = thresholds.get("hum")
    temp_max = temp_sensor.max_value if temp_sensor else None
    hum_max = hum_sensor.max_value if hum_sensor else None
    motor_on = (
        (temp is not None and temp_max is not None and temp > temp_max)
        or (hum is not None and hum_max is not None and hum > hum_max)
    )
    ts = points[0]["ts"]
    return [*points, {"sensor_code": "motor", "value": 1.0 if motor_on else 0.0, "ts": ts}]


def parse_optional_datetime(value):
    if not value:
        return timezone.now()
    try:
        parsed = parse_datetime(str(value))
    except ValueError:
        # 形如2026-02-30T00:00:00的"格式合法但日期非法"输入会抛ValueError
        raise ValidationError({"ts": "ISO8601 datetime is required"})
    if parsed is None:
        raise ValidationError({"ts": "ISO8601 datetime is required"})
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    now = timezone.now()
    if parsed > now + timedelta(hours=24):
        raise ValidationError({"ts": "timestamp is more than 24 hours in the future"})
    if parsed < now - timedelta(hours=24):
        raise ValidationError({"ts": "timestamp is more than 24 hours in the past"})
    return parsed


def parse_numeric(value, field):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValidationError({field: "numeric value is required"})
    if not math.isfinite(result):
        raise ValidationError({field: "numeric value is required"})
    return result


def persist_and_publish(sensor, value, ts):
    device = sensor.device

    with transaction.atomic():
        RawPoint.objects.create(device=device, sensor=sensor, ts=ts, value=value)
        sensor.latest_ts = ts
        sensor.latest_value = value
        sensor.save(update_fields=["latest_ts", "latest_value"])

        alarm = record_threshold_alarm(sensor, value, ts)
        if alarm:
            has_open_alarm = True
            abnormal_reason = alarm.message
        else:
            open_alarm = Alarm.objects.filter(device=device, status=Alarm.Status.NEW).first()
            has_open_alarm = open_alarm is not None
            abnormal_reason = open_alarm.message if open_alarm else ""
        if device.status != Device.Status.MAINTENANCE:
            device.status = Device.Status.WARNING if has_open_alarm else Device.Status.ONLINE
            device.abnormal_reason = abnormal_reason
        device.last_seen = ts
        device.save(update_fields=["status", "last_seen", "abnormal_reason"])

    payload = {
        "deviceId": device.id,
        "sensorId": sensor.id,
        "code": sensor.code,
        "name": sensor.name,
        "unit": sensor.unit,
        "value": value,
        "ts": ts.isoformat(),
        "status": device.status,
    }
    channel_layer = get_channel_layer()
    if channel_layer:
        from django.conf import settings as _settings
        group_name = getattr(_settings, "REALTIME_GROUP_NAME", "realtime")
        async_to_sync(channel_layer.group_send)(group_name, {"type": "sensor.point", "payload": payload})
        if alarm is not None:
            alarm_payload = {
                "id": alarm.id,
                "deviceId": device.id,
                "sensorId": sensor.id,
                "deviceName": device.sn,
                "level": alarm.level,
                "status": alarm.status,
                "message": alarm.message,
                "ts": alarm.ts.isoformat(),
            }
            async_to_sync(channel_layer.group_send)(
                group_name, {"type": "alarm.event", "payload": alarm_payload}
            )
    return payload


def record_threshold_alarm(sensor, value, ts):
    # 执行器类传感器只反映状态，不参与阈值告警
    if sensor.code in EXECUTOR_SENSOR_CODES:
        return None
    min_value = sensor.min_value
    max_value = sensor.max_value
    if min_value is not None and value < min_value:
        return upsert_alarm(sensor, ts, Alarm.Level.WARNING, f"{sensor.name}低于阈值：{value}{sensor.unit} < {min_value}{sensor.unit}")
    if max_value is not None and value > max_value:
        return upsert_alarm(sensor, ts, Alarm.Level.WARNING, f"{sensor.name}高于阈值：{value}{sensor.unit} > {max_value}{sensor.unit}")
    close_resolved_alarms(sensor)
    return None


def close_resolved_alarms(sensor):
    """自动关闭已恢复的NEW/ACKNOWLEDGED告警，数值回归正常后无需人工显式关闭。"""
    Alarm.objects.filter(
        device=sensor.device,
        sensor=sensor,
        status__in=[Alarm.Status.NEW, Alarm.Status.ACKNOWLEDGED],
    ).select_for_update().update(status=Alarm.Status.CLOSED)


def upsert_alarm(sensor, ts, level, message):
    alarm = Alarm.objects.filter(
        device=sensor.device,
        sensor=sensor,
        status=Alarm.Status.NEW,
    ).select_for_update().first()
    if alarm:
        alarm.ts = ts
        alarm.level = level
        alarm.message = message
        alarm.save(update_fields=["ts", "level", "message"])
        return alarm
    return Alarm.objects.create(
        device=sensor.device,
        sensor=sensor,
        ts=ts,
        level=level,
        message=message,
        status=Alarm.Status.NEW,
    )


def parse_required_datetime(value, field):
    try:
        parsed = parse_datetime(value or "")
    except ValueError:
        # 形如2026-02-30T00:00:00的"格式合法但日期非法"输入会抛ValueError
        raise ValidationError({field: "ISO8601 datetime is required"})
    if parsed is None:
        raise ValidationError({field: "ISO8601 datetime is required"})
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def bucket_points(rows, start: datetime, step: timedelta):
    buckets = OrderedDict()
    step_seconds = int(step.total_seconds())
    for ts, value in rows:
        offset = max(0, int((ts - start).total_seconds()))
        bucket_start = start + timedelta(seconds=(offset // step_seconds) * step_seconds)
        buckets.setdefault(bucket_start, []).append(value)
    return buckets
