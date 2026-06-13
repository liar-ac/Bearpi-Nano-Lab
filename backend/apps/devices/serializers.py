from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework import serializers

from apps.devices.models import Device, DeviceCommand, Sensor


class SensorSerializer(serializers.ModelSerializer):
    deviceId = serializers.IntegerField(source="device_id", read_only=True)
    min = serializers.FloatField(source="min_value", read_only=True)
    max = serializers.FloatField(source="max_value", read_only=True)
    latest = serializers.SerializerMethodField()

    class Meta:
        model = Sensor
        fields = ["id", "deviceId", "code", "name", "unit", "description", "min", "max", "latest"]

    def get_latest(self, obj):
        if obj.latest_ts is None or obj.latest_value is None:
            return None
        return {"ts": obj.latest_ts.isoformat(), "value": obj.latest_value}


class DeviceSerializer(serializers.ModelSerializer):
    slotNo = serializers.IntegerField(source="slot_no")
    labId = serializers.CharField(source="lab_id")
    firmwareVersion = serializers.CharField(source="firmware_version")
    lastSeen = serializers.DateTimeField(source="last_seen", allow_null=True)
    registerTime = serializers.DateTimeField(source="register_time")
    ipAddress = serializers.IPAddressField(source="ip_address", allow_null=True)
    sampleRate = serializers.IntegerField(source="sample_rate")
    abnormalReason = serializers.CharField(source="abnormal_reason")
    sensors = SensorSerializer(many=True, read_only=True)
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        """动态计算设备在线状态：基于last_seen和TTL"""
        if obj.status == Device.Status.MAINTENANCE:
            return obj.status
        if obj.last_seen is None:
            return Device.Status.OFFLINE
        cutoff = timezone.now() - timedelta(seconds=settings.DEVICE_ACTIVE_TTL_SECONDS)
        if obj.last_seen < cutoff:
            return Device.Status.OFFLINE
        return obj.status

    class Meta:
        model = Device
        fields = [
            "id",
            "slotNo",
            "sn",
            "labId",
            "model",
            "firmwareVersion",
            "location",
            "owner",
            "member",
            "status",
            "lastSeen",
            "registerTime",
            "ipAddress",
            "sampleRate",
            "abnormalReason",
            "sensors",
        ]


class DeviceCommandSerializer(serializers.ModelSerializer):
    deviceId = serializers.IntegerField(source="device_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    ackAt = serializers.DateTimeField(source="ack_at", read_only=True, allow_null=True)

    class Meta:
        model = DeviceCommand
        fields = ["id", "deviceId", "command", "params", "status", "message", "createdAt", "ackAt"]


ALLOWED_COMMAND_PARAM_KEYS = frozenset(
    {
        "motor_override",
        "light_override",
        "firmware_url",
        "firmware_version",
        "sample_rate",
        "execute_at",
        "sync_delay_ms",
        "sync",
        "batch_id",
        "retry_of",
    }
)


class DeviceCommandCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=DeviceCommand.Command.choices)
    params = serializers.DictField(required=False)

    def validate(self, attrs):
        command_type = attrs.get("type")
        params = attrs.get("params", {})
        if command_type == "set_param" and not params:
            raise serializers.ValidationError({"params": "set_param 指令必须包含参数"})
        return attrs

    def validate_params(self, value):
        unknown = set(value.keys()) - ALLOWED_COMMAND_PARAM_KEYS
        if unknown:
            raise serializers.ValidationError(
                f"unsupported params: {', '.join(sorted(unknown))}"
            )
        for key in ("motor_override", "light_override"):
            if key in value and value[key] not in ("auto", "on", "off"):
                raise serializers.ValidationError(f"{key} must be one of auto/on/off")
        if "sample_rate" in value:
            try:
                rate = int(value["sample_rate"])
            except (TypeError, ValueError):
                raise serializers.ValidationError({"sample_rate": "sample_rate must be a positive integer"})
            if rate <= 0 or rate > 3600:
                raise serializers.ValidationError({"sample_rate": "sample_rate must be between 1 and 3600"})
        return value


class DeviceBulkCommandSerializer(serializers.Serializer):
    device_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=False,
    )
    target = serializers.ChoiceField(choices=["all", "online", "selected"], default="online")
    actuator = serializers.ChoiceField(choices=["motor", "light"])
    mode = serializers.ChoiceField(choices=["auto", "on", "off"])
    sync_delay_ms = serializers.IntegerField(required=False, min_value=500, max_value=30000)

    def validate(self, attrs):
        target = attrs.get("target", "online")
        if target == "selected" and not attrs.get("device_ids"):
            raise serializers.ValidationError({"device_ids": "selected target requires device_ids"})
        return attrs


class DeviceCommandPullSerializer(serializers.Serializer):
    sn = serializers.CharField(required=False)
    node_id = serializers.CharField(required=False)
    cloud_device_id = serializers.CharField(required=False)
    device_id = serializers.CharField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=20, default=1)

    def validate(self, attrs):
        if not any(attrs.get(field) for field in ("sn", "node_id", "cloud_device_id", "device_id")):
            raise serializers.ValidationError("one of sn/node_id/cloud_device_id/device_id is required")
        return attrs


class DeviceCommandAckSerializer(serializers.Serializer):
    command_id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=[DeviceCommand.Status.ACKED, DeviceCommand.Status.FAILED])
    message = serializers.CharField(required=False, allow_blank=True, max_length=255)
    ack_at = serializers.DateTimeField(required=False)
    sn = serializers.CharField(required=False)
    node_id = serializers.CharField(required=False)
    cloud_device_id = serializers.CharField(required=False)
    device_id = serializers.CharField(required=False)

    def validate(self, attrs):
        if not any(attrs.get(field) for field in ("sn", "node_id", "cloud_device_id", "device_id")):
            raise serializers.ValidationError("one of sn/node_id/cloud_device_id/device_id is required")
        return attrs


class RuleSerializer(serializers.ModelSerializer):
    deviceId = serializers.IntegerField(source="device_id", read_only=True)
    deviceName = serializers.CharField(source="device.sn", read_only=True)
    slotNo = serializers.IntegerField(source="device.slot_no", read_only=True)
    min = serializers.FloatField(source="min_value", allow_null=True, required=False)
    max = serializers.FloatField(source="max_value", allow_null=True, required=False)
    sampleRate = serializers.IntegerField(source="device.sample_rate", read_only=True)

    class Meta:
        model = Sensor
        fields = [
            "id",
            "deviceId",
            "deviceName",
            "slotNo",
            "code",
            "name",
            "unit",
            "description",
            "min",
            "max",
            "sampleRate",
        ]
        read_only_fields = ["code", "name", "unit", "description"]

    def validate(self, attrs):
        min_value = attrs.get("min_value", getattr(self.instance, "min_value", None))
        max_value = attrs.get("max_value", getattr(self.instance, "max_value", None))
        if min_value is not None and max_value is not None and min_value >= max_value:
            raise serializers.ValidationError({"max": "上限必须大于下限"})
        return attrs
