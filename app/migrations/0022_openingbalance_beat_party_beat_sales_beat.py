# Generated by Django 5.0 on 2024-09-14 00:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0021_beat"),
    ]

    operations = [
        migrations.AddField(
            model_name="openingbalance",
            name="beat",
            field=models.TextField(default="", max_length=40),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="party",
            name="beat",
            field=models.CharField(default="", max_length=60),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="sales",
            name="beat",
            field=models.TextField(default="", max_length=40),
            preserve_default=False,
        ),
    ]