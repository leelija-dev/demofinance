import uuid

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
from django.db import models
from agent.models import Agent
from django.utils import timezone
from django.db.models import Q, UniqueConstraint
from headquater.models import Branch, HeadquarterEmployee
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.files.storage import default_storage
from django.db.models.fields.files import FieldFile
from cloudinary_storage.storage import MediaCloudinaryStorage

class LoanApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('success', 'Success'),
        ('reject', 'Rejected'),
        ('rejected_by_branch', 'Rejected by Branch'),
        ('inactive', 'Inactive'),
        ('document_requested', 'Document Requested by Branch'),
        ('resubmitted', 'Resubmitted - Pending Branch Review'),
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
        ('closed', 'Closed'),
    ]
    loan_ref_no = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    customer = models.ForeignKey('CustomerDetail', on_delete=models.CASCADE, related_name='loan_applications', null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='pending')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='loan_applications')
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, related_name='loan_applications')
    shop = models.ForeignKey('Shop', on_delete=models.SET_NULL, null=True, blank=True, related_name='loan_applications')
    shop_bank_account = models.ForeignKey('ShopBankAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='loan_applications')
    created_by_agent = models.ForeignKey(
        Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_loan_applications'
    )
    created_by_branch_manager = models.ForeignKey('branch.BranchEmployee', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_loan_applications'
    )
    rejection_reason = models.TextField(blank=True, null=True)
    document_request_reason = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    ever_branch_approved = models.BooleanField(default=False)
    customer_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON snapshot of CustomerDetail (personal info) at application time. "
                  "Used so old loans show historical data while current customer record stays updated."
    )

    def save(self, *args, **kwargs):
        print("Start LoanApplication Save.............................................")
        if not self.loan_ref_no:
            print("called if not self.loan_ref_no.............................................")
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.loan_ref_no = f"LOAN-{short_uuid}"
            print('Completed if 1')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.loan_ref_no} - {self.customer.full_name}"
    
    def populate_customer_snapshot(self, force=False):
        """
        Populates the customer_snapshot JSONField with a point-in-time snapshot 
        of related customer data.
        
        Call this on a LoanApplication instance, e.g.:
            loan.populate_customer_snapshot()
            loan.save(update_fields=['customer_snapshot'])
            
        Use force=True to overwrite an existing snapshot.
        """

        print('Start  populating customer snapshot ...................................................')
        if not self.customer:
            print('Nothing to snapshot')
            return  # Nothing to snapshot

        if self.customer_snapshot and not force:
            print('Already has snapshot (skip unless forced)')
            return  # Already has snapshot (skip unless forced)

        snapshot = {
            "snapshot_timestamp": datetime.now().isoformat(),
            "customer_details": {},
            "address": {},
            "bank_details": {},
            "documents": []
        }

        customer = self.customer

        # === 1. CustomerDetail snapshot ===
        customer_fields = [
            f.name for f in customer._meta.fields
            if f.name not in ['id', 'customer_id', 'created_at', 'updated_at', 'last_update',
                              'loan_application', 'agent', 'branch', 'branch_rejection_reason']
        ]

        for field_name in customer_fields:
            value = getattr(customer, field_name, None)
            if isinstance(value, (date, datetime)):
                value = value.isoformat()
            elif isinstance(value, FieldFile):
                value = default_storage.url(value.name) if value.name else None
            elif isinstance(value, Decimal):
                value = str(value)
            snapshot["customer_details"][field_name] = value

        print('Customer details snapshot completed -> ', snapshot["customer_details"])
        # === 2. Address (OneToOne or related) ===
        # try:
        # address = customer.customeraddress_set.first() if hasattr(customer, 'customeraddress_set') else None
        address = None
        if hasattr(customer, 'address'):
            try:
                address = customer.address
            except ObjectDoesNotExist:
                address = None
        # Alternative: if you have a direct OneToOneField on CustomerDetail → CustomerAddress
        # address = getattr(customer, 'customeraddress', None)

        print('hasattr(customer, "customeraddress_set") -> ', hasattr(customer, 'customeraddress_set'))
        print('customer.address -> ', address)
        print('address -> ',address)
        if address:
            addr_fields = [
                f.name for f in address._meta.fields
                if f.name not in ['id', 'customer_id', 'customer', 'loan_application',
                                    'agent', 'branch', 'submitted_at', 'last_update']
            ]
            for field_name in addr_fields:
                value = getattr(address, field_name, None)
                if isinstance(value, (date, datetime)):
                    value = value.isoformat()
                elif isinstance(value, FieldFile):
                    value = default_storage.url(value.name) if value.name else None
                snapshot["address"][field_name] = value
        # except Exception:
        #     pass  # Address may not exist

        print('Address snapshot completed -> ', snapshot["address"] if snapshot["address"] else 'No address found')
        
        # === 3. Bank Details (CustomerAccount) ===
        # try:
        # bank = customer.customeraccount_set.first() if hasattr(customer, 'customeraccount_set') else None
        bank = None
        if hasattr(customer, 'account'):
            try:
                bank = customer.account
            except ObjectDoesNotExist:
                bank = None
        # Or: bank = getattr(customer, 'customeraccount', None)
        
        print('hasattr(customer, "customeraccount_set") -> ', hasattr(customer, 'customeraccount_set'))
        print('customer.account -> ', bank)
        print('bank -> ',bank)

        if bank:
            bank_fields = [
                f.name for f in bank._meta.fields
                if f.name not in ['id', 'customer_id', 'customer', 'loan_application',
                                    'agent', 'branch', 'submitted_at', 'last_update']
            ]
            for field_name in bank_fields:
                value = getattr(bank, field_name, None)
                if isinstance(value, (date, datetime)):
                    value = value.isoformat()
                elif isinstance(value, FieldFile):
                    value = default_storage.url(value.name) if value.name else None
                snapshot["bank_details"][field_name] = value
        # except Exception:
        #     pass

        print('Bank details snapshot completed -> ', snapshot["bank_details"] if snapshot["bank_details"] else 'No bank details found')

        # === 4. Documents ===
        # try:
            # Option A: If CustomerDocument has a OneToOne relation with loan_application
        if hasattr(self, 'documents') and self.documents:
            doc = self.documents
            doc_fields = [
                f.name for f in doc._meta.fields
                if f.name not in ['id', 'loan_application', 'savings_application',
                                    'agent', 'branch', 'submitted_at', 'last_update']
            ]
            doc_snapshot = {}
            for field_name in doc_fields:
                value = getattr(doc, field_name, None)
                if isinstance(value, FieldFile):
                    value = default_storage.url(value.name) if value.name else None
                elif isinstance(value, (date, datetime)):
                    value = value.isoformat()
                elif isinstance(value, Decimal):
                    value = str(value)
                doc_snapshot[field_name] = value

            snapshot["documents"] = [doc_snapshot]

            # Option B: If multiple documents via reverse relation (uncomment if needed)
            # docs = customer.customerdocument_set.all()
            # snapshot["documents"] = [ ... build list ... ]

        # except Exception:
        #     snapshot["documents"] = []
        print('Snapshot completed -> ', snapshot)

        self.customer_snapshot = snapshot

class CustomerDetail(models.Model):
    loan_application = models.ForeignKey('LoanApplication', on_delete=models.SET_NULL, null=True, blank=True, related_name='customer_details')
    customer_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    full_name = models.CharField(max_length=255)
    father_name = models.CharField(max_length=255, blank=True, null=True)
    guarantor_name = models.CharField(max_length=255, blank=True, null=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20)
    contact = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    adhar_number = models.CharField(max_length=20, unique=True)
    pan_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    voter_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    branch_rejection_reason = models.TextField(blank=True, null=True)
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, related_name='customers')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='customers')
    submitted_at = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pan_number:
            self.pan_number = self.pan_number.upper()
        if not self.customer_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.customer_id = f"CUST-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_id} - {self.full_name}"

class CustomerAddress(models.Model):
    loan_application = models.ForeignKey('LoanApplication', on_delete=models.SET_NULL, null=True, blank=True, related_name='customer_addresses')
    customer = models.OneToOneField(CustomerDetail, on_delete=models.CASCADE, related_name='address')
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    landmark = models.CharField(max_length=255, blank=True, null=True)
    post_office = models.CharField(max_length=255, blank=True, null=True)
    city_or_town = models.CharField(max_length=255, default='N/A')
    district = models.CharField(max_length=255, default='N/A')
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=255, default='India')
    post_code = models.CharField(max_length=20)
    current_address_line_1 = models.CharField(max_length=255)
    current_address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    current_landmark = models.CharField(max_length=255, blank=True, null=True)
    current_post_office = models.CharField(max_length=255, blank=True, null=True)
    current_city_or_town = models.CharField(max_length=255, default='N/A')
    current_district = models.CharField(max_length=255, default='N/A')
    current_state = models.CharField(max_length=100)
    current_country = models.CharField(max_length=255, default='India')
    current_post_code = models.CharField(max_length=20)
    residential_proof_type = models.CharField(max_length=50, blank=True, null=True, choices=[
        ('electricity_bill', 'Electricity Bill'),
        ('water_bill', 'Water Bill'),
        ('gas_bill', 'Gas Bill'),
        ('rental_agreement', 'Rental Agreement (with landlord signature)'),
        ('bank_passbook', 'Bank Passbook with current address'),
        ('government_certificate', 'Government-issued Address Certificate'),
        ('mobile_bill', 'Post-paid Mobile Bill'),
    ])
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, related_name='customer_addresses')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='customer_addresses')
    submitted_at = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Address for Customer {self.customer.customer_id}"

class CustomerLoanDetail(models.Model):
    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, null=True, blank=True, related_name='loan_details')
    loan_category = models.ForeignKey('LoanCategory', on_delete=models.SET_NULL, null=True, related_name='loan_applications')
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tenure = models.ForeignKey('LoanTenure', on_delete=models.SET_NULL, null=True, related_name='loan_applications')
    loan_purpose = models.CharField(max_length=255)
    interest_rate = models.ForeignKey('LoanInterest', on_delete=models.SET_NULL, null=True, related_name='loan_applications')
    emi_amount = models.DecimalField(max_digits=12, decimal_places=2)
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='customer_loans')
    loan_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    processing_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    processing_fee_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON snapshot of processing fee details at application time."
    )
    down_payment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, related_name='customer_loans')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='customer_loans')
    submitted_at = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loan for Application {self.loan_application.loan_ref_no if self.loan_application else 'N/A'} - {self.loan_category}"

class CustomerDocument(models.Model):
    loan_application = models.OneToOneField('LoanApplication', on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    savings_application = models.OneToOneField('savings.SavingsAccountApplication', on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    id_proof = models.FileField(upload_to='static/customer/id_proof/', storage=MediaCloudinaryStorage())
    guarantor_id_proof = models.FileField(upload_to='static/customer/guarantor_id_proof/', blank=True, null=True, storage=MediaCloudinaryStorage())
    pan_card_document = models.FileField(upload_to='static/customer/pan_card/', blank=True, null=True, storage=MediaCloudinaryStorage())
    id_proof_back = models.FileField(upload_to='static/customer/id_proof/', blank=True, null=True, storage=MediaCloudinaryStorage())
    income_proof = models.FileField(upload_to='static/customer/income_proof/', blank=True, null=True, storage=MediaCloudinaryStorage())
    photo = models.ImageField(upload_to='static/customer/photo/', blank=True, null=True, storage=MediaCloudinaryStorage())
    signature = models.FileField(upload_to='static/customer/signature/', blank=True, null=True, storage=MediaCloudinaryStorage())
    collateral = models.FileField(upload_to='static/customer/collateral/', blank=True, null=True, storage=MediaCloudinaryStorage())
    residential_proof_file = models.FileField(upload_to='static/customer/residential_proof/', blank=True, null=True, storage=MediaCloudinaryStorage())
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, related_name='customer_documents')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='customer_documents')
    submitted_at = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.loan_application:
            return f"Documents for Application {self.loan_application.loan_ref_no}"
        if self.savings_application:
            return f"Documents for Savings Application {self.savings_application.application_id}"
        return "Documents"

class CustomerAccount(models.Model):
    ACCOUNT_TYPES = [
        ('', 'Select Account Type'),
        ('savings', 'Savings'),
        ('current', 'Current'),
        ('fixed_deposit', 'Fixed Deposit'),
        ('recurring_deposit', 'Recurring Deposit'),
    ]

    loan_application = models.OneToOneField('LoanApplication', on_delete=models.CASCADE, null=True, blank=True, related_name='customer_account')
    customer = models.OneToOneField(CustomerDetail, on_delete=models.CASCADE, related_name='account')
    account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='', blank=True, null=True)
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, related_name='customer_accounts')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='customer_accounts')
    submitted_at = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Customer Account"
        verbose_name_plural = "Customer Accounts"

    def __str__(self):
        return f"Account for Customer {self.customer.customer_id} - {self.account_number}"
        
class DocumentRequest(models.Model):
    DOCUMENT_TYPES = [
        ('id_proof', 'ID Proof (Aadhar/PAN)'),
        ('pan_card_document', 'PAN Card Document'),
        ('id_proof_back', 'ID Proof Back'),
        ('income_proof', 'Income Proof'),
        ('photo', 'Passport Photo'),
        ('signature', 'Digital Signature'),
        ('collateral', 'Collateral Documents'),
        ('residential_proof', 'Residential Proof'),
        ('residential_proof_file', 'Residential Proof'),
    ]
    
    REQUEST_REASONS = [
        ('missing', 'Document Missing'),
        ('blurred', 'Document Blurred/Unclear'),
        ('wrong_file', 'Wrong Document Uploaded'),
        ('expired', 'Document Expired'),
        ('incomplete', 'Document Incomplete'),
        ('other', 'Other'),
    ]
    
    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, null=True, blank=True, related_name='document_requests')
    savings_application = models.ForeignKey('savings.SavingsAccountApplication', on_delete=models.CASCADE, null=True, blank=True, related_name='document_requests')
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    reason = models.CharField(max_length=20, choices=REQUEST_REASONS)
    comment = models.TextField(blank=True, null=True)
    requested_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.SET_NULL, null=True, related_name='document_requests')
    requested_by_hq = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True, blank=True, related_name='hq_document_requests')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='document_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-requested_at']
    
    def __str__(self):
        who = self.requested_by or self.requested_by_hq
        app_ref = 'N/A'
        if self.loan_application:
            app_ref = self.loan_application.loan_ref_no
        elif self.savings_application:
            app_ref = self.savings_application.application_id
        return f"Document Request for Application {app_ref} - {self.get_document_type_display()} (by {who})"
    
    def mark_as_resolved(self):
        """Mark the document request as resolved"""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.save()

class DocumentReupload(models.Model):
    document_request = models.ForeignKey(DocumentRequest, on_delete=models.CASCADE, related_name='reuploads')
    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, null=True, blank=True, related_name='document_reuploads')
    document_type = models.CharField(max_length=30, choices=DocumentRequest.DOCUMENT_TYPES)
    uploaded_file = models.FileField(upload_to='static/customer/reuploads/', storage=MediaCloudinaryStorage())
    agent_note = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, related_name='document_reuploads')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Reupload for Application {self.loan_application.loan_ref_no if self.loan_application else 'N/A'} - {self.get_document_type_display()}"

class DocumentReview(models.Model):
    REVIEW_DECISIONS = [
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('request_again', 'Request Again'),
        ('reject_application', 'Reject Application - Document Tampering Suspected'),
    ]
    
    document_reupload = models.ForeignKey(DocumentReupload, on_delete=models.CASCADE, related_name='reviews')
    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, null=True, blank=True, related_name='document_reviews')
    decision = models.CharField(max_length=20, choices=REVIEW_DECISIONS)
    review_comment = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.SET_NULL, null=True, related_name='document_reviews')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, related_name='document_reviews')
    reviewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-reviewed_at']
    
    def __str__(self):
        return f"Review for Application {self.loan_application.loan_ref_no if self.loan_application else 'N/A'} - {self.get_decision_display()}"
    
    def save(self, *args, **kwargs):
        # Status update logic removed; handled in the view instead
        super().save(*args, **kwargs)

class LoanMainCategory(models.Model):
    main_category_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    # name = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    is_shop_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True, related_name='created_loan_main_categories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Loan Main Category'
        verbose_name_plural = 'Loan Main Categories'
        ordering = ['name']
        constraints = [
            # 1. When created_by has a value → unique together (created_by + name)
            UniqueConstraint(
                fields=['created_by', 'name'],
                condition=Q(created_by__isnull=False),
                name='unique_created_by_name_when_not_null'
            ),
            
            # 2. When created_by is NULL → name must be unique by itself
            UniqueConstraint(
                fields=['name'],
                condition=Q(created_by__isnull=True),
                name='unique_name_when_created_by_null'
            ),
        ]


    def save(self, *args, **kwargs):
        if not self.main_category_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.main_category_id = f"LoanMAIN-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.main_category_id} - {self.name}"

class LoanCategory(models.Model):
    category_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    main_category = models.ForeignKey(
        LoanMainCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_categories',
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True, related_name='created_loan_categories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Loan Category"
        verbose_name_plural = "Loan Categories"
        ordering = ['name']
        unique_together = [('main_category', 'name', 'created_by')]
    
    def save(self, *args, **kwargs):
        if not self.category_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.category_id = f"LoanCAT-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        if self.main_category:
            return f"{self.category_id} - {self.main_category.name} - {self.name}"
        return f"{self.category_id} - {self.name}"

class LoanInterest(models.Model):
    interest_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    main_category = models.ForeignKey(
        LoanMainCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_interest_rates',
    )
    rate_of_interest = models.DecimalField(max_digits=5, decimal_places=2, help_text="Interest rate in percentage (e.g., 12.50 for 12.5%)")
    description = models.CharField(max_length=255, blank=True, null=True, help_text="Optional description for this interest rate")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True, related_name='created_loan_interests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Loan Interest Rate"
        verbose_name_plural = "Loan Interest Rates"
        ordering = ['rate_of_interest']
        unique_together = [('main_category', 'rate_of_interest', 'created_by')]
    
    def save(self, *args, **kwargs):
        if not self.interest_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.interest_id = f"LoanINT-{short_uuid}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.interest_id} - {self.rate_of_interest}%"


class LoanTenure(models.Model):
    UNIT_CHOICES = [
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
        ('years', 'Years'),
    ]

    tenure_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    interest_rate = models.ForeignKey(LoanInterest, on_delete=models.CASCADE, related_name='tenures')
    value = models.PositiveIntegerField(help_text="Duration value (e.g., 90 for 90 days)")
    unit = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES,
        help_text="Unit of duration (e.g., 'days', 'weeks', 'months', 'years')",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True, related_name='created_loan_tenures')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Loan Tenure"
        verbose_name_plural = "Loan Tenures"
        ordering = ['value', 'unit']
        unique_together = [('interest_rate', 'value', 'unit', 'created_by')]

    def save(self, *args, **kwargs):
        if not self.tenure_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.tenure_id = f"TEN-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tenure_id} - {self.value} {self.unit} ({self.interest_rate.rate_of_interest}%)"

    @property
    def display_name(self):
        return f"{self.value} {self.unit} ({self.interest_rate.rate_of_interest}%)"


class LoanPeriod(models.Model):
    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, related_name='periods')
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    rate_of_interest = models.DecimalField(max_digits=5, decimal_places=2, help_text="Interest rate in percentage (e.g., 12.50 for 12.5%)")
    installment_size = models.DecimalField(max_digits=12, decimal_places=2, help_text="EMI or installment amount")
    realizable_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total amount to be realized (principal + interest)")
    number_of_installments = models.PositiveIntegerField(help_text="Number of installments")
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=None)
    remaining_principal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=None)
    remaining_interest = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    reschedule_count = models.PositiveIntegerField(default=0)
    original_installment_size = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original installment size for comparison during reschedule",
    )
    original_frequency = models.CharField(
        max_length=10,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        null=True,
        blank=True,
        help_text="Original frequency (daily/weekly/monthly) of this period",
    )
    is_reschedule = models.BooleanField(
        default=False,
        help_text="True if this LoanPeriod was created as part of a reschedule.",
    )
    original_period = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rescheduled_periods',
        help_text="Reference to the original LoanPeriod from which this reschedule was derived.",
    )

    def __str__(self):
        return f"LoanPeriod for {self.loan_application.loan_ref_no} - {self.number_of_installments} installments"


class Deductions(models.Model):
    deduction_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    main_category = models.ForeignKey(
        LoanMainCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_deductions',
    )
    deduction_name = models.CharField(max_length=255)
    deduction_type = models.CharField(max_length=50, choices=[
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ])
    deduction_value = models.DecimalField(max_digits=10, decimal_places=2)
    deduction_description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True,
    related_name='deductions_created', blank=True)
    updated_by = models.ForeignKey(HeadquarterEmployee, on_delete=models.SET_NULL, null=True,
    related_name='deductions_updated', blank=True)

    class Meta:
        verbose_name = 'Deduction'
        verbose_name_plural = 'Deductions'
        unique_together = ('main_category', 'deduction_name', 'deduction_type', 'created_by')

    def save(self, *args, **kwargs):
        if not self.deduction_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.deduction_id = f"DED-{short_uuid}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.deduction_name} ({self.get_deduction_type_display()}: {self.deduction_value})"


class LateFeeSetting(models.Model):
    """Late fee settings applied to overdue EMIs.
    - percentage: percentage of the EMI installment amount charged as late fee
    - grace_days: number of days after installment_date before late fee applies
    - is_active: allow toggling and keeping history of changes
    """
    FEE_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('amount', 'Fixed Amount'),
    ]

    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    # Deprecated: kept for backward compatibility with older records/templates
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="[Deprecated] Late fee percentage (e.g., 2.50 for 2.5%)")
    main_category = models.ForeignKey(
        LoanMainCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='late_fee_settings',
    )
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES, default='percentage')
    fee_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Late fee value (percentage or fixed amount based on type)")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='monthly', help_text="How often late fee accrues")
    grace_days = models.PositiveIntegerField(default=5, help_text="Number of days after due date before late fee applies")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        HeadquarterEmployee, on_delete=models.SET_NULL, null=True, blank=True, related_name='late_fee_settings_created_in_loan'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Late Fee Setting'
        verbose_name_plural = 'Late Fee Settings'
        ordering = ['-created_at']

    def __str__(self):
        if self.fee_type == 'percentage':
            val_display = f"{self.fee_value}%"
        else:
            val_display = f"{self.fee_value}"
        return f"LateFee {val_display} {self.frequency} after {self.grace_days} days ({'Active' if self.is_active else 'Inactive'})"

    @classmethod
    def get_active(cls):
        """Return the most recent active setting, or None if not configured."""
        return cls.objects.filter(is_active=True).order_by('-created_at').first()

    @property
    def display_value(self):
        """Return a formatted value string with unit for display."""
        return f"{self.fee_value}%" if self.fee_type == 'percentage' else f"{self.fee_value}"


##### for loan disbursed #####

class DisbursementLog(models.Model):
    MODE_CHOICES = [
        ('Cash', 'Cash'),
        ('Bank Transfer', 'Bank Transfer'),
        ('UPI', 'UPI'),
        ('Cheque', 'Cheque'),
    ]

    dis_id = models.CharField(
        primary_key=True, max_length=50, editable=False, unique=True
    )
    loan_id = models.ForeignKey(
        'LoanApplication',
        on_delete=models.CASCADE,
        related_name='disbursement_logs' 
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    disb_mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    bank_name = models.CharField(max_length=255, blank=True)
    account_number = models.CharField(max_length=50, blank=True)  
    net_amount_cust = models.DecimalField(max_digits=12, decimal_places=2)
    tax_charges = models.DecimalField(max_digits=12, decimal_places=2)
    disburse_proof = models.CharField(max_length=255, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    disbursed_by = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='disbursements_made')
    disbursed_to = models.ForeignKey(
        'LoanApplication',
        on_delete=models.CASCADE,
        related_name='disbursements_received'  
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.dis_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.dis_id = f"DIS-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Disbursement {self.dis_id} for {self.loan_id.loan_ref_no} by {self.disbursed_by}"

    class Meta:
        verbose_name = "Disbursement Log"
        verbose_name_plural = "Disbursement Logs"


class ProductCategory(models.Model):
    main_category_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    name = models.CharField(max_length=100, unique=True)
    loan_main_category = models.ForeignKey(
        LoanMainCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_categories',
    )
    loan_category = models.ForeignKey(
        LoanCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_categories',
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        HeadquarterEmployee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_product_categories',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Category'
        verbose_name_plural = 'Product Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.main_category_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.main_category_id = f"PRODMAIN-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.main_category_id} - {self.name}"


class ProductSubCategory(models.Model):
    sub_category_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    main_category = models.ForeignKey(
        ProductCategory,
        on_delete=models.CASCADE,
        related_name='sub_categories',
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        HeadquarterEmployee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_product_sub_categories',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Sub Category'
        verbose_name_plural = 'Product Sub Categories'
        ordering = ['name']
        unique_together = [('main_category', 'name', 'created_by')]

    def save(self, *args, **kwargs):
        if not self.sub_category_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.sub_category_id = f"PRODSUB-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sub_category_id} - {self.main_category.name} - {self.name}"


class Product(models.Model):
    product_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    sub_category = models.ForeignKey(
        ProductSubCategory,
        on_delete=models.CASCADE,
        related_name='products',
    )
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        HeadquarterEmployee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_products',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['name']
        unique_together = [('sub_category', 'name', 'created_by')]

    def save(self, *args, **kwargs):
        if not self.product_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.product_id = f"PROD-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_id} - {self.name} ({self.price})"

###------ for loan emi schedule ------###

class LoanEMISchedule(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, related_name='emi_schedules')
    # installment_number = models.PositiveIntegerField()
    installment_date = models.DateField()
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='monthly')
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2)  
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2) 
    # remaining_principal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)   
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2) 
    # remaining_interest = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)     
    paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    is_overdue = models.BooleanField(default=False)  
    overdue_days = models.PositiveIntegerField(default=0)  
    late_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    # 0 = original schedule, 1 = loan has been rescheduled
    reschedule = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('loan_application', 'installment_date')
        ordering = ['installment_date']

    def __str__(self):
        return f"EMI {self.installment_date} for {self.loan_application.loan_ref_no} ({self.frequency})"


class LoanRescheduleLog(models.Model):
    UNIT_CHOICES = [
        ('days', 'Days'),
        ('weeks', 'Weeks'),
    ]

    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, related_name='reschedule_logs')
    period = models.ForeignKey('LoanPeriod', on_delete=models.CASCADE, related_name='reschedule_logs')

    reschedule_no = models.PositiveIntegerField(help_text="1..3, number of times this loan has been rescheduled")
    old_outstanding = models.DecimalField(max_digits=12, decimal_places=2)
    penalty_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Penalty rate in percentage")
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2)
    new_total_balance = models.DecimalField(max_digits=12, decimal_places=2)
    new_installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    new_number_of_installments = models.PositiveIntegerField()

    reschedule_unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    reschedule_length = models.PositiveIntegerField(help_text="Length of reschedule period (30 days or 5 weeks)")

    remarks = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        'branch.BranchEmployee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_reschedules_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Reschedule #{self.reschedule_no} for {self.loan_application.loan_ref_no}"


class LoanEMIReschedule(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, related_name='emi_reschedules')
    reschedule_log = models.ForeignKey('LoanRescheduleLog', on_delete=models.CASCADE, related_name='emi_reschedules')
    installment_date = models.DateField()
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='monthly')
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Mirror core status fields from LoanEMISchedule for rescheduled plan tracking
    paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    is_overdue = models.BooleanField(default=False)
    overdue_days = models.PositiveIntegerField(default=0)
    late_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['installment_date']

    def __str__(self):
        return f"Rescheduled EMI {self.installment_date} for {self.loan_application.loan_ref_no}"

class EmiAgentAssign(models.Model):
    assignment_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='emi_assignments')
    emi = models.ForeignKey(LoanEMISchedule, on_delete=models.CASCADE, related_name='agent_assignments', null=True, blank=True)
    reschedule_emi = models.ForeignKey('LoanEMIReschedule', on_delete=models.CASCADE, related_name='agent_assignments', null=True, blank=True)
    installment_date = models.DateField()
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2)
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    assigned_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.SET_NULL, null=True, related_name='assigned_emis')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-assigned_at']
        unique_together = (
            ('emi', 'is_active'),
            ('reschedule_emi', 'is_active'),
        )

    def save(self, *args, **kwargs):
        if not self.assignment_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.assignment_id = f"EMA-{short_uuid}"
            
            # Determine source EMI (original or rescheduled)
            source_emi = self.emi or self.reschedule_emi
            if source_emi is None:
                raise ValueError("EmiAgentAssign must have either emi or reschedule_emi set.")

            # Copy values from related EMI
            self.installment_date = source_emi.installment_date
            self.principal_amount = source_emi.principal_amount
            self.interest_amount = source_emi.interest_amount
            self.installment_amount = source_emi.installment_amount

            # Deactivate any other active assignments for this EMI (original or rescheduled)
            if self.emi is not None:
                EmiAgentAssign.objects.filter(
                    emi=self.emi,
                    is_active=True
                ).exclude(assignment_id=self.assignment_id).update(is_active=False)
            if self.reschedule_emi is not None:
                EmiAgentAssign.objects.filter(
                    reschedule_emi=self.reschedule_emi,
                    is_active=True
                ).exclude(assignment_id=self.assignment_id).update(is_active=False)
            
        super().save(*args, **kwargs)

    def __str__(self):
        if self.emi is not None:
            return f"{self.agent.full_name} assigned to EMI {self.emi.id} for {self.emi.loan_application.loan_ref_no}"
        if self.reschedule_emi is not None:
            return f"{self.agent.full_name} assigned to Rescheduled EMI {self.reschedule_emi.id} for {self.reschedule_emi.loan_application.loan_ref_no}"
        return f"{self.agent.full_name} assigned to EMI (unlinked)"

class EmiCollectionDetail(models.Model):
    PAYMENT_MODES = [
        ('Cash', 'Cash'),
        ('Bank Transfer', 'Bank Transfer'),
        ('UPI', 'UPI'),
        ('Cheque', 'Cheque'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('collected', 'Collected'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    collected_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    assignment = models.ForeignKey('EmiAgentAssign', on_delete=models.CASCADE, related_name='collections', null=True, blank=True)
    # Original EMI (pre-reschedule)
    emi = models.ForeignKey('LoanEMISchedule', on_delete=models.CASCADE, related_name='collections', null=True, blank=True)
    # Rescheduled EMI (post-reschedule); exactly one of emi or reschedule_emi should be set
    reschedule_emi = models.ForeignKey('LoanEMIReschedule', on_delete=models.CASCADE, related_name='collections', null=True, blank=True)
    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, related_name='emi_collections')

    # Either an Agent collected it, or a Branch collected it
    collected_by_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='emi_collections_made')
    collected_by_branch = models.ForeignKey('branch.BranchEmployee', on_delete=models.SET_NULL, null=True, blank=True, related_name='emi_collections_received')

    amount_received = models.DecimalField(max_digits=12, decimal_places=2)
    principal_received = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    interest_received = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    penalty_received = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='Cash')
    payment_reference = models.CharField(max_length=100, blank=True, null=True)

    collected_at = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)

    agent_reject_reason = models.TextField(blank=True, null=True)
    agent_rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by_agent = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emi_rejections_made'
    )

    verified_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.SET_NULL, null=True, blank=True, related_name='emi_collections_verified')
    verified_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    collected = models.BooleanField(default=False)

    class Meta:
        ordering = ['-collected_at']
        constraints = [
            models.UniqueConstraint(
                fields=['emi'],
                condition=Q(collected=True),
                name='unique_true_collected_per_emi'
            )
        ]

    def clean(self):
        # Ensure exactly one of collected_by_agent or collected_by_branch is set
        if bool(self.collected_by_agent) == bool(self.collected_by_branch):
            raise ValidationError('Exactly one of collected_by_agent or collected_by_branch (manager) must be set.')

    def save(self, *args, **kwargs):
        if not self.collected_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.collected_id = f"COL-{short_uuid}"
        # Normalize monetary fields to two decimal places
        if self.amount_received is not None:
            self.amount_received = Decimal(self.amount_received).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
        if self.principal_received is not None:
            self.principal_received = Decimal(self.principal_received).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
        if self.interest_received is not None:
            self.interest_received = Decimal(self.interest_received).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
        # Validate XOR constraint before saving
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.collected_id} - {self.loan_application.loan_ref_no if self.loan_application else 'N/A'}"


class LoanCloseRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    request_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    loan_application = models.ForeignKey('LoanApplication', on_delete=models.CASCADE, related_name='close_requests')
    branch = models.ForeignKey('headquater.Branch', on_delete=models.SET_NULL, null=True, related_name='loan_close_requests')
    requested_by = models.ForeignKey('branch.BranchEmployee', on_delete=models.SET_NULL, null=True, related_name='loan_close_requests_made')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    remarks = models.TextField(blank=True, null=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    approved_by = models.ForeignKey('headquater.HeadquarterEmployee', on_delete=models.SET_NULL, null=True, blank=True, related_name='loan_close_requests_approved')
    approved_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.request_id:
            import uuid
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.request_id = f"NOC-{short_uuid}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.request_id} - {self.loan_application.loan_ref_no} ({self.status})"


class LoanApplicationDraft(models.Model):
    USER_TYPE_CHOICES = [
        ('agent', 'Agent'), 
        ('branch', 'Branch'),
    ]

    draft_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    token = models.CharField(max_length=100, unique=True, help_text="Unique token for draft identification")
    user_id = models.CharField(max_length=50, help_text="Agent ID or Branch ID")
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    draft_data = models.JSONField(help_text="Complete form data as JSON")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = [('user_id', 'user_type', 'token')]

    def save(self, *args, **kwargs):
        if not self.draft_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.draft_id = f"DRAFT-{short_uuid}"
        if not self.token:
            self.token = str(uuid.uuid4())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Draft {self.draft_id} for {self.user_type} {self.user_id}"



class ChartOfAccount(models.Model):
    MAIN_TYPES = (
        ('A', 'Assets'),
        ('B', 'Fund and Liabilities'),
        ('C', 'Operation Expenses'),
        ('D', 'Income'),
    )

    main_type = models.CharField(
        max_length=1,
        choices=MAIN_TYPES,
        help_text="Main account type (A=Assets, B=Fund & Liabilities, C=Operation Expenses, D=Income)"
    )
    sl_no = models.PositiveIntegerField(help_text="Serial number under main type")
    head_of_account = models.CharField(max_length=255, help_text="Name of the head account")
    code = models.CharField(max_length=10, help_text="Account code number")
    description = models.TextField(blank=True, null=True, help_text="Nature of receipts and payments")
    is_editable = models.BooleanField(default=True, help_text="If False, this account row is locked from edits (e.g., seeded by migration)")

    class Meta:
        db_table = "chart_of_accounts"
        ordering = ["main_type", "sl_no"]
        verbose_name = "Chart of Account"
        verbose_name_plural = "Chart of Accounts"

    def __str__(self):
        main_type_display = dict(self.MAIN_TYPES).get(self.main_type, "Unknown")
        return f"{main_type_display} - {self.head_of_account} ({self.code})"


###############shop and shop account ##################

class Shop(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
    ]
    
    CREATED_BY_CHOICES = [
        ('agent', 'Agent'),
        ('branch', 'Branch'),
    ]

    shop_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='shops')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='shops')

    name = models.CharField(max_length=255)
    contact = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    owner_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.CharField(max_length=10, choices=CREATED_BY_CHOICES, default='agent')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.shop_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.shop_id = f"SHOP-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shop_id} - {self.name}"


class ShopBankAccount(models.Model):
    bank_account_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, related_name='bank_accounts')

    account_holder_name = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    upi_id = models.CharField(max_length=255, blank=True, null=True)

    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['shop']),
            models.Index(fields=['account_number']),
        ]

    def save(self, *args, **kwargs):
        if self.ifsc_code:
            self.ifsc_code = self.ifsc_code.upper()
        if not self.bank_account_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.bank_account_id = f"SBA-{short_uuid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"

