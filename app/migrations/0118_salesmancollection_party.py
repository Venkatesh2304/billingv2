# Generated by Django 5.1.1 on 2024-11-30 13:58

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0117_salesmancollection_time"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesmancollection",
            name="party",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                to="app.party",
            ),
        ),
    ]
