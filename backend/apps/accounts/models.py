from django.contrib.auth.models import User
from django.db import models


class UserRoleProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        EXPERIMENTER = "experimenter", "Experimenter"
        VIEWER = "viewer", "Viewer"

    user = models.OneToOneField(User, related_name="role_profile", on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id"]

    def __str__(self):
        return f"{self.user.username}:{self.role}"
