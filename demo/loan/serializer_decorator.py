from functools import wraps
from django.conf import settings


def get_branch_created_by_decorator(method):
    """
    Method decorator for DRF SerializerMethodField methods that filter
    ``Deductions`` objects and need to scope them by ``obj.branch.created_by``.

    When ``settings.IS_DEMO`` is ``True``, the decorator patches
    ``Deductions.objects.filter`` to automatically add
    ``created_by=obj.branch.created_by`` to every filter call inside the
    decorated method. The original ``filter`` is restored in a ``finally``
    block, so other code is unaffected.

    When ``settings.IS_DEMO`` is ``False``, the decorator is a no-op.

    Usage::

        from demo.loan.serializer_decorator import get_branch_created_by_decorator

        class LoanDisbursedListSerializer(serializers.ModelSerializer):

            @get_branch_created_by_decorator
            def get_deductions(self, obj):
                loans = self.get_loans(obj)
                main_category = loans[0].get('loan_category').get('main_category') if loans else None
                deductions = Deductions.objects.filter(main_category=main_category)
                return DeductionSerializer(deductions, many=True).data
    """

    @wraps(method)
    def wrapper(self, obj, *args, **kwargs):
        if settings.IS_DEMO:
            from loan.models import Deductions

            branch_created_by = obj.branch.created_by
            original_filter = Deductions.objects.filter

            def patched_filter(**filter_kwargs):
                return original_filter(created_by=branch_created_by, **filter_kwargs)

            Deductions.objects.filter = patched_filter
            try:
                return method(self, obj, *args, **kwargs)
            finally:
                Deductions.objects.filter = original_filter

        return method(self, obj, *args, **kwargs)

    return wrapper