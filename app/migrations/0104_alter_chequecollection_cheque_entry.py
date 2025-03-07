# Generated by Django 5.1.1 on 2024-11-26 13:03

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0103_rename_cheque_chequecollection_cheque_entry_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chequecollection",
            name="cheque_entry",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                db_index=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="collection",
                to="app.chequedeposit",
            ),
        ),
    ]
