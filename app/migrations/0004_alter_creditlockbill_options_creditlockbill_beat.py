# Generated by Django 5.0 on 2024-07-30 08:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0003_alter_billstatistics_count"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="creditlockbill",
            options={"verbose_name": "Billing", "verbose_name_plural": "Billing"},
        ),
        migrations.AddField(
            model_name="creditlockbill",
            name="beat",
            field=models.TextField(default=None, max_length=50),
            preserve_default=False,
        ),
    ]