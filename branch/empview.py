from django.shortcuts import render, redirect, get_object_or_404
from .models import BranchRole, BranchPermission, BranchEmployee
from django.contrib.auth.decorators import login_required
from branch.decorators import branch_permission_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.contrib import messages
from .forms import BranchEmployeeForm, BranchRoleForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from loan.models import (
    LoanApplication,
    EmiCollectionDetail,
    DocumentRequest,
    DocumentReview,
    EmiAgentAssign,
    LoanRescheduleLog,
    LoanCloseRequest,
)


# Create your views here.
@branch_permission_required('view_branch_employee')
def employee_list(request):
    loggedin_branch = request.session.get('logged_user_branch_id')
    status = (request.GET.get('status') or 'active').strip().lower()

    employees_qs = BranchEmployee.objects.filter(branch_id=loggedin_branch)
    if status == 'active':
        employees_qs = employees_qs.filter(is_active=True)
    elif status in ['inactive', 'deactive', 'deactivated']:
        employees_qs = employees_qs.filter(is_active=False)
    else:
        status = 'all'

    employees = employees_qs.order_by('-is_active', 'first_name', 'last_name')
    return render(request, 'rbac/employee_list.html', {'employees': employees, 'status_filter': status})


@branch_permission_required('add_branch_employee')
def employee_create(request):
    # Get the logged-in user's branch
    loggedin_branch_id = request.session.get('logged_user_branch_id')
    loggedin_user_id = request.session.get('logged_user_id')
    
    if not loggedin_branch_id or not loggedin_user_id:
        messages.error(request, 'User session information is missing. Please log in again.')
        return redirect('login')  # Replace with your login URL

    if request.method == 'POST':
        form = BranchEmployeeForm(request.POST)
        if form.is_valid():
            try:
                employee = form.save(commit=False)
                employee.branch_id = loggedin_branch_id
                employee.is_manager = False
                employee.created_by = loggedin_user_id
                employee.save()
                messages.success(request, 'Employee created successfully!')
                return redirect('branch:employee_list')
            except Exception as e:
                messages.error(request, f'Error creating employee: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BranchEmployeeForm(initial={'branch': loggedin_branch_id})
    
    # Filter roles to only show roles from the current branch
    form.fields['role'].queryset = BranchRole.objects.filter(branch_id=loggedin_branch_id)
    
    context = {
        'form': form,
        'title': 'Create New Employee'
    }
    return render(request, 'rbac/employee_form.html', context)


@branch_permission_required('change_branch_employee')
def employee_edit(request, employee_id):
    try:
        employee = BranchEmployee.objects.get(id=employee_id)
    except BranchEmployee.DoesNotExist:
        messages.error(request, 'Employee not found')
        return redirect('branch:employee_list')

    if request.method == 'POST':
        form = BranchEmployeeForm(request.POST, instance=employee, is_edit=True)
        if form.is_valid():
            # Only update password if it was provided
            if not form.cleaned_data.get('password'):
                # Remove the password from the form data to prevent clearing the existing password
                employee = form.save(commit=False)
                employee.save()
                form.save_m2m()  # Save many-to-many relations if any
            else:
                form.save()
            messages.success(request, 'Employee updated successfully')
            return redirect('branch:employee_list')
    else:
        form = BranchEmployeeForm(instance=employee, is_edit=True)
    
    context = {
        'form': form,
        'employee': employee,
        'title': 'Edit Employee'
    }
    return render(request, 'rbac/employee_form.html', context)


@branch_permission_required('view_branch_employee')
def employee_detail(request):
    return render(request, 'rbac/employee_detail.html')


@branch_permission_required('view_branch_employee')
def employee_deactivate_info(request, employee_id):
    loggedin_branch_id = request.session.get('logged_user_branch_id')
    employee = get_object_or_404(BranchEmployee, id=employee_id, branch_id=loggedin_branch_id)

    data = {
        'employee': {
            'id': employee.id,
            'employee_id': employee.employee_id,
            'name': employee.get_full_name(),
            'email': employee.email,
            'is_active': employee.is_active,
            'is_manager': employee.is_manager,
            'role': employee.role.name if employee.role else None,
        },
        'activity': {
            'applications_created': LoanApplication.objects.filter(created_by_branch_manager=employee).count(),
            'emi_collections': EmiCollectionDetail.objects.filter(collected_by_branch=employee).count(),
            'emi_verified': EmiCollectionDetail.objects.filter(verified_by=employee).count(),
            'document_requests': DocumentRequest.objects.filter(requested_by=employee).count(),
            'document_reviews': DocumentReview.objects.filter(reviewed_by=employee).count(),
            'emi_assignments': EmiAgentAssign.objects.filter(assigned_by=employee).count(),
            'loan_reschedules': LoanRescheduleLog.objects.filter(created_by=employee).count(),
            'loan_close_requests': LoanCloseRequest.objects.filter(requested_by=employee).count(),
        },
    }

    return JsonResponse(data)


@require_POST
@branch_permission_required('view_branch_employee')
def employee_deactive(request, employee_id):
    loggedin_branch_id = request.session.get('logged_user_branch_id')
    loggedin_user_id = request.session.get('logged_user_id')
    employee = get_object_or_404(BranchEmployee, id=employee_id, branch_id=loggedin_branch_id)

    employee.is_active = False
    employee.updated_by = loggedin_user_id
    employee.save(update_fields=['is_active', 'updated_by', 'updated_at'])
    messages.success(request, 'Employee deactivated successfully')
    return redirect('branch:employee_list')


@require_POST
@branch_permission_required('view_branch_employee')
def employee_active(request, employee_id):
    loggedin_branch_id = request.session.get('logged_user_branch_id')
    loggedin_user_id = request.session.get('logged_user_id')
    employee = get_object_or_404(BranchEmployee, id=employee_id, branch_id=loggedin_branch_id)

    employee.is_active = True
    employee.updated_by = loggedin_user_id
    employee.save(update_fields=['is_active', 'updated_by', 'updated_at'])
    messages.success(request, 'Employee activated successfully')
    return redirect('branch:employee_list')