from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loan', '0007_seed_default_loan_main_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='loaninterest',
            name='main_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='loan_interest_rates', to='loan.loanmaincategory'),
        ),
        migrations.AddField(
            model_name='deductions',
            name='main_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='loan_deductions', to='loan.loanmaincategory'),
        ),
        migrations.AddField(
            model_name='latefeesetting',
            name='main_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='late_fee_settings', to='loan.loanmaincategory'),
        ),
        migrations.AlterUniqueTogether(
            name='loaninterest',
            unique_together={('main_category', 'rate_of_interest')},
        ),
        migrations.AlterUniqueTogether(
            name='deductions',
            unique_together={('main_category', 'deduction_name', 'deduction_type')},
        ),
    ]
