# Generated by Django 5.1.1 on 2024-12-03 13:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0122_alter_chequedeposit_bank"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SalesmanPendingSheet",
        ),
        migrations.CreateModel(
            name="SalesmanPendingSheetX",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("app.beat",),
        ),
    ]
