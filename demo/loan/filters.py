from functools import wraps
from django.conf import settings
from django.db.models import Q
from rest_framework.response import Response

def filter_by_created_by_or_null(method):
    """
    Method decorator for APIView ``get()`` methods that query
    ``LoanMainCategory``, ``LoanCategory``, or ``ProductCategory`` and need
    to scope results by ``created_by=parent_hq_user`` (or null).

    When ``settings.IS_DEMO`` is ``True``, the decorator:
    1. Resolves the parent HQ user from the request
    2. Patches ``.filter()`` on ``LoanMainCategory.objects``,
       ``LoanCategory.objects``, and ``ProductCategory.objects`` to
       automatically add ``Q(created_by=parent_hq_user) | Q(created_by__isnull=True)``
    3. Restores the original ``.filter()`` in a ``finally`` block

    When ``settings.IS_DEMO`` is ``False``, the decorator is a no-op.

    Usage::

        from demo.loan.filters import filter_by_created_by_or_null

        class LoanSubCategoryListAPI(APIView):

            @filter_by_created_by_or_null
            def get(self, request):
                ...
                main_category = LoanMainCategory.objects.filter(
                    main_category_id=main_category_id,
                    is_active=True,
                ).first()

                categories = LoanCategory.objects.filter(
                    main_category=main_category,
                    is_active=True,
                ).order_by('name')
                ...
    """

    @wraps(method)
    def wrapper(self, request, *args, **kwargs):
        if settings.IS_DEMO:
            parent_hq_user = _resolve_parent_hq_user(request)
            if parent_hq_user:
                _patch_filters(parent_hq_user)
                try:
                    response = method(self, request, *args, **kwargs)
                    _inject_created_by(response, parent_hq_user)
                    return response
                finally:
                    _restore_filters()
            else:
                return method(self, request, *args, **kwargs)
        return method(self, request, *args, **kwargs)

    return wrapper


def _resolve_parent_hq_user(request):
    """Resolve the parent HQ user from the request (same logic as
    ``get_parent_hq_user()`` in ``loan/views.py``)."""
    try:
        # Check for HQ user authentication (Django standard auth)
        if hasattr(request.user, "is_headquater_admin"):
            # HQ user is directly authenticated
            return request.user

        # Check for agent authentication (session-based)
        agent_id = request.session.get("agent_id")
        if agent_id:
            try:
                from loan.models import Agent

                agent = Agent.objects.get(agent_id=agent_id)
                # Agent's parent HQ user is the one who created their branch
                return agent.branch.created_by
            except (Agent.DoesNotExist, AttributeError):
                pass

        # Check for branch employee authentication (session-based)
        logged_user_id = request.session.get("logged_user_id")
        if logged_user_id:
            try:
                from loan.models import BranchEmployee

                branch_employee = BranchEmployee.objects.get(id=logged_user_id)
                # Branch employee's parent HQ user is the one who created their branch
                return branch_employee.branch.created_by
            except (BranchEmployee.DoesNotExist, AttributeError):
                pass

        return None
    except (AttributeError, Agent.DoesNotExist, BranchEmployee.DoesNotExist):
        pass

    return None


# ── Monkey-patch machinery ──────────────────────────────────────────────

_originals = {}


def _patch_filters(parent_hq_user):
    from loan.models import LoanMainCategory, LoanCategory, ProductCategory

    _fields = {
        LoanMainCategory: "LoanMainCategory.objects.filter",
        LoanCategory: "LoanCategory.objects.filter",
        ProductCategory: "ProductCategory.objects.filter",
    }

    for model in (LoanMainCategory, LoanCategory, ProductCategory):
        key = f"{model.__module__}.{model.__name__}.objects.filter"
        orig = model.objects.filter
        _originals[key] = orig

        def _make_patched(original_filter):
            def patched_filter(*args, **filter_kwargs):
                q_objects = list(args) if args else []
                q_objects.append(Q(created_by=parent_hq_user) | Q(created_by__isnull=True))
                return original_filter(*q_objects, **filter_kwargs)

            return patched_filter

        model.objects.filter = _make_patched(orig)


def _restore_filters():
    from loan.models import LoanMainCategory, LoanCategory, ProductCategory

    for model in (LoanMainCategory, LoanCategory, ProductCategory):
        key = f"{model.__module__}.{model.__name__}.objects.filter"
        orig = _originals.pop(key, None)
        if orig is not None:
            model.objects.filter = orig


def _inject_created_by(response, parent_hq_user):
    """Inject ``created_by`` into each item of the response data list.

    Adds ``"created_by": parent_hq_user.username`` to each dictionary
    in the response list when ``parent_hq_user`` is provided.

    This runs only when ``settings.IS_DEMO`` is ``True``, ensuring the
    ``created_by`` field is present in the response only in demo mode.
    """
    if hasattr(response, "data") and isinstance(response.data, list):
        username = parent_hq_user.username if parent_hq_user else None
        for item in response.data:
            if isinstance(item, dict):
                item["created_by"] = username





def filter_by_parent_hq(model_class, return_empty_on_fail=False):
    """
    Completely isolates parent_hq_user resolution and filtering logic inside the decorator.
    Dynamically patches the target Model's .filter() method during view execution.

    If this decorator is deleted, the main view code will execute natively without changes.
    """

    def decorator(method):
        @wraps(method)
        def wrapper(self, request, *args, **kwargs):
            if not settings.IS_DEMO:
                return method(self, request, *args, **kwargs)
            # 1. Resolve parent HQ user completely inside the decorator
            parent_hq_user = None

            if hasattr(request.user, "is_headquater_admin"):
                parent_hq_user = request.user

            agent_id = request.session.get("agent_id")
            if agent_id and not parent_hq_user:
                try:
                    from loan.models import Agent

                    agent = Agent.objects.get(agent_id=agent_id)
                    parent_hq_user = agent.branch.created_by
                except (Agent.DoesNotExist, AttributeError):
                    pass

            logged_user_id = request.session.get("logged_user_id")
            if logged_user_id and not parent_hq_user:
                try:
                    from loan.models import BranchEmployee

                    branch_employee = BranchEmployee.objects.get(id=logged_user_id)
                    parent_hq_user = branch_employee.branch.created_by
                except (BranchEmployee.DoesNotExist, AttributeError):
                    pass

            # 2. Handle missing authentication fallback rules
            if not parent_hq_user:
                if return_empty_on_fail:
                    return Response([])
                return Response({"error": "Authentication required"}, status=401)

            # 3. Dynamic Monkey-Patching: Intercept the target model's filter queries
            original_filter = model_class.objects.filter

            def patched_filter(*args, **filter_kwargs):
                # Forces 'created_by' filtering into every query on this model
                filter_kwargs["created_by"] = parent_hq_user
                return original_filter(*args, **filter_kwargs)

            # Apply the patch
            model_class.objects.filter = patched_filter

            try:
                # 4. Execute the original view function cleanly
                return method(self, request, *args, **kwargs)
            finally:
                # 5. Safety restoration: Put back the original Django .filter() method
                model_class.objects.filter = original_filter

        return wrapper

    return decorator
