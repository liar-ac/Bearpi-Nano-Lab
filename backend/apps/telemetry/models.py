from django.db import models


class RawPoint(models.Model):
    ts = models.DateTimeField(db_index=True)
    device = models.ForeignKey("devices.Device", related_name="raw_points", on_delete=models.CASCADE)
    sensor = models.ForeignKey("devices.Sensor", related_name="raw_points", on_delete=models.CASCADE)
    value = models.FloatField()

    class Meta:
        indexes = [
            models.Index(fields=["sensor", "ts"]),
            models.Index(fields=["device", "ts"]),
        ]
        ordering = ["ts"]

    def __str__(self):
        return f"{self.sensor_id}@{self.ts}:{self.value}"
