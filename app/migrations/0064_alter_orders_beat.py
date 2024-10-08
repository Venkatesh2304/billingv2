# Generated by Django 5.1.1 on 2024-10-11 03:09

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0063_alter_print_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orders",
            name="beat",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                db_index=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="orders",
                to="app.beat",
            ),
        ),
    ]
