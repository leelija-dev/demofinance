from django.db import models

import uuid

from django.utils import timezone
from datetime import timedelta

from agent.models import Agent
from headquater.models import Branch, HeadquarterEmployee
from branch.models import BranchEmployee
from loan.models import CustomerDetail
from django.db.models import Q


class SavingsAccountApplication(models.Model):
    PRODUCT_TYPES = [
        ('fd', 'Fixed Deposit'),
        ('rd', 'Recurring Deposit'),
    ]

    NOMINEE_KYC_TYPES = [
        ('aadhaar', 'Aadhaar'),
        ('pan', 'PAN'),
    ]

    SURRENDER_STATUS_CHOICES = [
        ('none', 'No Surrender'),
        ('requested', 'Requested'),
        ('processing', 'Processing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('success', 'Success'),
        ('reject', 'Rejected'),
        ('rejected_by_branch', 'Rejected by Branch'),
        ('inactive', 'Inactive'),
        ('document_requested', 'Document Requested by Branch'),
        ('resubmitted', 'Reuploaded - Pending branch approve'),
        ('branch_document_accepted', 'Branch Accepted Document'),
        ('branch_approved', 'Branch Approved - Pending HQ Approval'),
        ('branch_resubmitted', 'Reuploaded - Pending HQ review'),
        ('hq_document_accepted', 'HQ Accepted Document'),
        ('hq_resubmitted', 'HQ Requested Resubmission'),
        ('hq_approved', 'HQ Approved'),
        ('hq_rejected', 'HQ Rejected'),
        ('disbursed', 'Disbursed'),
        ('disbursed_fund_released', 'Disbursed - Fund Released'),
        ('document_requested_by_hq', 'Document Requested by HQ'),
    ]

    application_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    account_id = models.CharField(max_length=50, null=True, blank=True, unique=True)
    customer = models.ForeignKey(CustomerDetail, on_delete=models.CASCADE, related_name='savings_applications')
    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPES)
    product_id = models.CharField(max_length=50, null=True, blank=True)
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    rd_principal_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rd_interest_accrued = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rd_last_interest_date = models.DateField(null=True, blank=True)
    tenure = models.PositiveIntegerField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='pending')

    account_opened_at = models.DateTimeField(null=True, blank=True)
    hq_approved_at = models.DateTimeField(null=True, blank=True)
    hq_approved_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True, blank=True, related_name='hq_approved_savings_applications')

    withdraw_date = models.DateField(null=True, blank=True)
    withdraw_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    maturity_date = models.DateField(null=True, blank=True)
    maturity_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    surrender_status = models.CharField(max_length=20, choices=SURRENDER_STATUS_CHOICES, default='none', null=True, blank=True)
    surrender_note = models.TextField(null=True, blank=True)

    nominee_name = models.CharField(max_length=255, null=True, blank=True)
    nominee_relationship = models.CharField(max_length=100, null=True, blank=True)
    nominee_kyc_type = models.CharField(max_length=20, choices=NOMINEE_KYC_TYPES, null=True, blank=True)
    nominee_kyc_number = models.CharField(max_length=50, null=True, blank=True)
    nominee_kyc_document = models.FileField(upload_to='static/nominee/kyc/', null=True, blank=True)

    rejection_reason = models.TextField(null=True, blank=True)

    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, related_name='savings_applications')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='savings_applications')
    submitted_at = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.application_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.application_id = f"SAV-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application_id} - {self.customer.customer_id} ({self.product_type})"

    def ensure_expected_collections_schedule(self):
        if SavingsCollection.objects.filter(account=self, is_expected=True).exists():
            return

        tenure_unit = None
        if self.product_type == 'fd' and self.product_id:
            tenure_unit = OneTimeDeposit.objects.filter(one_time_deposit_id=self.product_id).values_list('tenure_unit', flat=True).first()
        elif self.product_type == 'rd' and self.product_id:
            tenure_unit = DailyProduct.objects.filter(daily_product_id=self.product_id).values_list('tenure_unit', flat=True).first()

        if tenure_unit in ['daily', 'days']:
            step_days = 1
        elif tenure_unit in ['weekly', 'weeks']:
            step_days = 7
        elif tenure_unit in ['monthly', 'months']:
            step_days = 30
        elif tenure_unit in ['yearly', 'years']:
            step_days = 365
        else:
            step_days = 30

        start_date = (self.hq_approved_at or self.account_opened_at or timezone.now()).date()

        expected_amount = self.installment_amount
        if expected_amount is None:
            if self.product_type == 'fd' and self.product_id:
                expected_amount = OneTimeDeposit.objects.filter(one_time_deposit_id=self.product_id).values_list('deposit_amount', flat=True).first()
            elif self.product_type == 'rd' and self.product_id:
                expected_amount = DailyProduct.objects.filter(daily_product_id=self.product_id).values_list('deposit_amount', flat=True).first()

        if expected_amount is None:
            return

        rows = []
        if self.product_type == 'rd':
            for i in range(1, (self.tenure or 0) + 1):
                short_uuid = str(uuid.uuid4())[:8].upper()
                rows.append(
                    SavingsCollection(
                        collection_id=f"SCOL-{short_uuid}",
                        account=self,
                        collection_type='rd_installment',
                        amount=expected_amount,
                        collection_date=start_date + timedelta(days=step_days * (i - 1)),
                        installment_no=i,
                        is_expected=True,
                        is_collected=False,
                        branch=self.branch,
                        agent=self.agent,
                    )
                )

        if rows:
            SavingsCollection.objects.bulk_create(rows)


class SavingsCollection(models.Model):
    TXN_TYPES = [
        ('rd_installment', 'RD Installment'),
        ('fd_deposit', 'FD Deposit'),
        ('interest', 'Interest'),
        ('penalty', 'Penalty'),
        ('withdrawal', 'Withdrawal'),
        ('maturity_payout', 'Maturity Payout'),
    ]

    PAYMENT_MODES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('bank', 'Bank'),
        ('other', 'Other'),
    ]

    collection_id = models.CharField(max_length=50, editable=False, unique=True)
    account = models.ForeignKey(SavingsAccountApplication, on_delete=models.CASCADE, related_name='collections')
    collection_type = models.CharField(max_length=20, choices=TXN_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    collection_date = models.DateField()

    installment_no = models.PositiveIntegerField(null=True, blank=True)
    is_expected = models.BooleanField(default=False)
    is_collected = models.BooleanField(default=True)

    receipt_no = models.CharField(max_length=50, null=True, blank=True)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='cash')
    note = models.TextField(null=True, blank=True)

    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='savings_transactions')
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='savings_transactions')
    collected_by_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='savings_collections')
    collected_by_branch_employee = models.ForeignKey(BranchEmployee, on_delete=models.SET_NULL, null=True, blank=True, related_name='savings_transactions')

    is_deposited_to_branch = models.BooleanField(default=False)
    deposited_at = models.DateTimeField(null=True, blank=True)
    deposited_deposit_id = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('account', 'collection_type', 'installment_no', 'is_expected')]

    def save(self, *args, **kwargs):
        if not self.collection_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.collection_id = f"SCOL-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.collection_id} - {self.account.application_id} ({self.collection_type})"


class SavingsAgentAssign(models.Model):
    assignment_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    account = models.ForeignKey(SavingsAccountApplication, on_delete=models.CASCADE, related_name='agent_assignments')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='savings_agent_assignments')
    assigned_by = models.ForeignKey(
        BranchEmployee,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_savings_accounts',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-assigned_at']
        constraints = [
            models.UniqueConstraint(
                fields=['account'],
                condition=Q(is_active=True),
                name='unique_active_savings_agent_assign_per_account',
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.assignment_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.assignment_id = f"SASSIGN-{short_uuid}"
        if self.is_active:
            SavingsAgentAssign.objects.filter(
                account=self.account,
                is_active=True,
            ).exclude(assignment_id=self.assignment_id).update(is_active=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.assignment_id} - {self.account.application_id} -> {self.agent.agent_id}"


class SavingType(models.Model):
    type_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True, related_name='created_saving_types')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Saving Type"
        verbose_name_plural = "Saving Types"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.type_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.type_id = f"SAVTYPE-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.type_id} - {self.name}"


class OneTimeDeposit(models.Model):
    TENURE_UNIT_CHOICES = [
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
        ('years', 'Years'),
    ]
    one_time_deposit_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    tenure = models.PositiveIntegerField()
    tenure_unit = models.CharField(max_length=20, choices=TENURE_UNIT_CHOICES, default='months')
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True, related_name='created_one_time_deposits')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "One Time Deposit"
        verbose_name_plural = "One Time Deposits"
        ordering = ['deposit_amount', 'tenure', 'tenure_unit', 'payable_amount']
        unique_together = [('deposit_amount', 'tenure', 'tenure_unit')]

    def save(self, *args, **kwargs):
        if not self.one_time_deposit_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.one_time_deposit_id = f"OTD-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.one_time_deposit_id} - {self.deposit_amount} ({self.tenure} {self.tenure_unit})"


class DailyProduct(models.Model):
    TENURE_UNIT_CHOICES = [
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
        ('years', 'Years'),
    ]
    daily_product_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tenure = models.PositiveIntegerField()
    tenure_unit = models.CharField(max_length=20, choices=TENURE_UNIT_CHOICES, default='days')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True, related_name='created_daily_products')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Daily Product"
        verbose_name_plural = "Daily Products"
        ordering = ['deposit_amount', 'interest_rate', 'tenure', 'tenure_unit']
        unique_together = [('deposit_amount', 'interest_rate', 'tenure', 'tenure_unit')]

    def save(self, *args, **kwargs):
        if not self.daily_product_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.daily_product_id = f"DLY-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.daily_product_id} - {self.deposit_amount} @ {self.interest_rate}% ({self.tenure} {self.tenure_unit})"
