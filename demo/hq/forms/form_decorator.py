from functools import wraps
from django.conf import settings
from django import forms
from django.db.models import Q


def check_demo_duplicate_loan_main_category_in_form():
    """
    Decorator for form clean_FIELD methods to check for duplicate entries.
    Safely intercepts and overrides the form's native validation during demo mode.
    Can be safely removed in production without modifying the form.
    """

    def decorator(clean_method):
        @wraps(clean_method)
        def wrapper(form_instance, *args, **kwargs):

            # --- CASE 1: PRODUCTION ENVIRONMENT ---
            # Run the form naturally. If the decorator is deleted later, this is exactly how it will run.
            if not settings.IS_DEMO:
                return clean_method(form_instance, *args, **kwargs)

            # --- CASE 2: DEMO ENVIRONMENT ---
            try:
                # Execute the form's native clean method first.
                # If there are NO duplicates anywhere in the DB, it passes cleanly.
                return clean_method(form_instance, *args, **kwargs)

            except forms.ValidationError as e:
                # If the form raised a ValidationError, it means a global duplicate exists!
                # Now we must double-check if this duplicate is a tenant collision we should ignore.

                field_name = clean_method.__name__.replace("clean_", "")
                field_value = form_instance.cleaned_data.get(field_name)

                if field_value:
                    model_class = form_instance._meta.model
                    qs = model_class.objects.filter(**{field_name: field_value})

                    if form_instance.instance and form_instance.instance.pk:
                        qs = qs.exclude(pk=form_instance.instance.pk)

                    # Identify the active tenant session user
                    current_user = getattr(form_instance.instance, "created_by", None)
                    if not current_user and hasattr(form_instance, "current_user"):
                        current_user = form_instance.current_user

                    # Loop through the duplicates that caused the form to crash
                    for existing_record in qs:
                        # CRASH: If it's a global template record (no owner)
                        if existing_record.created_by is None:
                            raise e
                        # CRASH: If it belongs to the active demo user session
                        if existing_record.created_by and current_user and existing_record.created_by == current_user:
                            raise e

                # SILENCE: If the loop finishes without hitting a "raise e", it means the duplicate
                # belongs to another demo user. We swallow the exception and safely return the value!
                return field_value

        return wrapper

    return decorator


def headquater_form_demo_filter_queryset(queryset_fields_name):
    """
    Decorator for ModelForm.__init__ that handles demo user isolation.

    Completes __init__, filters the specified queryset field by created_by=self.user
    (only when settings.IS_DEMO is enabled and user is provided).

    Usage:
        class MyForm(ModelForm):
            @headquater_form_demo_filter_queryset('interest_rate')
            def __init__(self, *args, **kwargs):
                ...
        or

        class MyForm(ModelForm):
            @headquater_form_demo_filter_queryset({'loan_category', 'loan_main_category'})
            def __init__(self, *args, **kwargs):
                ...

    Args:
        queryset_fields_name: The name of the form field whose queryset
                             should be filtered (either string or dict).
    """

    def update_queryset(self, queryset_field_name):
        field = self.fields.get(queryset_field_name)
        if field and hasattr(field, "queryset"):
            field.queryset = field.queryset.filter(created_by=self.user)

    def decorator(init_method):
        @wraps(init_method)
        def wrapper(self, *args, **kwargs):
            init_method(self, *args, **kwargs)
            if settings.IS_DEMO:
                if self.user is not None:
                    if isinstance(queryset_fields_name, str):
                        update_queryset(self, queryset_fields_name)
                    if isinstance(queryset_fields_name, set):
                        for queryset_field_name in queryset_fields_name:
                            update_queryset(self, queryset_field_name)

        return wrapper

    return decorator
