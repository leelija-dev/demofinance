from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('savings', '0015_savingsagentassign_active_and_rename'),
    ]

    operations = [
        migrations.AddField(
            model_name='savingsaccountapplication',
            name='rd_principal_balance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='savingsaccountapplication',
            name='rd_interest_accrued',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='savingsaccountapplication',
            name='rd_last_interest_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
