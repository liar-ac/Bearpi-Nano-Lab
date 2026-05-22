from rest_framework.permissions import BasePermission

from apps.accounts.serializers import resolve_role


class CanAcknowledgeAlarm(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and resolve_role(request.user) in {"admin", "experimenter"}
