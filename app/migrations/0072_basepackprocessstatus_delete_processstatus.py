# Generated by Django 5.1.1 on 2024-10-19 15:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0071_alter_processstatus_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="BasepackProcessStatus",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("status", models.IntegerField(default=0)),
                ("process", models.TextField(max_length=30)),
                ("time", models.FloatField(blank=True, null=True)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.DeleteModel(
            name="ProcessStatus",
        ),
    ]
