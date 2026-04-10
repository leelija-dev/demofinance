from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.db.models import Sum, Max, Exists, OuterRef, Subquery

from branch.decorators import branch_permission_required
from agent.models import Agent
from loan.models import CustomerDetail, LoanApplication, LoanCloseRequest
from savings.models import SavingsAccountApplication


@branch_permission_required('view_customers')
def customer_list(request):
    loggedin_branch_id = request.session.get('logged_user_branch_id')

    qs = CustomerDetail.objects.all()
    if loggedin_branch_id:
        qs = qs.filter(branch_id=loggedin_branch_id)

    agents_qs = Agent.objects.all()
    if loggedin_branch_id:
        agents_qs = agents_qs.filter(branch_id=loggedin_branch_id)
    agents = agents_qs.order_by('full_name')

    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(customer_id__icontains=q)
            | Q(full_name__icontains=q)
            | Q(contact__icontains=q)
            | Q(adhar_number__icontains=q)
            | Q(pan_number__icontains=q)
        )

    agent_id = (request.GET.get('agent') or '').strip()
    if agent_id:
        qs = qs.filter(agent_id=agent_id)

    loan_filter = (request.GET.get('loan') or '').strip().lower()
    savings_filter = (request.GET.get('savings') or '').strip().lower()
    savings_type_choices = list(getattr(SavingsAccountApplication, 'PRODUCT_TYPES', []))

    requires_distinct = False
    if loan_filter in {'daily', 'weekly', 'monthly'}:
        requires_distinct = True
        qs = qs.filter(
            Q(loan_applications__emi_schedules__frequency=loan_filter)
            | Q(loan_applications__emi_reschedules__frequency=loan_filter)
        )

    if savings_filter:
        requires_distinct = True
        qs = qs.filter(savings_applications__product_type=savings_filter)

    if requires_distinct:
        qs = qs.distinct()

    customers = qs.order_by('-submitted_at')
    paginator = Paginator(customers, 10)
    customers_page = paginator.get_page(request.GET.get('page') or 1)
    try:
        page_links = list(
            paginator.get_elided_page_range(customers_page.number, on_each_side=2, on_ends=1)
        )
    except Exception:
        page_links = list(paginator.page_range)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    return render(
        request,
        'customer/customer_list.html',
        {
            'customers_page': customers_page,
            'page_links': page_links,
            'query_string': query_string,
            'q': q,
            'agents': agents,
            'selected_agent': agent_id,
            'loan_filter': loan_filter,
            'savings_filter': savings_filter,
            'savings_type_choices': savings_type_choices,
        },
    )


@branch_permission_required('view_customers')
def customer_detail(request, customer_id):
    loggedin_branch_id = request.session.get('logged_user_branch_id')

    customer = get_object_or_404(
        CustomerDetail.objects.select_related('address', 'account'),
        customer_id=customer_id,
        branch_id=loggedin_branch_id,
    )

    loan_applications = (
        LoanApplication.objects
        .filter(customer=customer)
        .annotate(
            loan_amount=Max('loan_details__loan_amount'),
            emi_amount=Max('loan_details__emi_amount'),
            disbursed_total=Sum('disbursement_logs__amount'),
            has_approved_close_request=Exists(
                LoanCloseRequest.objects.filter(
                    loan_application=OuterRef('pk'),
                    status='approved',
                )
            ),
            close_approved_at=Subquery(
                LoanCloseRequest.objects.filter(
                    loan_application=OuterRef('pk'),
                    status='approved',
                )
                .order_by('-approved_at', '-updated_at')
                .values('approved_at')[:1]
            ),
        )
        .select_related('branch', 'agent')
        .order_by('-submitted_at')
    )

    savings_accounts = (
        SavingsAccountApplication.objects
        .filter(customer=customer)
        .select_related('branch', 'agent')
        .order_by('-submitted_at')
    )

    return render(
        request,
        'customer/customer_detail.html',
        {
            'customer': customer,
            'loan_applications': loan_applications,
            'savings_accounts': savings_accounts,
        },
    )
