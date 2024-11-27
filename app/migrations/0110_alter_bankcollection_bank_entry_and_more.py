# Generated by Django 5.1.1 on 2024-11-27 13:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0109_remove_bankcollection_coll_code_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bankcollection",
            name="bank_entry",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                db_index=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="collection",
                to="app.bankstatement",
            ),
        ),
        migrations.AlterField(
            model_name="bankcollection",
            name="cheque_entry",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                db_index=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="collection",
                to="app.chequedeposit",
            ),
        ),
    ]
