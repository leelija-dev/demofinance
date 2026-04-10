from django.db import models
from django.contrib.auth.models import AbstractUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import os
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver

# from branch.models import BranchTransaction

class Role(models.Model):
    ROLE_TYPES = [
        ('super_admin', 'Super Admin'),
        ('finance_manager', 'Finance Manager'),
        ('operations_manager', 'Operations Manager'),
        ('compliance_officer', 'Compliance Officer'),
        ('data_analyst', 'Data Analyst'),
        ('customer_support_lead', 'Customer Support Lead'),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    role_type = models.CharField(max_length=50, choices=ROLE_TYPES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

     # Add this line to create the many-to-many relationship
    permissions = models.ManyToManyField(
        Permission,
        verbose_name='permissions',
        blank=True,
        related_name='role_permissions'  # This allows permission.role_permissions.all() to get all roles with this permission
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def is_super_admin(self, employee):
        return employee.role and employee.role.role_type == 'super_admin'

    def can_access_user_management(self, employee):
        return employee.role and employee.role.role_type in ['super_admin', 'operations_manager']

    def can_access_role_management(self, employee):
        return employee.role and employee.role.role_type in ['super_admin', 'operations_manager']

    def can_create_users(self, employee):
        return employee.role and employee.role.role_type in ['super_admin', 'operations_manager']

    def can_edit_users(self, employee):
        return employee.role and employee.role.role_type in ['super_admin', 'operations_manager']

    def can_delete_users(self, employee):
        return employee.role and employee.role.role_type == 'super_admin'

    def get_role_type(self, employee):
        return employee.role.role_type if employee.role else None

class HeadquarterEmployee(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    image = models.ImageField(
        upload_to='hq/employee/profile/',
        null=True,
        blank=True,
        help_text='Profile Image of Headquater Employee',
        storage=FileSystemStorage(location=os.path.join(settings.BASE_DIR, 'media'))
    )

    address = models.TextField(blank=True, null=True)
    is_headquater_admin = models.BooleanField(default=False)
    role = models.ForeignKey(
        'Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headquarter_employees'
    )
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name='headquarter_employees',
        related_query_name='headquarter_employee'
    )
    
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='headquarter_employees',
        related_query_name='headquarter_employee'
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'Headquarter Employee'
        verbose_name_plural = 'Headquarter Employees'

    def __str__(self):
        return self.username

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name

    def has_perm(self, perm, obj=None):
        if self.is_active and self.is_headquater_admin:
            return True
        # First check if user is active and has the permission through their role
        if self.is_active and self.role:
            try:
                # Check if the permission exists in the role's permissions
                app_label, codename = perm.split('.', 1)
                return self.role.permissions.filter(
                    content_type__app_label=app_label,
                    codename=codename
                ).exists()
            except ValueError:
                # Handle case where perm doesn't contain a dot
                return False
        return False

    def has_module_perms(self, app_label):
        # return self.is_active and self.is_headquater_admin
        
        # Super admin has all module permissions
        if self.is_active and self.is_headquater_admin:
            return True
            
        # Check role-based module permissions
        if self.is_active and self.role:
            return self.role.permissions.filter(
                content_type__app_label=app_label
            ).exists()
        return False

    def get_role_name(self):
        return self.role.name if self.role else 'No Role'

    def get_role_type(self):
        return self.role.role_type if self.role else None

    def can_access_user_management(self):
        return self.role and self.role.can_access_user_management(self)

    def can_access_role_management(self):
        return self.role and self.role.can_access_role_management(self)

    def can_create_users(self):
        return self.role and self.role.can_create_users(self)

    def can_edit_users(self):
        return self.role and self.role.can_edit_users(self)

    def can_delete_users(self):
        return self.role and self.role.can_delete_users(self)

class Branch(models.Model):
    branch_id = models.AutoField(primary_key=True)
    branch_name = models.CharField(max_length=255, unique=True)
    address_line_1 = models.CharField(max_length=255, default='')
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, default='')
    state = models.CharField(max_length=100, default='')
    postal_code = models.CharField(max_length=6, default='')
    country = models.CharField(max_length=100, default='')
    district = models.CharField(max_length=100, default='')
    contact_number = models.CharField(max_length=10, blank=True, null=True, unique=True)
    email = models.EmailField(unique=True)
    manager_id = models.CharField(max_length=100, blank=True, null=True)  # You may want to use a ForeignKey to Headquarters or User if needed
    status = models.BooleanField(default=True)
    # wallet_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    wallet_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='branches_created')

    def __str__(self):
        return self.branch_name

    class Meta:
        verbose_name = 'Branch'
        verbose_name_plural = 'Branches'


# Auto-create a CASH HQ wallet when a superuser or HQ admin account is created
@receiver(post_save, sender=HeadquarterEmployee)
def ensure_hq_cash_wallet_on_superuser_create(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.is_superuser or getattr(instance, 'is_headquater_admin', False):
        HeadquartersWallet.objects.get_or_create(
            type='CASH',
            defaults={'name': 'Cash', 'balance': 0.00}
        )


class HeadquartersWallet(models.Model):
    def generate_wallet_id():
        return f"HQW-{str(uuid.uuid4())[:8].upper()}"

    wallet_id = models.CharField(primary_key=True, max_length=12, default=generate_wallet_id, editable=False)
    type = models.CharField(max_length=10, choices=[
        ('CASH', 'Cash'),
        ('BANK', 'Bank')
    ], default='CASH', null=False)
    name = models.CharField(max_length=255, null=True)
    bank_name = models.CharField(max_length=255, null=True)
    account_number = models.CharField(max_length=255, null=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, null=False)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.wallet_id} - Balance: {self.balance}"

    class Meta:
        verbose_name = 'Headquarters Wallet'
        verbose_name_plural = 'Headquarters Wallets'


class HeadquartersTransactions(models.Model):
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('adjustment', 'Adjustment'),
    ]
    
    def generate_transaction_id():
        return f"HQT-{str(uuid.uuid4())[:8].upper()}"
    
    transaction_id = models.CharField(primary_key=True, max_length=12, default=generate_transaction_id, editable=False)
    wallet = models.ForeignKey(HeadquartersWallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    purpose = models.CharField(
        max_length=255, 
        blank=True,
        null=True,
        help_text='Purpose of the transaction (from Chart of Accounts)'
    )

    code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text='Account code from Chart of Accounts'
    )
    proof_document = models.FileField(
        upload_to='hq/transaction_proof/',
        null=True,
        blank=True,
        help_text='Upload proof document for this transaction (e.g., bank receipt, UPI screenshot)',
        storage=FileSystemStorage(location=os.path.join(settings.BASE_DIR, 'static'))
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Reference number for the transaction (e.g., UTR, Cheque number)'
    )
    transaction_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='hq_transactions_created')

    def __str__(self):
        return f"{self.transaction_id} - {self.transaction_type} - {self.amount}"

    class Meta:
        verbose_name = 'Headquarters Transaction'
        verbose_name_plural = 'Headquarters Transactions'
        ordering = ['-transaction_date']



class FundTransfers(models.Model):
    def generate_transfer_id():
        return f"TRAN-{str(uuid.uuid4())[:8].upper()}"

    transfer_id = models.CharField(
        primary_key=True,
        max_length=13,
        default=generate_transfer_id,
        editable=False
    )
    hq_transaction = models.ForeignKey(
        HeadquartersTransactions,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fund_transfers'
    )
    branch_transaction = models.ForeignKey(
        'branch.BranchTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fund_transfers'
    )
    # Optional destination BranchAccount for HQ→Branch transfers (BANK or CASH)
    branch_account = models.ForeignKey(
        'branch.BranchAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fund_transfers',
        help_text='Destination BranchAccount when applicable (e.g., HQ→Branch cash/bank transfers)'
    )
    created_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Stores the transaction_id (HQ or Branch) that initiated the transfer."
    )
    transfer_to = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text=(
            "Destination identifier: store Branch.branch_id when HQ→Branch, or the Headquarters ID when Branch→HQ."
        ),
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    transfer_date = models.DateTimeField(auto_now_add=True)
    # Optional mode and bank method for richer audit trails
    payment_mode = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )
    bank_method = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )
    purpose = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.created_by:
            if self.hq_transaction:
                self.created_by = self.hq_transaction.transaction_id
            elif self.branch_transaction:
                self.created_by = self.branch_transaction.transaction_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transfer_id} - {self.amount}"

    class Meta:
        verbose_name = 'Fund Transfer'
        verbose_name_plural = 'Fund Transfers'
        ordering = ['-transfer_date']