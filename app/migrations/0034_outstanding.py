# Generated by Django 5.0 on 2024-09-14 16:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0033_remove_orders_value"),
    ]

    operations = [
        migrations.CreateModel(
            name="Outstanding",
            fields=[
                (
                    "inum",
                    models.CharField(max_length=20, primary_key=True, serialize=False),
                ),
                ("balance", models.FloatField(blank=True, null=True)),
                ("beat", models.TextField(max_length=40)),
                ("date", models.DateField()),
            ],
            options={
                "managed": False,
            },
        ),
    ]
