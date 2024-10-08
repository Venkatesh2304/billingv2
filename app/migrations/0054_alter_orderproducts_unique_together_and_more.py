# Generated by Django 5.1.1 on 2024-10-07 11:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0053_remove_orderproducts_billed"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="orderproducts",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="orderproducts",
            name="batch",
            field=models.TextField(db_default="00000", default="00000", max_length=10),
        ),
        migrations.AlterUniqueTogether(
            name="orderproducts",
            unique_together={("order", "product", "batch")},
        ),
    ]
