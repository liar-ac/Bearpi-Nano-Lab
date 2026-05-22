from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = "login", "Login"
        REGISTER = "register", "Register"
        ROLE_UPDATE = "role_update", "Role update"
        COMMAND_CREATE = "command_create", "Command create"
        COMMAND_ACK = "command_ack", "Command ack"
        ALARM_ACK = "alarm_ack", "Alarm ack"
        RULE_UPDATE = "rule_update", "Rule update"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    actor_name = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=32, choices=Action.choices)
    target = models.CharField(max_length=160)
    detail = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"], name="audit_action_created_idx"),
        ]

    def __str__(self):
        return f"{self.action}/{self.target}"
