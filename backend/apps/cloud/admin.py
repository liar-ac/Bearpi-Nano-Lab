from django.contrib import admin

from apps.cloud.models import CloudDeviceStatus


@admin.register(CloudDeviceStatus)
class CloudDeviceStatusAdmin(admin.ModelAdmin):
    list_display = ["device", "platform", "mqtt_status", "sync_status", "rule_engine", "last_sync"]
    list_filter = ["mqtt_status", "sync_status", "rule_engine"]
    search_fields = ["device__sn", "node_id", "cloud_device_id"]
