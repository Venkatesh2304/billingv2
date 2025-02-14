# Generated by Django 5.1.1 on 2024-11-26 14:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0104_alter_chequecollection_cheque_entry"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="ChequeCollection",
            new_name="BankCollection",
        ),
        migrations.AlterUniqueTogether(
            name="bankcollection",
            unique_together={("bill", "cheque_entry", "bank_entry")},
        ),
    ]
