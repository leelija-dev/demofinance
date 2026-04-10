import uuid

from django.db import migrations


def _new_prefixed_id(prefix: str) -> str:
    short_uuid = str(uuid.uuid4())[:8].upper()
    return f"{prefix}{short_uuid}"


def seed_samsung_mobiles(apps, schema_editor):
    MobileMainCategory = apps.get_model('loan', 'MobileMainCategory')
    MobileSubCategory = apps.get_model('loan', 'MobileSubCategory')
    Mobile = apps.get_model('loan', 'Mobile')

    # Historical models used by migrations won't run your custom save() method.
    # So we must set CharField PKs ourselves.
    Mobile.objects.filter(mobile_id='').delete()
    MobileSubCategory.objects.filter(sub_category_id='').delete()
    MobileMainCategory.objects.filter(main_category_id='').delete()

    samsung_main = MobileMainCategory.objects.filter(name='Samsung').first()
    if not samsung_main:
        samsung_main = MobileMainCategory.objects.create(
            main_category_id=_new_prefixed_id('MOBMAIN-'),
            name='Samsung',
            is_active=True,
        )

    sub_s24 = MobileSubCategory.objects.filter(main_category=samsung_main, name='Galaxy S24').first()
    if not sub_s24:
        sub_s24 = MobileSubCategory.objects.create(
            sub_category_id=_new_prefixed_id('MOBSUB-'),
            main_category=samsung_main,
            name='Galaxy S24',
            is_active=True,
        )

    sub_a15 = MobileSubCategory.objects.filter(main_category=samsung_main, name='Galaxy A15').first()
    if not sub_a15:
        sub_a15 = MobileSubCategory.objects.create(
            sub_category_id=_new_prefixed_id('MOBSUB-'),
            main_category=samsung_main,
            name='Galaxy A15',
            is_active=True,
        )

    if not Mobile.objects.filter(sub_category=sub_s24, name='Samsung Galaxy S24').exists():
        Mobile.objects.create(
            mobile_id=_new_prefixed_id('MOB-'),
            sub_category=sub_s24,
            name='Samsung Galaxy S24',
            price='74999.00',
            is_active=True,
        )
    if not Mobile.objects.filter(sub_category=sub_s24, name='Samsung Galaxy S24+').exists():
        Mobile.objects.create(
            mobile_id=_new_prefixed_id('MOB-'),
            sub_category=sub_s24,
            name='Samsung Galaxy S24+',
            price='94999.00',
            is_active=True,
        )
    if not Mobile.objects.filter(sub_category=sub_s24, name='Samsung Galaxy S24 Ultra').exists():
        Mobile.objects.create(
            mobile_id=_new_prefixed_id('MOB-'),
            sub_category=sub_s24,
            name='Samsung Galaxy S24 Ultra',
            price='129999.00',
            is_active=True,
        )
    if not Mobile.objects.filter(sub_category=sub_a15, name='Samsung Galaxy A15').exists():
        Mobile.objects.create(
            mobile_id=_new_prefixed_id('MOB-'),
            sub_category=sub_a15,
            name='Samsung Galaxy A15',
            price='17999.00',
            is_active=True,
        )


def unseed_samsung_mobiles(apps, schema_editor):
    MobileMainCategory = apps.get_model('loan', 'MobileMainCategory')
    MobileSubCategory = apps.get_model('loan', 'MobileSubCategory')
    Mobile = apps.get_model('loan', 'Mobile')

    samsung_main = MobileMainCategory.objects.filter(name='Samsung').first()
    if not samsung_main:
        return

    sub_names = ['Galaxy S24', 'Galaxy A15']

    Mobile.objects.filter(
        sub_category__main_category=samsung_main,
        sub_category__name__in=sub_names,
    ).delete()

    MobileSubCategory.objects.filter(
        main_category=samsung_main,
        name__in=sub_names,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('loan', '0009_mobilemaincategory_mobilesubcategory_mobile'),
    ]

    operations = [
        migrations.RunPython(seed_samsung_mobiles, unseed_samsung_mobiles),
    ]
