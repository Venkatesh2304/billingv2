# Generated by Django 5.1.1 on 2024-12-04 15:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0128_vehicle_name_on_impact"),
    ]

    operations = [
        migrations.AddField(
            model_name="bill",
            name="delivery_reason",
            field=models.TextField(
                blank=True,
                choices=[
                    ("scanned", "Scanned"),
                    ("bill_with_shop", "Bill With Shop"),
                    ("cash_bill_success", "Cash Bill (Collected Money)"),
                    ("bill_return", "Bill Return"),
                    ("qrcode_not_found", "QR Code Not Found"),
                    ("others", "Other Reason"),
                ],
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="pendingsheetbill",
            name="bill_status",
            field=models.TextField(
                choices=[
                    ("scanned", "Scanned"),
                    ("qrcode_not_found", "qrcode_not_found"),
                    ("loading_sheet", "loading_sheet"),
                    ("sales_return", "sales_return"),
                    ("others", "Other Reason"),
                ],
                default="scanned",
                max_length=25,
                null=True,
            ),
        ),
    ]
