# Generated by Django 5.0 on 2024-07-30 18:56

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0009_alter_orders_creditlock"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orders",
            name="creditlock",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to="app.creditlockbill",
            ),
        ),
    ]
