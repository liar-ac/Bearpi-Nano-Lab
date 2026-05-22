from django.db import migrations


def replace_acc_with_motor(apps, schema_editor):
    Sensor = apps.get_model("devices", "Sensor")
    RawPoint = apps.get_model("telemetry", "RawPoint")

    for acc_sensor in Sensor.objects.filter(code="acc"):
        device_id = acc_sensor.device_id
        motor_sensor = Sensor.objects.filter(device_id=device_id, code="motor").first()
        if motor_sensor:
            RawPoint.objects.filter(sensor=acc_sensor).delete()
            acc_sensor.delete()
            continue

        acc_sensor.code = "motor"
        acc_sensor.name = "电机驱动"
        acc_sensor.unit = ""
        acc_sensor.description = "IA1 通风电机状态，0=关闭，1=开启"
        acc_sensor.min_value = 0
        acc_sensor.max_value = 1
        acc_sensor.latest_value = 0
        acc_sensor.save(
            update_fields=[
                "code",
                "name",
                "unit",
                "description",
                "min_value",
                "max_value",
                "latest_value",
            ]
        )
        RawPoint.objects.filter(sensor=acc_sensor).update(value=0)


def restore_motor_to_acc(apps, schema_editor):
    Sensor = apps.get_model("devices", "Sensor")
    Sensor.objects.filter(code="motor").update(
        code="acc",
        name="加速度",
        unit="g",
        description="三轴加速度合成值",
        min_value=0,
        max_value=2,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0001_initial"),
        ("telemetry", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(replace_acc_with_motor, restore_motor_to_acc),
    ]
