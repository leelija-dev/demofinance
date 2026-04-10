from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('savings', '0016_savingsaccountapplication_rd_tracking_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='savingscollection',
            name='is_deposited_to_branch',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='savingscollection',
            name='deposited_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='savingscollection',
            name='deposited_deposit_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
