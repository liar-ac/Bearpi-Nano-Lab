from django.urls import path

from apps.devices.views import (
    DeviceCommandAckView,
    DeviceBulkCommandView,
    DeviceBulkTaskListView,
    DeviceBulkTaskRetryView,
    DeviceCommandPullView,
    DeviceCommandView,
    DeviceDetailView,
    DeviceListView,
    RuleDetailView,
    RuleListView,
)

urlpatterns = [
    path("devices", DeviceListView.as_view(), name="device-list"),
    path("devices/<int:pk>", DeviceDetailView.as_view(), name="device-detail"),
    path("devices/<int:device_id>/commands", DeviceCommandView.as_view(), name="device-commands"),
    path("devices/bulk-commands", DeviceBulkCommandView.as_view(), name="device-bulk-commands"),
    path("devices/bulk-tasks", DeviceBulkTaskListView.as_view(), name="device-bulk-tasks"),
    path("devices/bulk-tasks/<str:batch_id>/retry", DeviceBulkTaskRetryView.as_view(), name="device-bulk-task-retry"),
    path("device/commands/pull", DeviceCommandPullView.as_view(), name="device-command-pull"),
    path("device/commands/ack", DeviceCommandAckView.as_view(), name="device-command-ack"),
    path("rules", RuleListView.as_view(), name="rule-list"),
    path("rules/<int:sensor_id>", RuleDetailView.as_view(), name="rule-detail"),
]
