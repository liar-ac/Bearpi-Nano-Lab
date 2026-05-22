from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_name", models.CharField(blank=True, max_length=150)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("login", "Login"),
                            ("register", "Register"),
                            ("role_update", "Role update"),
                            ("command_create", "Command create"),
                            ("command_ack", "Command ack"),
                            ("alarm_ack", "Alarm ack"),
                            ("rule_update", "Rule update"),
                        ],
                        max_length=32,
                    ),
                ),
                ("target", models.CharField(max_length=160)),
                ("detail", models.CharField(max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
