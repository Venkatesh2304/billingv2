# Generated by Django 5.1.1 on 2024-10-28 00:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0080_salesmanloadingsheet_remove_einvoice_bill_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='RetailPrint',
        ),
        migrations.DeleteModel(
            name='WholeSalePrint',
        ),
        migrations.RenameModel(
            old_name='Print',
            new_name='Bill',
        ),
    ]
