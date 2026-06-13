from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0003_add_hot_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="devicecommand",
            name="sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
