# Generated by Django 5.1.1 on 2024-11-25 16:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0092_todaybillin"),
    ]

    operations = [
        migrations.AddField(
            model_name="bill",
            name="cash_bill",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="bill",
            name="is_reloaded",
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
