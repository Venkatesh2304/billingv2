# Generated by Django 5.0 on 2024-07-30 08:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0005_alter_creditlockbill_beat"),
    ]

    operations = [
        migrations.AlterField(
            model_name="creditlockbill",
            name="beat",
            field=models.TextField(blank=True, max_length=50, null=True),
        ),
    ]
