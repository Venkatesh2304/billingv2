# Generated by Django 5.1.1 on 2024-10-19 16:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0073_remove_basepackprocessstatus_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="basepackprocessstatus",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                default=1,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="basepackprocessstatus",
            name="process",
            field=models.TextField(max_length=30, unique=True),
        ),
    ]
