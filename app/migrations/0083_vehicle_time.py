# Generated by Django 5.1.1 on 2024-10-28 16:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0082_retailprint_wholesaleprint'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehicle',
            name='time',
            field=models.DateTimeField(null=True),
        ),
    ]
