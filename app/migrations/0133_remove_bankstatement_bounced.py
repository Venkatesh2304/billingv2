# Generated by Django 5.1.1 on 2024-12-12 19:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0132_bankstatement_bounced_alter_bankstatement_bank_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="bankstatement",
            name="bounced",
        ),
    ]