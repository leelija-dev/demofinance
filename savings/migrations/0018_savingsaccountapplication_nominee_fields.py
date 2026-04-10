from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('savings', '0017_savingscollection_deposit_tracking_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='savingsaccountapplication',
            name='nominee_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='savingsaccountapplication',
            name='nominee_kyc_type',
            field=models.CharField(blank=True, choices=[('aadhaar', 'Aadhaar'), ('pan', 'PAN')], max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='savingsaccountapplication',
            name='nominee_kyc_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='savingsaccountapplication',
            name='nominee_kyc_document',
            field=models.FileField(blank=True, null=True, upload_to='static/nominee/kyc/'),
        ),
    ]
