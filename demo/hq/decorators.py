from functools import wraps
from django.conf import settings
from django.db.models import Q


def branch_created_by_filter_decorator(cls):
    """
    Class decorator for HQ views that adds a `get_branch_filter` helper method.

    Extracts the common `branch__created_by=self.request.user` filter pattern
    used across HQ saving views to filter records by branches the current user created.

    This filter only applies when settings.IS_DEMO is True. When IS_DEMO is False,
    it returns an empty dict, meaning no branch filter is applied.

    Usage:
        @branch_created_by_filter_decorator
        class SomeHQView(LoginRequiredMixin, TemplateView):
            ...

        Then inside any queryset filter:
            qs = SomeModel.objects.filter(**self.get_branch_filter())

        For Branch model directly:
            Branch.objects.filter(**self.get_branch_filter(field='created_by'))
    """

    def get_branch_filter(self, field="branch__created_by"):
        """
        Returns a dict with the branch-created-by filter condition
        based on the current request user.

        Only applies the filter when settings.IS_DEMO is True.
        When IS_DEMO is False, returns an empty dict (no filter).

        Args:
            field (str): The field name to filter on.
                         Defaults to 'branch__created_by' for related lookups.
                         Use 'created_by' for Branch.objects.filter() directly.

        Returns:
            dict: e.g. {'branch__created_by': <request.user>} when IS_DEMO is True,
                  or {} when IS_DEMO is False.
        """
        if not settings.IS_DEMO:
            return {}
        return {field: self.request.user}

    cls.filter_kwargs = get_branch_filter
    return cls


def created_by_filter(field="created_by"):
    """
    Decorator for function-based views that replaces kwargs with
    the appropriate user filter based on IS_DEMO setting.

    When IS_DEMO is True, adds {field: request.user} to the filter kwargs.
    When IS_DEMO is False, returns empty dict {} (no filtering).

    Usage:
        @created_by_filter(field='created_by')
        def saving_management(request):
            ...

        Then use it as:
            queryset.filter(**request.filter_kwargs)
            -- or --
            queryset.filter(**_get_field_filter(request))
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if settings.IS_DEMO:
                request.filter_kwargs = {field: request.user}
            else:
                request.filter_kwargs = {}
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# Bellow For Headquater views ------------------------------------------------------------------------------------------------------------------------------------


def check_demo_mode(func):
    """
    Decorator that encapsulates the full demo filtering logic.
    Executes and builds the filter ONLY if IS_DEMO is True.
    """

    @wraps(func)
    def wrapper(ref, isBranch=False, isNullable=False, *args, **kwargs):
        # 1. Execute logic ONLY when IS_DEMO is True
        if getattr(settings, "IS_DEMO", False):
            field = "branch__created_by" if isBranch else "created_by"
            user = getattr(ref, "user", ref)

            if isNullable:
                null_lookup = f"{field}__isnull"
                return Q(**{field: user}) | Q(**{null_lookup: True})

            return Q(**{field: user})

        # 2. Otherwise, skip logic and return empty Q object
        return Q()

    return wrapper


def apply_demo_filter(func):
    """
    Decorator that encapsulates demo response filtering.
    Applies the branch filter to the QuerySet ONLY if IS_DEMO is True.
    """

    @wraps(func)
    def wrapper(self, qs, *args, **kwargs):
        # 1. Execute logic ONLY when IS_DEMO is True
        if getattr(settings, "IS_DEMO", False):
            bfq = getattr(self, "branch_filter_q", None)
            print("[Filtering] Fetched branch_filter_q.", bfq)

            if bfq:
                print("[Filtering] Checking for any filter added into this by the decorator and execute it.")
                return qs.filter(bfq)

        return qs

    return wrapper


def hq_dashboard_branch_filter(method):
    """
    Method decorator for HQDashboardView.get_context_data that adds
    branch/agent filtering to loan counts only when settings.IS_DEMO is True.

    When IS_DEMO is False or this decorator is removed, the base
    get_context_data works with unfiltered (global) counts.

    The decorator intercepts the context after the base method runs,
    and replaces the `hq_approved_count` and `pending_loan_count` values
    with versions scoped to the logged-in user's created branches and agents.

    Usage:
        from demo.hq.decorators import hq_dashboard_branch_filter

        class HQDashboardView(LoginRequiredMixin, TemplateView):
            template_name = 'hq/dashboard.html'

            @hq_dashboard_branch_filter
            def get_context_data(self, **kwargs):
                context = super().get_context_data(**kwargs)
                ...
                context['hq_approved_count'] = LoanApplication.objects.filter(status='hq_approved').count()
                context['pending_loan_count'] = LoanApplication.objects.filter(status='branch_approved').count()
                return context

    If the decorator is removed, the base counts (unfiltered) are used as-is.
    If IS_DEMO is False, the decorator is a no-op and passes through unchanged.
    """

    @wraps(method)
    def wrapper(self, **kwargs):
        context = method(self, **kwargs)

        if not settings.IS_DEMO:
            return context

        from headquater.models import Branch
        from agent.models import Agent
        from loan.models import LoanApplication
        from django.db.models import Q

        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list("branch_id", flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)

        # Override the counts with branch/agent filtered versions
        context["hq_approved_count"] = LoanApplication.objects.filter(status="hq_approved").filter(Q(branch__in=user_branches) | Q(agent__in=user_agents)).count()
        context["pending_loan_count"] = LoanApplication.objects.filter(status="branch_approved").filter(Q(branch__in=user_branches) | Q(agent__in=user_agents)).count()

        return context

    return wrapper


def hq_branch_context_filter(queryset_fields_name):
    """
    Method decorator factory for HQ class-based view methods.
    """

    def decorator(method):
        def update_context(self, context, queryset_field_name):
            if queryset_field_name == "branches":
                print('[Decorator] Updating "branches" context.')
                context["branches"] = self.user_branches.order_by("branch_name")
            if queryset_field_name == "agents":
                print('[Decorator] Updating "agents" context.')
                context["agents"] = self.user_agents.select_related("branch").order_by("full_name")

        @wraps(method)
        def wrapper(self, *args, **kwargs):
            if settings.IS_DEMO:
                from headquater.models import Branch
                from agent.models import Agent
                from django.db.models import Q

                # Get branches and agents created by the logged-in HQ user
                user_branches = Branch.objects.filter(created_by=self.request.user)
                user_branch_ids = user_branches.values_list("branch_id", flat=True)
                user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)

                # Setting self data
                self.branch_filter_q = Q(branch__in=user_branches) | Q(agent__in=user_agents)
                self.user_branches = user_branches
                self.user_branch_ids = user_branch_ids
                self.user_agents = user_agents

                print("[Decorator] Adding self.branch_filter_q", self.branch_filter_q)

            method(self, *args, **kwargs)
            context = method(self, **kwargs)

            print("[Decorator] Fetched context.", context)

            if not settings.IS_DEMO:
                print("[Decorator] Not Demo.")
                return context

            # Update context dictionary elements
            if isinstance(queryset_fields_name, str):
                update_context(self, context, queryset_fields_name)

            elif isinstance(queryset_fields_name, (set, list, tuple)):
                for field_name in queryset_fields_name:
                    update_context(self, context, field_name)

            return context

        return wrapper

    return decorator


def hq_method_setup(method):
    """
    Method decorator for HQ class-based view methods like `get()`, `post()`, etc.
    that return HttpResponse (not a context dict).

    Sets up `self.branch_filter_q`, `self.user_branches`, `self.user_branch_ids`,
    and `self.user_agents` on view instances when settings.IS_DEMO is True.

    Unlike `hq_branch_context_filter`, this decorator:
    - Works with any method signature (get, post, etc.)
    - Does NOT expect or modify a dict return value
    - Calls the original method only ONCE (no double-call bug)
    - Passes through all args and kwargs unchanged
    - Returns the original HttpResponse/object unmodified

    Usage:
        from demo.hq.decorators import hq_method_setup

        class HQHomeView(TemplateView):
            @hq_method_setup
            def get(self, request, *args, **kwargs):
                if request.user.is_authenticated:
                    return redirect('hq:dashboard')
                return redirect('hq:login')

        After decorator, inside the method you can use:
            self.branch_filter_q   -> Q object for branch/agent filtering
            self.user_branches     -> QuerySet of user's branches
            self.user_branch_ids   -> list of branch IDs
            self.user_agents       -> QuerySet of user's agents

    If IS_DEMO is False, the decorator is a no-op and passes through unchanged.
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if settings.IS_DEMO:
            from headquater.models import Branch
            from agent.models import Agent
            from django.db.models import Q

            # Get branches and agents created by the logged-in HQ user
            user_branches = Branch.objects.filter(created_by=self.request.user)
            user_branch_ids = user_branches.values_list("branch_id", flat=True)
            user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)

            # Setting self data
            self.branch_filter_q = Q(created_by=self.request.user) | Q(fund_transfers__branch_transaction__branch__in=user_branches)
            self.user_branches = user_branches
            self.user_branch_ids = user_branch_ids
            self.user_agents = user_agents

        # Call original method ONCE and return its result unmodified
        return method(self, *args, **kwargs)

    return wrapper