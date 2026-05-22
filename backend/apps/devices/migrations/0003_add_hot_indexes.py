from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0002_replace_acc_with_motor"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="device",
            index=models.Index(fields=["status", "last_seen"], name="devices_status_lastseen_idx"),
        ),
        migrations.AddIndex(
            model_name="device",
            index=models.Index(fields=["last_seen"], name="devices_lastseen_idx"),
        ),
        migrations.AddIndex(
            model_name="devicecommand",
            index=models.Index(
                fields=["device", "status", "created_at"],
                name="devcmd_device_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="devicecommand",
            index=models.Index(
                fields=["status", "created_at"],
                name="devcmd_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="devicecommand",
            index=models.Index(
                fields=["command", "created_at"],
                name="devcmd_command_idx",
            ),
        ),
    ]
