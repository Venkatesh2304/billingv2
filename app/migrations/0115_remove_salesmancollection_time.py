# Generated by Django 5.1.1 on 2024-11-30 13:10

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0114_alter_salesmancollection_time"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="salesmancollection",
            name="time",
        ),
    ]
