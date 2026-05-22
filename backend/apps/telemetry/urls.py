from django.urls import path

from apps.telemetry.views import SensorHistoryView, SimulateRealtimeView, TelemetryIngestView

urlpatterns = [
    path("sensors/<int:sensor_id>/history", SensorHistoryView.as_view(), name="sensor-history"),
    path("simulate/realtime", SimulateRealtimeView.as_view(), name="simulate-realtime"),
    path("ingest/telemetry", TelemetryIngestView.as_view(), name="telemetry-ingest"),
]
