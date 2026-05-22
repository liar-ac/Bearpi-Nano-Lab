from django.db import models


class CloudDeviceStatus(models.Model):
    class MqttStatus(models.TextChoices):
        CONNECTED = "connected", "Connected"
        DISCONNECTED = "disconnected", "Disconnected"
        UNKNOWN = "unknown", "Unknown"

    class RuleEngine(models.TextChoices):
        ENABLED = "enabled", "Enabled"
        DISABLED = "disabled", "Disabled"
        PENDING = "pending", "Pending"

    class SyncStatus(models.TextChoices):
        SYNCED = "synced", "Synced"
        DELAYED = "delayed", "Delayed"
        DISCONNECTED = "disconnected", "Disconnected"
        UNBOUND = "unbound", "Unbound"

    device = models.OneToOneField("devices.Device", related_name="cloud", on_delete=models.CASCADE)
    platform = models.CharField(max_length=64, default="Huawei Cloud IoTDA")
    product_id = models.CharField(max_length=128)
    cloud_device_id = models.CharField(max_length=128)
    node_id = models.CharField(max_length=128)
    mqtt_status = models.CharField(max_length=16, choices=MqttStatus.choices, default=MqttStatus.UNKNOWN)
    shadow_version = models.PositiveIntegerField(default=1)
    rule_engine = models.CharField(max_length=16, choices=RuleEngine.choices, default=RuleEngine.PENDING)
    last_sync = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=16, choices=SyncStatus.choices, default=SyncStatus.UNBOUND)

    def __str__(self):
        return f"{self.platform}/{self.node_id}"
