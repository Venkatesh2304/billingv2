# Generated by Django 5.0 on 2024-11-18 16:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0086_billdelivery_bill_delivered_time"),
    ]

    operations = [
        migrations.CreateModel(
            name="Settings",
            fields=[
                (
                    "key",
                    models.CharField(max_length=100, primary_key=True, serialize=False),
                ),
                ("value", models.TextField()),
            ],
        ),
    ]
