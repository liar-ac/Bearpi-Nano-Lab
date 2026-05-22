from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alarms", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="alarm",
            index=models.Index(
                fields=["status", "-ts"],
                name="alarms_status_ts_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="alarm",
            index=models.Index(
                fields=["device", "status"],
                name="alarms_device_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="alarm",
            index=models.Index(
                fields=["sensor", "status"],
                name="alarms_sensor_status_idx",
            ),
        ),
    ]
