from django.contrib import admin

from apps.alarms.models import Alarm


@admin.register(Alarm)
class AlarmAdmin(admin.ModelAdmin):
    list_display = ["id", "device", "sensor", "level", "status", "ts", "message"]
    list_filter = ["level", "status"]
    search_fields = ["device__sn", "message"]
    list_per_page = 50
