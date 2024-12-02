# Generated by Django 5.1.1 on 2024-11-30 16:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0120_alter_chequedeposit_bank"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chequedeposit",
            name="bank",
            field=models.CharField(
                choices=[
                    ("KVB 650", "KVB 650"),
                    ("HDFC", "HDFC"),
                    ("CENTRAL BANK", "CENTRAL BANK"),
                    ("SBI", "SBI"),
                    ("INDIAN BANK", "INDIAN BANK"),
                    ("IOB", "IOB"),
                    ("AXIS", "AXIS"),
                    ("ICICI", "ICICI"),
                    ("BARODA", "BARODA"),
                    ("CUB", "CUB"),
                    ("KOTAK", "KOTAK"),
                    ("SYNDICATE", "SYNDICATE"),
                    ("TMB", "TMB"),
                    ("UNION BANK", "UNION BANK"),
                    ("UNITED BANK", "UNITED BANK"),
                    ("TCB", "TCB"),
                    ("PGB", "PGB"),
                ],
                max_length=100,
            ),
        ),
    ]