from rest_framework import serializers

from apps.alarms.models import Alarm


class AlarmSerializer(serializers.ModelSerializer):
    deviceId = serializers.IntegerField(source="device_id", read_only=True)
    sensorId = serializers.IntegerField(source="sensor_id", read_only=True, allow_null=True)
    deviceName = serializers.CharField(source="device.sn", read_only=True)

    class Meta:
        model = Alarm
        fields = ["id", "deviceId", "sensorId", "deviceName", "ts", "level", "status", "message"]
