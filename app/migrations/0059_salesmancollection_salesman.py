# Generated by Django 5.1.1 on 2024-10-09 20:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0058_salesmancollection_salesmancollectionbill"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesmancollection",
            name="salesman",
            field=models.CharField(blank=True, max_length=25, null=True),
        ),
    ]