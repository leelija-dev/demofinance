from django.conf import settings


def settings_context(request):
    """
    Expose Django settings as 'setting' in the template context,
    so templates can access settings variables like {{ setting.COMPANY_LOGO_URL }}
    """
    return {
        'setting': settings,
    }