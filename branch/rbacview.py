from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from .models import BranchRole, BranchPermission
from django.contrib.auth.decorators import login_required
from branch.decorators import branch_permission_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.contrib import messages
from .forms import BranchRoleForm

# Create your views here.

# @login_required
@branch_permission_required('view_branch_role')
def role_list(request):
    """
    View to list all roles in the RBAC system.
    If branch_id is in session, shows only roles for that branch without pagination.
    Otherwise, shows all roles with pagination and filters.
    """
    # Get branch_id from session
    branch_id = request.session.get('logged_user_branch_id')

    # Get all available permissions for the filter (needed in both views)
    all_permissions = BranchPermission.objects.all().order_by('name')
    
    # Base query
    if branch_id:
        # If branch_id is in session, filter roles by that branch only
        roles = BranchRole.objects.filter(
            branch_id=branch_id
        ).select_related('branch').prefetch_related('permissions').order_by('name')
        
        context = {
            'roles': roles,
            'all_permissions': all_permissions,
        }
        
        print(roles)

        return render(request, 'rbac/role_list.html', context)
        
    else:
        # For global admin view, get all roles
        roles = BranchRole.objects.select_related('branch').prefetch_related('permissions').order_by('name')
        
        # Apply search query
        search_query = request.GET.get('search', '')
        if search_query:
            roles = roles.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(branch__name__icontains=search_query)
            )
        
        # Apply permission filter
        permission_filter = request.GET.get('permission')
        if permission_filter:
            roles = roles.filter(permissions__id=permission_filter).distinct()
        
        # Apply branch filter
        branch_filter = request.GET.get('branch')
        if branch_filter:
            roles = roles.filter(branch__id=branch_filter)
        
        # Enable pagination for global view
        pagination_enabled = True
        page = request.GET.get('page', 1)
        paginator = Paginator(roles, 20)  # Show 20 roles per page
        
        try:
            roles = paginator.page(page)
        except PageNotAnInteger:
            roles = paginator.page(1)
        except EmptyPage:
            roles = paginator.page(paginator.num_pages)
    
    context = {
        'roles': roles,
        'all_permissions': all_permissions,
        'search_query': request.GET.get('search', ''),
        'selected_permission': request.GET.get('permission'),
        'selected_branch': request.GET.get('branch'),
        'pagination_enabled': pagination_enabled,
    }
    
    print(roles)
    
    return render(request, 'rbac/role_list.html', context)

@branch_permission_required('add_branch_role')
def role_create(request):
    if request.method == 'POST':
        form = BranchRoleForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    role = form.save(commit=False)
                    # Set branch_id from session if available
                    branch_id = request.session.get('logged_user_branch_id')
                    if branch_id:
                        role.branch_id = branch_id
                    
                    # Save the role first
                    role.save()
                    
                    # Save the many-to-many relationships
                    form.save_m2m()
                    
                    # Verify the branch assignment
                    if branch_id and str(role.branch_id) != str(branch_id):
                        raise ValueError("Branch ID mismatch in role creation")
                    
                    # Verify permissions were saved
                    permission_ids = request.POST.getlist('permissions', [])
                    saved_permission_ids = list(role.permissions.values_list('id', flat=True))
                    
                    if set(map(str, permission_ids)) != set(map(str, saved_permission_ids)):
                        raise ValueError("Mismatch between requested and saved permissions")
                    
                    messages.success(request, f'Role "{role.name}" has been created successfully.')
                    return redirect('branch:role_list')
                    
            except Exception as e:
                print("ERROR:", str(e))
                messages.error(request, f'An error occurred while saving the role: {str(e)}')
        else:
            # Log form errors for debugging
            print("Form errors:", form.errors)
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BranchRoleForm()
    
    # Get the choices from the group field
    group_choices = dict(BranchPermission._meta.get_field('group').choices)
    
    # Group permissions by their group
    permissions = BranchPermission.objects.all().order_by('group')
    permission_groups = {}
    for perm in permissions:
        if perm.group not in permission_groups:
            permission_groups[perm.group] = []
        permission_groups[perm.group].append(perm)
    
    # Convert to list of tuples (group_name, permissions) for template
    permission_groups = [
        (group_choices.get(group, group), perms)
        for group, perms in permission_groups.items()
    ]
    
    # Sort by group name
    permission_groups.sort(key=lambda x: x[0])
    
    context = {
        'title': 'Create New Role',
        'form': form,
        'permission_groups': permission_groups,
    }
    
    return render(request, 'rbac/role_form.html', context)


@branch_permission_required('change_branch_role')
def role_edit(request, role_id):
    try:
        # Get the role or return 404 if not found
        role = get_object_or_404(BranchRole, id=role_id)
        
        # Check branch permission if user is from a specific branch
        branch_id = request.session.get('logged_user_branch_id')
        if branch_id and str(role.branch_id) != str(branch_id):
            messages.error(request, "You don't have permission to edit this role.")
            return redirect('branch:role_list')

        if request.method == 'POST':
            form = BranchRoleForm(request.POST, instance=role)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        updated_role = form.save(commit=False)
                        
                        # Ensure branch remains the same for branch-specific roles
                        if branch_id:
                            updated_role.branch_id = branch_id
                            
                        updated_role.save()
                        form.save_m2m()  # Save many-to-many relationships
                        
                        # Verify permissions were saved
                        permission_ids = request.POST.getlist('permissions', [])
                        saved_permission_ids = list(updated_role.permissions.values_list('id', flat=True))
                        
                        if set(map(str, permission_ids)) != set(map(str, saved_permission_ids)):
                            raise ValueError("Mismatch between requested and saved permissions")
                        
                        messages.success(request, f'Role "{updated_role.name}" has been updated successfully.')
                        return redirect('branch:role_list')
                        
                except Exception as e:
                    print("ERROR:", str(e))
                    messages.error(request, f'An error occurred while updating the role: {str(e)}')
            else:
                print("Form errors:", form.errors)
                messages.error(request, 'Please correct the errors below.')
        else:
            # For GET request, initialize form with role instance
            form = BranchRoleForm(instance=role)
            
        # Get the choices from the group field
        group_choices = dict(BranchPermission._meta.get_field('group').choices)
        
        # Group permissions by their group
        permissions = BranchPermission.objects.all().order_by('group')
        permission_groups = {}
        for perm in permissions:
            if perm.group not in permission_groups:
                permission_groups[perm.group] = []
            permission_groups[perm.group].append(perm)
        
        # Convert to list of tuples (group_name, permissions) for template
        permission_groups = [
            (group_choices.get(group, group), perms)
            for group, perms in permission_groups.items()
        ]
        
        # Sort by group name
        permission_groups.sort(key=lambda x: x[0])
        
        context = {
            'title': f'Edit Role: {role.name}',
            'form': form,
            'role': role,
            'permission_groups': permission_groups,
            'is_edit': True,
        }
        
        return render(request, 'rbac/role_form.html', context)
        
    except Exception as e:
        print("Unexpected error in role_edit:", str(e))
        messages.error(request, 'An unexpected error occurred.')
        return redirect('branch:role_list')