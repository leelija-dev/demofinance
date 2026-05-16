from dataclasses import fields
from pyexpat import model
from rest_framework import serializers
from django.db.models import Q
from .models import (
     LoanApplication,
     CustomerDetail,
     DocumentRequest,
     CustomerLoanDetail,
     CustomerAddress,
     CustomerDocument,
     Agent,
     LoanTenure,
     LoanCategory,
     LoanPeriod,
     Deductions,
     DisbursementLog,
     LoanEMISchedule,
     EmiAgentAssign,
     CustomerAccount,
     ChartOfAccount,
     EmiCollectionDetail,
)


class LoanApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanApplication
        fields = '__all__'

class CustomerDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerDetail
        fields = '__all__'

class LoanCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanCategory
        fields = '__all__'

class CustomerLoanDetailSerializer(serializers.ModelSerializer):
    loan_category = LoanCategorySerializer(read_only=True)
    tenure = serializers.SerializerMethodField()
    tenure_display = serializers.SerializerMethodField()
    interest_rate = serializers.SerializerMethodField()

    class Meta:
        model = CustomerLoanDetail
        fields = '__all__'

    def get_tenure(self, obj):
        return obj.tenure.value if obj.tenure else None

    def get_tenure_display(self, obj):
        if obj.tenure:
            return f"{obj.tenure.value} {obj.tenure.unit}"
        return None

    def get_interest_rate(self, obj):
        return float(obj.interest_rate.rate_of_interest) if obj.interest_rate else None


class CustomerAccountSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source='agent.full_name', read_only=True)
    branch_name = serializers.CharField(source='branch.branch_name', read_only=True)

    class Meta:
        model = CustomerAccount
        fields = [
            'account_number',
            'bank_name',
            'ifsc_code',
            'account_type',
            'agent_name',
            'branch_name',
            'submitted_at',
            'last_update',
        ]

class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = '__all__'

class CustomerDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerDocument
        fields = '__all__'

class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = '__all__'

class DocumentRequestSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()

    class Meta:
        model = DocumentRequest
        fields = '__all__'

    def get_customer(self, obj):
        if obj.loan_application and obj.loan_application.customer:
            return CustomerDetailSerializer(obj.loan_application.customer).data
        if obj.savings_application and obj.savings_application.customer:
            return CustomerDetailSerializer(obj.savings_application.customer).data
        return None


class LoanRejectedSerializer(serializers.ModelSerializer):
    customer = CustomerDetailSerializer(read_only=True)
    class Meta:
        model = LoanApplication
        fields = '__all__'

class LoanApprovedSerializer(serializers.ModelSerializer):
    customer = CustomerDetailSerializer(read_only= True)

    class Meta:
        model = LoanApplication
        fields = '__all__'
    
class LoanTenureSerializer(serializers.ModelSerializer):
    class Meta: 
        model = LoanTenure
        fields = '__all__'
class LoanApplicationDetailSerializer(serializers.ModelSerializer):
    document_requests = DocumentRequestSerializer(many=True, read_only=True)
    loans = CustomerLoanDetailSerializer(many=True, read_only=True)
    address = CustomerAddressSerializer(read_only=True)
    documents = CustomerDocumentSerializer(read_only=True)
    agent = AgentSerializer(read_only=True)
    tenure = LoanTenureSerializer(read_only=True)
    class Meta:
        model = CustomerDetail
        fields = '__all__' 


class LoanApplicationSerializer(serializers.ModelSerializer):
    loans = CustomerLoanDetailSerializer(many=True, read_only=True)
    class Meta:
        model = CustomerDetail
        fields = '__all__' 

class LoanApplicationListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    customer_id = serializers.CharField(source='customer.customer_id', read_only=True)
    loans = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    emi_assigned_to_agent = serializers.SerializerMethodField()

    class Meta:
        model = LoanApplication
        fields = [
            'loan_ref_no', 'customer_id', 'full_name', 'status', 'submitted_at', 'loans', 'agent', 'emi_assigned_to_agent'
        ]

    def get_full_name(self, obj):
        """Reusing the same logic as detailed serializer"""
        customer_snapshot = getattr(obj, 'customer_snapshot', None)
        if hasattr(obj, 'customer_snapshot') and obj.customer_snapshot:
            customer_details = customer_snapshot.get('customer_details', {})
            full_name = customer_details.get('full_name', {})
            if customer_details:
                is_old_loan = (
                    obj.customer.loan_application_id != obj.loan_ref_no
                )
                if is_old_loan:
                    return full_name

        return obj.customer.full_name if hasattr(obj, 'customer') and obj.customer else None

    def get_loans(self, obj):
        from .models import CustomerLoanDetail
        loans = CustomerLoanDetail.objects.filter(loan_application=obj)
        return CustomerLoanDetailSerializer(loans, many=True).data

    def get_agent(self, obj):
        if obj.agent:
            from .serializers import AgentSerializer
            return AgentSerializer(obj.agent).data
        return None 

    def get_emi_assigned_to_agent(self, obj):
        """Return True if any EMI for this loan has an active assignment to this loan's agent."""
        from .models import EmiAgentAssign
        if not obj.agent:
            return False
        return EmiAgentAssign.objects.filter(
            agent=obj.agent,
            emi__loan_application=obj,
            is_active=True,
        ).exists()


class LoanPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanPeriod
        fields = '__all__'


class DeductionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deductions
        fields = '__all__'


class DisbursementLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisbursementLog
        fields = '__all__'


class LoanEMIScheduleSerializer(serializers.ModelSerializer):
    assigned_agent_id = serializers.SerializerMethodField()
    assigned_agent_name = serializers.SerializerMethodField()
    class Meta:
        model = LoanEMISchedule
        fields = [
            'id',
            'installment_date',
            'frequency',
            'installment_amount',
            'principal_amount',
            'interest_amount',
            'paid',
            'paid_date',
            'payment_reference',
            'is_overdue',
            'overdue_days',
            'late_fee',
            'assigned_agent_id',
            'assigned_agent_name'
        ]
        read_only_fields = fields

    def get_assigned_agent_id(self, obj):
        assignment = (
            EmiAgentAssign.objects.select_related('agent')
            .filter(emi=obj, is_active=True)
            .first()
        )
        return assignment.agent.agent_id if assignment and assignment.agent else None

    def get_assigned_agent_name(self, obj):
        assignment = (
            EmiAgentAssign.objects.select_related('agent')
            .filter(emi=obj, is_active=True)
            .first()
        )
        return assignment.agent.full_name if assignment and assignment.agent else None


class LoanDisbursedListSerializer(serializers.ModelSerializer):
    customer = CustomerDetailSerializer(read_only= True)
    loans = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    periods = serializers.SerializerMethodField()
    deductions = serializers.SerializerMethodField()
    customer_account = CustomerAccountSerializer(source='customer.account', read_only=True)
    shop = serializers.SerializerMethodField()
    shop_bank_accounts = serializers.SerializerMethodField()

    class Meta:
        model = LoanApplication
        fields = '__all__'

    def get_loans(self, obj):
        from .models import CustomerLoanDetail
        loans = CustomerLoanDetail.objects.filter(loan_application=obj).select_related('loan_category', 'tenure', 'interest_rate', 'agent', 'branch')
        return CustomerLoanDetailSerializer(loans, many=True).data

    def get_agent(self, obj):
        if obj.agent:
            from .serializers import AgentSerializer
            return AgentSerializer(obj.agent).data
        return None 
    
    def get_periods(self, obj):
        periods = LoanPeriod.objects.filter(loan_application=obj)
        return LoanPeriodSerializer(periods, many=True).data

    def get_deductions(self, obj):
        # deductions = Deductions.objects.all()
        loans = self.get_loans(obj)
        main_category = loans[0].get('loan_category').get('main_category') if loans else None
        deductions = Deductions.objects.filter(main_category = main_category, created_by = obj.branch.created_by)
        return DeductionSerializer(deductions, many=True).data

    def get_shop(self, obj):
        if getattr(obj, 'shop', None):
            return {
                'shop_id': obj.shop.shop_id,
                'name': obj.shop.name,
            }
        return None

    def get_shop_bank_accounts(self, obj):
        shop = getattr(obj, 'shop', None)
        if not shop:
            return []

        from .models import ShopBankAccount
        accounts = ShopBankAccount.objects.filter(shop=shop).order_by('-is_primary', '-created_at')
        return [
            {
                'bank_account_id': a.bank_account_id,
                'bank_name': a.bank_name,
                'account_number': a.account_number,
                'account_holder_name': a.account_holder_name,
                'ifsc_code': a.ifsc_code,
                'upi_id': a.upi_id,
                'is_primary': a.is_primary,
            }
            for a in accounts
        ]


class EMICollectSerializer(serializers.ModelSerializer):
    loan_ref_no = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    can_collect = serializers.SerializerMethodField()

    class Meta:
        model = EmiAgentAssign
        fields = '__all__'

    def get_loan_ref_no(self, obj):
        try:
            emi_obj = obj.emi or getattr(obj, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None)
            return getattr(loan_app, 'loan_ref_no', None)
        except Exception:
            return None

    def get_customer_name(self, obj):
        try:
            emi_obj = obj.emi or getattr(obj, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None)
            customer = getattr(loan_app, 'customer', None)
            return getattr(customer, 'full_name', None)
        except Exception:
            return None

    def get_branch_name(self, obj):
        try:
            manager = obj.assigned_by
            branch = manager.branch if manager else None
            if branch and getattr(branch, 'branch_name', None):
                return branch.branch_name
            # Fallback to loan application's branch if assigned_by or branch is missing
            emi_obj = obj.emi or getattr(obj, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None)
            la_branch = getattr(loan_app, 'branch', None)
            return getattr(la_branch, 'branch_name', None)
        except Exception:
            return None

    def get_can_collect(self, obj):
        """Return True only if the immediately previous EMI for this loan is verified.

        Rules (original EMIs):
        - First EMI for a loan (no previous schedule) can always be collected.
        - For later EMIs, look up the previous LoanEMISchedule for the same
          loan (by installment_date then id) and check its latest collection
          record. The next EMI is collectable only when that previous
          collection has status = 'verified'.

        For rescheduled EMIs we apply the same rule but using
        LoanEMIReschedule and EmiCollectionDetail.reschedule_emi so that the
        next rescheduled EMI is only enabled after the previous one is
        verified by branch.
        """

        # 1) Handle normal (LoanEMISchedule-based) assignments
        emi = getattr(obj, 'emi', None)
        if emi is not None:
            loan_app = getattr(emi, 'loan_application', None)
            if not loan_app:
                return True

            prev_emi = (
                LoanEMISchedule.objects
                .filter(loan_application=loan_app)
                .filter(
                    Q(installment_date__lt=emi.installment_date) |
                    Q(installment_date=emi.installment_date, id__lt=emi.id)
                )
                .order_by('-installment_date', '-id')
                .first()
            )

            if not prev_emi:
                return True

            last_prev_collection = (
                EmiCollectionDetail.objects
                .filter(emi=prev_emi)
                .order_by('-collected_at')
                .first()
            )

            if not last_prev_collection:
                return False

            return last_prev_collection.status == 'verified'

        # 2) Handle rescheduled EMI assignments (LoanEMIReschedule)
        res_emi = getattr(obj, 'reschedule_emi', None)
        if res_emi is not None:
            from .models import LoanEMIReschedule  # local import to avoid circulars

            # Reschedule collectability should be evaluated **within the same
            # reschedule plan** only. EMIs from older reschedule plans for the
            # same loan must not block collection in a newer plan.
            prev_res_emi = (
                LoanEMIReschedule.objects
                .filter(reschedule_log=res_emi.reschedule_log)
                .filter(
                    Q(installment_date__lt=res_emi.installment_date) |
                    Q(installment_date=res_emi.installment_date, id__lt=res_emi.id)
                )
                .order_by('-installment_date', '-id')
                .first()
            )

            if not prev_res_emi:
                return True

            last_prev_res_collection = (
                EmiCollectionDetail.objects
                .filter(reschedule_emi=prev_res_emi)
                .order_by('-collected_at')
                .first()
            )

            if not last_prev_res_collection:
                return False

            return last_prev_res_collection.status == 'verified'

        # If neither emi nor reschedule_emi is present, do not block collection here.
        return True