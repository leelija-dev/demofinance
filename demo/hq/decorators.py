from django.conf import settings


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

    def get_branch_filter(self, field='branch__created_by'):
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

    cls.get_branch_filter = get_branch_filter
    return cls