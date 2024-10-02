# Generated by Django 5.0 on 2024-09-26 01:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0044_alter_bankcollection_unique_together"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bank",
            name="type",
            field=models.TextField(
                choices=[
                    ("cheque", "Cheque"),
                    ("neft", "NEFT"),
                    ("cash", "Cash Deposit"),
                    ("others", "Others"),
                ],
                default="cheque",
                max_length=15,
            ),
            preserve_default=False,
        ),
    ]
