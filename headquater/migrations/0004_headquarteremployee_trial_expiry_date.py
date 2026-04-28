# Generated manually for trial expiry date field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('headquater', '0003_alter_headquarteremployee_image_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='headquarteremployee',
            name='trial_expiry_date',
            field=models.DateTimeField(blank=True, help_text='Trial account expiry date', null=True),
        ),
    ]
