# Generated by Django 5.1.1 on 2024-10-19 16:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0072_basepackprocessstatus_delete_processstatus"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="basepackprocessstatus",
            name="id",
        ),
        migrations.AlterField(
            model_name="basepackprocessstatus",
            name="process",
            field=models.TextField(max_length=30, primary_key=True, serialize=False),
        ),
    ]
