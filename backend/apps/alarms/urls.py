from django.urls import path

from apps.alarms.views import AlarmAckView, AlarmListView

urlpatterns = [
    path("alarms", AlarmListView.as_view(), name="alarm-list"),
    path("alarms/<int:alarm_id>/ack", AlarmAckView.as_view(), name="alarm-ack"),
]
