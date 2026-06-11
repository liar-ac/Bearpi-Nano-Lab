from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alarms.models import Alarm
from apps.alarms.permissions import CanAcknowledgeAlarm
from apps.alarms.serializers import AlarmSerializer
from apps.audit.models import AuditLog
from apps.audit.services import record_audit


class AlarmListView(ListAPIView):
    serializer_class = AlarmSerializer

    def get_queryset(self):
        queryset = Alarm.objects.select_related("device", "sensor")
        status_filter = self.request.query_params.get("status")
        level_filter = self.request.query_params.get("level")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            queryset = queryset.exclude(status=Alarm.Status.CLOSED)
        if level_filter:
            queryset = queryset.filter(level=level_filter)
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


class AlarmAckView(APIView):
    permission_classes = [CanAcknowledgeAlarm]

    def post(self, request, alarm_id):
        from django.db import transaction
        with transaction.atomic():
            alarm = get_object_or_404(Alarm.objects.select_related("device", "sensor").select_for_update(), pk=alarm_id)
            if alarm.status == Alarm.Status.CLOSED:
                return Response({"detail": "已关闭的告警无法确认"}, status=400)
            alarm.status = Alarm.Status.ACKNOWLEDGED
            alarm.save(update_fields=["status"])
        record_audit(
            request,
            AuditLog.Action.ALARM_ACK,
            alarm.device.sn,
            f"确认告警：{alarm.message}",
            {"alarmId": alarm.id, "level": alarm.level},
        )
        return Response(AlarmSerializer(alarm).data)
