# Generated by Django 5.0 on 2024-07-30 05:09

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Billing",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("start_time", models.DateTimeField()),
                ("end_time", models.DateTimeField(blank=True, null=True)),
                ("status", models.IntegerField()),
                ("error", models.TextField(blank=True, max_length=100000, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="BillStatistics",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("type", models.TextField(max_length=30)),
                ("count", models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name="CreditLockBill",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("party", models.TextField(max_length=30)),
                ("bills", models.TextField(max_length=30)),
                ("value", models.FloatField()),
                ("salesman", models.TextField(max_length=30)),
                ("collection", models.TextField(max_length=30)),
                ("phone", models.TextField(max_length=30)),
                ("data", models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name="ProcessStatus",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("status", models.IntegerField(default=0)),
                ("process", models.TextField(max_length=30)),
                ("time", models.FloatField(blank=True, null=True)),
                (
                    "billing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="process_status",
                        to="app.billing",
                    ),
                ),
            ],
        ),
    ]
