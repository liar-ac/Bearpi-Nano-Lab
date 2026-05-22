from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.accounts.serializers import resolve_role
from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer


class CanViewAuditLog(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and resolve_role(request.user) == "admin"


class AuditLogListView(ListAPIView):
    permission_classes = [CanViewAuditLog]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("actor")
        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        try:
            limit = int(request.query_params.get("limit", 200))
        except ValueError:
            limit = 200
        try:
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            offset = 0
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        total = queryset.count()
        page = queryset[offset : offset + limit]
        return Response({
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": self.get_serializer(page, many=True).data,
        })
