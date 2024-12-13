# Generated by Django 5.1.1 on 2024-12-13 16:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0136_alter_bankstatement_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bankstatement",
            name="cheque_status",
            field=models.TextField(
                choices=[("passed", "Passed"), ("bounced", "Bounced")],
                db_default="passed",
                default="passed",
            ),
        ),
    ]
