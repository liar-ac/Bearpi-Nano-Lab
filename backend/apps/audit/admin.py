from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "action", "actor_name", "target", "ip_address", "created_at"]
    list_filter = ["action"]
    search_fields = ["actor_name", "target", "detail"]
    list_per_page = 50
    readonly_fields = ["actor", "actor_name", "action", "target", "detail", "metadata", "ip_address", "created_at"]
