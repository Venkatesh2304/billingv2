# Generated by Django 5.1.1 on 2024-12-03 22:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0127_alter_pendingsheetbill_unique_together"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="name_on_impact",
            field=models.CharField(max_length=30, null=True),
        ),
    ]
