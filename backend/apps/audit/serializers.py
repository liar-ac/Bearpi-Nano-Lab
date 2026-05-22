from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actorName = serializers.CharField(source="actor_name")
    ipAddress = serializers.IPAddressField(source="ip_address", allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at")

    class Meta:
        model = AuditLog
        fields = ["id", "actorName", "action", "target", "detail", "metadata", "ipAddress", "createdAt"]
