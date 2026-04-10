import uuid
from django.db import models
from django.conf import settings

from agent.models import Agent
from loan.models import LoanApplication, Shop
# from headquater.models import Branch

# Create your models here.


class BranchPermission(models.Model):
    """
    Model representing custom permissions for branch operations.
    These are separate from Django's built-in permissions.
    """
    # Core fields
    name = models.CharField(max_length=100)
    codename = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Group field with choices
    group = models.CharField(
        max_length=50,
        choices=[
            ('branch', 'Branch Operations'),
            ('role', 'Role Management'),
            ('staff', 'Staff Management'),
            ('agent', 'Agent Management'),
            ('loan', 'Loan Management'),
            ('emi', 'EMI Management'),
            ('customer', 'Customer Management'),
            ('payment', 'Payment Processing'),
            ('report', 'Reports'),
        ],
        default='branch'
    )
    
    class Meta:
        db_table = 'branch_permissions'
        verbose_name = 'Branch Permission'
        verbose_name_plural = 'Branch Permissions'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.codename})"

    ##########################################################################################
    # Branch Permission Decorator Usage Example 
    ##########################################################################################

    # @branch_permission_required('view_agent')
    # def my_view(request):
    #     # Your view code here
    #     pass

    # # Or in templates
    # {% if user.has_perm('view_agent') %}
    #     <!-- Show agent-related content -->
    # {% endif %}


class BranchRole(models.Model):
    """
    Model representing different roles for branch employees with branch-specific permissions.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    permissions = models.ManyToManyField(
        'BranchPermission',
        related_name='branch_roles',
        blank=True,
        verbose_name='branch permissions'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    branch = models.ForeignKey(
        'headquater.Branch', 
        on_delete=models.CASCADE, 
        related_name='branch_roles',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'branch_roles'
        ordering = ['name']
        verbose_name = 'Branch Role'
        verbose_name_plural = 'Branch Roles'
        unique_together = ('name', 'branch')

    def __str__(self):
        branch_name = self.branch.branch_name if self.branch else 'Global'
        return f"{self.name} ({branch_name})"

    def has_permission(self, codename):
        """Check if this role has the specified permission."""
        return self.permissions.filter(codename=codename).exists()

    def get_all_permissions(self):
        """Get all permissions for this role."""
        return self.permissions.all()

class BranchEmployee(models.Model):
    """Model representing all branch staff including managers and regular employees."""
    employee_id = models.CharField(max_length=100, unique=True, editable=True)
    branch = models.ForeignKey('headquater.Branch', on_delete=models.CASCADE, related_name='employees')
    role = models.ForeignKey(
        BranchRole, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='employees'
    )
    is_manager = models.BooleanField(default=False, verbose_name='Is Manager')
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='branch/profile/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    date_of_joining = models.DateField(auto_now_add=True)
    gender = models.CharField(
        max_length=10,
        choices=[
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other')
        ],
        default='male'
    )
    password = models.CharField(max_length=128)  # Store hashed password
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    is_verified = models.BooleanField(default=False, verbose_name='Is Verified')
    gov_id_type = models.CharField(
        max_length=50,
        choices=[
            ('aadhar', 'Aadhar Card'),
            ('pan', 'PAN Card'),
            ('passport', 'Passport'),
            ('driving_license', 'Driving License'),
            ('voter_id', 'Voter ID'),
            ('other', 'Other')
        ],
        default='aadhar'
    )
    gov_id_number = models.CharField(max_length=100, unique=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True, null=True)
    emergency_contact_number = models.CharField(max_length=15, blank=True, null=True)
    emergency_contact_relation = models.CharField(max_length=100, blank=True, null=True)
    
    # Manager-specific fields (nullable for regular employees)
    manager_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.IntegerField(null=True, blank=True)
    updated_by = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.employee_id} - {self.get_full_name()}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        if not self.pk:  # Only for new instances
            # Get the highest employee_id for this branch
            last_employee = BranchEmployee.objects.all().order_by('-employee_id').first()
            
            if last_employee:
                try:
                    new_number = int(last_employee.employee_id) + 1
                except (ValueError, TypeError):
                    new_number = 1
            else:
                new_number = 1

            self.employee_id = str(new_number).zfill(4)
        
        # Handle manager ID if needed
        if (not self.pk or not self.manager_id) and self.is_manager:
            last_manager = BranchEmployee.objects.filter(
                manager_id__isnull=False
            ).order_by('-id').first()
            
            if last_manager:
                try:
                    last_num = int(last_manager.manager_id[2:]) if last_manager.manager_id.startswith('M-') else 0
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            self.manager_id = f"M-{str(new_num).zfill(4)}"
        
        super().save(*args, **kwargs)

    def has_branch_permission(self, codename):
        """Check if the employee has the specified branch permission.
        Managers automatically have all permissions. For others, check their role.
        """
        if self.is_manager:
            return True
        if not self.role:
            return False
        return self.role.has_permission(codename)
    
    def get_branch_permissions(self):
        """Get all branch permissions for this employee."""
        if not self.role:
            return BranchPermission.objects.none()
        return self.role.get_all_permissions()

    # def has_perm(self, perm_codename):
    #     """
    #     Check if the employee has the specified permission through their role.
    #     """
    #     # Check role permissions
    #     if hasattr(self, 'role') and self.role:
    #         return self.role.permissions.filter(codename=perm_codename).exists()

    def has_perm(self, perm_codename):
        """
        Check if the employee has the specified permission through their role.
        """
        # Check if employee has a role
        if hasattr(self, 'role') and self.role:
            
            # Get all permissions for the role
            # role_permissions = list(self.role.permissions.values_list('codename', flat=True))
            # print(f"Role permissions: {role_permissions}")
            
            # Check if the permission exists
            has_perm = self.role.permissions.filter(codename=perm_codename).exists()
            # print(f"Has permission '{perm_codename}': {has_perm}")
            
            return has_perm
        else:
            print("Employee has no role assigned")
            
        return False

    class Meta:
        db_table = 'branch_employees'
        ordering = ['-created_at']
        verbose_name = 'Branch Employee'
        verbose_name_plural = 'Branch Employees'
        indexes = [
            models.Index(fields=['is_manager']),
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
        ]


class BranchTransaction(models.Model):
    transaction_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    branch = models.ForeignKey('headquater.Branch', on_delete=models.CASCADE, related_name='transactions')
    branch_account = models.ForeignKey('branch.BranchAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    disbursement_log = models.ForeignKey('loan.DisbursementLog', on_delete=models.SET_NULL, null=True, blank=True, related_name='branch_transactions')
    transaction_type = models.CharField(max_length=10, choices=[
        ('CREDIT', 'Credit'),
        ('DEBIT', 'Debit')
    ], null=False)
    purpose = models.CharField(max_length=255, null=False)
    code = models.CharField(max_length=20, null=True, blank=True)
    mode = models.CharField(max_length=20, null=True, blank=True)
    bank_payment_method = models.CharField(max_length=20, null=True, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=False)
    transfer_to_from = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    transaction_date = models.DateTimeField(auto_now_add=True, null=False)
    loan_application = models.ForeignKey(LoanApplication, on_delete=models.CASCADE, null=True, blank=True, related_name='branch_transactions')
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, related_name='branch_transactions')
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True, related_name='branch_transactions')
    created_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.CASCADE, related_name='transactions_created', null=True, blank=True)


    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.branch} - {self.transaction_type} - {self.amount}"

    class Meta:
        db_table = 'branch_transactions'
        ordering = ['-transaction_date']
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.transaction_id = f"BTID-{short_uuid}"
        super().save(*args, **kwargs)


class BranchAccount(models.Model):
    id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    branch = models.ForeignKey('headquater.Branch', on_delete=models.CASCADE, related_name='accounts')
    type = models.CharField(max_length=10, choices=[
        ('CASH', 'Cash'),
        ('BANK', 'Bank')
    ], null=False)
    name = models.CharField(max_length=255, null=False)
    bank_name = models.CharField(max_length=255, null=False)
    account_number = models.CharField(max_length=255, null=False)
    # transaction_id = models.CharField(max_length=50, editable=False, unique=True)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.CASCADE, related_name='funds_created')
    updated_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.CASCADE, related_name='funds_updated')

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"

    class Meta:
        db_table = 'branch_accounts'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.id = f"BFID-{short_uuid}"
        super().save(*args, **kwargs)


# Cash deposited by Agent to Branch office 
class AgentDeposit(models.Model):
    deposit_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)

    # Who/where/when
    agent = models.ForeignKey('agent.Agent', on_delete=models.PROTECT, related_name='deposits')
    branch = models.ForeignKey('headquater.Branch', on_delete=models.PROTECT, related_name='agent_deposits')
    received_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.PROTECT, related_name='deposits_received')
    received_at = models.DateTimeField(auto_now_add=True)

    # Amounts (all Decimal(12,2))
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2)   # sum of denomination line_totals
    coin_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cash_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    online_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)       # subtotal + online
    expected_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # from API: today’s agent collections
    mismatch = models.BooleanField(default=False)  # true if grand_total != expected_total and online_amount == 0

    # Categories (from EMI frequency)
    daily_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    weekly_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saving_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    others_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Lifecycle
    STATUS_CHOICES = [('pending','Pending'), ('verified','Verified'), ('rejected','Rejected')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    remarks = models.TextField(blank=True, null=True)

    # Audit
    created_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.SET_NULL, null=True, related_name='agent_deposits_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.deposit_id:
            import uuid
            self.deposit_id = f"DEP-{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)


class AgentDepositDenomination(models.Model):
    deposit = models.ForeignKey('AgentDeposit', on_delete=models.CASCADE, related_name='denominations')
    value = models.PositiveIntegerField()     # e.g., 2000, 500, 100...
    qty = models.PositiveIntegerField()       # integer only
    line_total = models.DecimalField(max_digits=12, decimal_places=2)  # value * qty
    coin = models.PositiveIntegerField(default=0)  # integer only, clamped to <= line_total
    cash = models.PositiveIntegerField(default=0)  # line_total - coin (integer)

    class Meta:
        indexes = [models.Index(fields=['deposit'])]