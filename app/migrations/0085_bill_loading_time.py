# Generated by Django 5.1.1 on 2024-10-29 00:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0084_remove_vehicle_time_bill_delivered'),
    ]

    operations = [
        migrations.AddField(
            model_name='bill',
            name='loading_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
