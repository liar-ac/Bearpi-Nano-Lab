from django.contrib import admin

from apps.telemetry.models import RawPoint


@admin.register(RawPoint)
class RawPointAdmin(admin.ModelAdmin):
    list_display = ["id", "device", "sensor", "ts", "value"]
    list_filter = ["sensor__code"]
    search_fields = ["device__sn"]
    list_per_page = 50
