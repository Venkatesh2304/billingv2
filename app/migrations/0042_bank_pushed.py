# Generated by Django 5.0 on 2024-09-16 15:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0041_bank_type_alter_bankcollection_entry_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="bank",
            name="pushed",
            field=models.BooleanField(db_default=models.Value(False), default=False),
        ),
    ]