# Generated by Django 5.1.1 on 2024-10-19 15:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0068_einvoice_remove_sales_irn"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessStatu1s",
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
                ("type", models.IntegerField(default=0)),
                ("process", models.TextField(max_length=30)),
                ("time", models.FloatField(blank=True, null=True)),
            ],
        ),
        migrations.RenameModel(
            old_name="ProcessStatus",
            new_name="BillingProcessStatus",
        ),
    ]
