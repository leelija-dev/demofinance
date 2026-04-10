from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('savings', '0018_savingsaccountapplication_nominee_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='savingsaccountapplication',
            name='nominee_relationship',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
