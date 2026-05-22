from django.contrib import admin

from apps.devices.models import Device, DeviceCommand, Sensor


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["slot_no", "sn", "model", "status", "member", "last_seen", "sample_rate"]
    list_filter = ["status", "model", "lab_id"]
    search_fields = ["sn", "member", "location", "ip_address"]
    list_per_page = 50


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ["id", "device", "code", "name", "unit", "latest_value", "latest_ts"]
    list_filter = ["code"]
    search_fields = ["device__sn", "code", "name"]
    list_per_page = 50


@admin.register(DeviceCommand)
class DeviceCommandAdmin(admin.ModelAdmin):
    list_display = ["id", "device", "command", "status", "created_at", "ack_at"]
    list_filter = ["command", "status"]
    search_fields = ["device__sn", "message"]
    list_per_page = 50
