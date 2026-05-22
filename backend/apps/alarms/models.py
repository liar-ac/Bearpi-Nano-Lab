from django.db import models


class Alarm(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        NEW = "new", "New"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        CLOSED = "closed", "Closed"

    device = models.ForeignKey("devices.Device", related_name="alarms", on_delete=models.CASCADE)
    sensor = models.ForeignKey("devices.Sensor", related_name="alarms", on_delete=models.CASCADE, null=True, blank=True)
    ts = models.DateTimeField(db_index=True)
    level = models.CharField(max_length=16, choices=Level.choices)
    message = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)

    class Meta:
        ordering = ["-ts"]
        indexes = [
            models.Index(fields=["status", "-ts"], name="alarms_status_ts_idx"),
            models.Index(fields=["device", "status"], name="alarms_device_status_idx"),
            models.Index(fields=["sensor", "status"], name="alarms_sensor_status_idx"),
        ]

    def __str__(self):
        return f"{self.level}:{self.message}"
