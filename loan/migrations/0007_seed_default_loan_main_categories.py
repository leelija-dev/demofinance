import hashlib

from django.db import migrations


DEFAULT_MAIN_CATEGORIES = [
    'Personal Loans',
    'Home & Property Loans',
    'Vehicle Loans',
    'Consumer / Gadget Loans',
]


def seed_default_main_categories(apps, schema_editor):
    LoanMainCategory = apps.get_model('loan', 'LoanMainCategory')

    # If a previous failed migration run inserted rows with an empty primary key,
    # remove them so we can safely seed again.
    try:
        LoanMainCategory.objects.filter(main_category_id='').delete()
    except Exception:
        pass

    for name in DEFAULT_MAIN_CATEGORIES:
        main_category_id = f"LoanMAIN-{hashlib.md5(name.encode('utf-8')).hexdigest()[:8].upper()}"

        obj, created = LoanMainCategory.objects.get_or_create(
            name=name,
            defaults={
                'main_category_id': main_category_id,
                'is_active': True,
            },
        )

        # If it already existed but has a blank ID (or any unexpected), normalize it.
        if not getattr(obj, 'main_category_id', None):
            obj.main_category_id = main_category_id
            obj.save(update_fields=['main_category_id'])


def unseed_default_main_categories(apps, schema_editor):
    LoanMainCategory = apps.get_model('loan', 'LoanMainCategory')
    LoanMainCategory.objects.filter(name__in=DEFAULT_MAIN_CATEGORIES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('loan', '0006_loan_main_category_and_category_link'),
    ]

    operations = [
        migrations.RunPython(seed_default_main_categories, reverse_code=unseed_default_main_categories),
    ]
