# Generated by Django 5.1.1 on 2024-11-26 12:31

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0102_alter_chequecollection_bank_entry"),
    ]

    operations = [
        migrations.RenameField(
            model_name="chequecollection",
            old_name="cheque",
            new_name="cheque_entry",
        ),
        migrations.RemoveField(
            model_name="bankstatement",
            name="matched_cheque",
        ),
        migrations.AddField(
            model_name="bankstatement",
            name="cheque_entry",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="bank_entry",
                to="app.chequedeposit",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="chequecollection",
            unique_together={("bill", "cheque_entry")},
        ),
    ]