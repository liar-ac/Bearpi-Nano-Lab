from django.db import models


class Device(models.Model):
    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"
        WARNING = "warning", "Warning"
        MAINTENANCE = "maintenance", "Maintenance"

    slot_no = models.PositiveIntegerField(unique=True)
    sn = models.CharField(max_length=64, unique=True)
    lab_id = models.CharField(max_length=64, default="lab-embedded-01")
    model = models.CharField(max_length=64, default="BearPi-HM Nano")
    firmware_version = models.CharField(max_length=32, default="unknown")
    location = models.CharField(max_length=128)
    owner = models.CharField(max_length=128)
    member = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OFFLINE)
    last_seen = models.DateTimeField(null=True, blank=True)
    register_time = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    cloud_twin_id = models.CharField(max_length=128, blank=True)
    sample_rate = models.PositiveIntegerField(default=1)
    abnormal_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["slot_no"]
        indexes = [
            models.Index(fields=["status", "last_seen"], name="devices_status_lastseen_idx"),
            models.Index(fields=["last_seen"], name="devices_lastseen_idx"),
        ]

    def __str__(self):
        return self.sn


class Sensor(models.Model):
    device = models.ForeignKey(Device, related_name="sensors", on_delete=models.CASCADE)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=64)
    unit = models.CharField(max_length=16, blank=True)
    description = models.TextField(blank=True)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    latest_ts = models.DateTimeField(null=True, blank=True)
    latest_value = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = [("device", "code")]
        ordering = ["device_id", "id"]

    def __str__(self):
        return f"{self.device.sn}/{self.code}"


class DeviceCommand(models.Model):
    class Command(models.TextChoices):
        REBOOT = "reboot", "Reboot"
        UPGRADE = "upgrade", "Upgrade"
        SET_PARAM = "set_param", "Set Param"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        ACKED = "acked", "Acked"
        FAILED = "failed", "Failed"

    device = models.ForeignKey(Device, related_name="commands", on_delete=models.CASCADE)
    command = models.CharField(max_length=32, choices=Command.choices)
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    ack_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["device", "status", "created_at"], name="devcmd_device_status_idx"),
            models.Index(fields=["status", "created_at"], name="devcmd_status_idx"),
            models.Index(fields=["command", "created_at"], name="devcmd_command_idx"),
        ]

    def __str__(self):
        return f"{self.device.sn}/{self.command}/{self.status}"
