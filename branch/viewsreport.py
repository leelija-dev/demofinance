from django.db import models
from django.views.generic import TemplateView
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse

from .models import BranchEmployee
from agent.models import Agent
from datetime import datetime
from django.db.models import Q
from django.db.models import Sum
from decimal import Decimal

from django.utils.decorators import method_decorator
from .decorators import branch_permission_required


####---------------------------------####
      # Daily Reports and Payments #
####---------------------------------####
@method_decorator(branch_permission_required('view_reports', 'export_reports'), name='dispatch')
class DailyReceiptsPaymentsView(TemplateView):
    template_name = 'report/dailyReceipt-payment.html'

    def dispatch(self, request, *args, **kwargs):
        """Ensure only logged-in branch employees can access this view.

        Uses the same session-based branch authentication pattern as
        BranchDashboardView so that unauthenticated users are redirected
        to the branch login page instead of the HQ login.
        """
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        try:
            branch_employee = BranchEmployee.objects.get(
                id=logged_user_id,
                is_active=True,
            )
        except BranchEmployee.DoesNotExist:
            request.session.flush()
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        request.branch_employee = branch_employee
        request.branch_manager = branch_employee
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_export'] = (
            self.request.branch_employee.is_manager or 
            self.request.branch_employee.has_perm('export_reports')
        )
        request = self.request

        # 1) Get logged-in branch manager and branch
        logged_user_id = request.session.get('logged_user_id')
        branch_employee = None
        branch = None
        if logged_user_id:
            try:
                branch_employee = BranchEmployee.objects.get(id=logged_user_id)
                branch = branch_employee.branch
            except BranchEmployee.DoesNotExist:
                branch = None

        # 2) Basic filters from GET
        from_date_str = request.GET.get('from_date')
        to_date_str = request.GET.get('to_date')
        collector_id = request.GET.get('collector')  # agent_id
        product_filter = request.GET.get('product')  # 'daily' / 'weekly' / None

        # Default period: today
        today = timezone.localdate()
        if from_date_str:
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            except ValueError:
                from_date = today
        else:
            from_date = today

        if to_date_str:
            try:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            except ValueError:
                to_date = today
        else:
            to_date = today

        # 3) Collector list (for dropdown) - agents of this branch (kept for future use)
        collectors_qs = Agent.objects.none()
        if branch:
            collectors_qs = Agent.objects.filter(branch=branch, status='active').order_by('full_name')
        context['collectors'] = collectors_qs
        context['collector_id'] = collector_id

        # 4) Build data from EmiCollectionDetail (EMI collections)
        from loan.models import EmiCollectionDetail
        from loan.models import LoanEMISchedule
        from savings.models import SavingsCollection

        rows = []
        totals = {
            'installment': Decimal('0'),
            'lpf': Decimal('0'),
            'saving': Decimal('0'),
            'others': Decimal('0'),
            'total': Decimal('0'),
            'disbursed': Decimal('0'),  # placeholder for now
        }

        if branch:
            collections = EmiCollectionDetail.objects.select_related(
                'collected_by_agent', 'collected_by_branch', 'emi', 'reschedule_emi', 'loan_application'
            ).filter(
                loan_application__branch=branch,
                status__in=['verified'],
                collected=True,
            ).filter(
                Q(verified_at__date__gte=from_date, verified_at__date__lte=to_date) |
                Q(verified_at__isnull=True, collected_at__date__gte=from_date, collected_at__date__lte=to_date)
            ).exclude(
                collected_by_agent__isnull=True,
                collected_by_branch__isnull=True,
            )

            # Optional filter: if collector_id passed, limit to that collector
            # First try agent_id, then branch employee id
            if collector_id:
                collections = collections.filter(
                    models.Q(collected_by_agent__agent_id=collector_id) |
                    models.Q(collected_by_branch__employee_id=collector_id)
                )

            # Aggregate per collector (agent or branch employee) and frequency (daily/weekly)
            per_collector = {}
            loan_freq_cache = {}

            for col in collections:
                collector_name = None
                collector_key = None
                collector_identity = None
                collector_code = None

                if col.collected_by_agent:
                    collector = col.collected_by_agent
                    collector_name = collector.full_name
                    collector_key = f"agent:{collector.agent_id}"
                    collector_identity = 'Agent'
                    collector_code = collector.agent_id
                elif col.collected_by_branch:
                    collector = col.collected_by_branch
                    collector_name = collector.get_full_name()
                    collector_key = f"branch:{collector.employee_id}"
                    collector_identity = 'Branch Employee'
                    collector_code = collector.employee_id
                else:
                    continue

                # Determine frequency from related EMI / reschedule EMI
                freq = None
                if col.emi and col.emi.frequency:
                    freq = col.emi.frequency
                elif col.reschedule_emi and col.reschedule_emi.frequency:
                    freq = col.reschedule_emi.frequency

                if not freq and col.loan_application_id:
                    loan_key = col.loan_application_id
                    freq = loan_freq_cache.get(loan_key)
                    if freq is None:
                        freq = (
                            LoanEMISchedule.objects
                            .filter(loan_application_id=loan_key)
                            .order_by('installment_date')
                            .values_list('frequency', flat=True)
                            .first()
                        )
                        loan_freq_cache[loan_key] = freq

                if freq not in ['daily', 'weekly']:
                    continue

                if collector_key not in per_collector:
                    per_collector[collector_key] = {
                        'collector_name': collector_name,
                        'collector_identity': collector_identity,
                        'collector_code': collector_code,
                        'daily_installment': Decimal('0'),
                        'weekly_installment': Decimal('0'),
                        'saving': Decimal('0'),
                        'others': Decimal('0'),
                        'daily_disbursed': Decimal('0'),
                        'weekly_disbursed': Decimal('0'),
                        'daily_lpf': Decimal('0'),
                        'weekly_lpf': Decimal('0'),
                    }

                data = per_collector[collector_key]

                # For this report, the installment amount should include any
                # penalty_received recorded on the EmiCollectionDetail.
                installment_component = (Decimal(col.amount_received or 0) + Decimal(col.penalty_received or 0))

                if freq == 'daily':
                    data['daily_installment'] += installment_component
                elif freq == 'weekly':
                    data['weekly_installment'] += installment_component

            # --- Savings collections (RD/FD) per collector ---
            # Include savings collections done by agents or branch employees in the period.
            savings_qs = SavingsCollection.objects.filter(
                account__branch=branch,
                is_collected=True,
            ).filter(
                Q(collected_by_agent__isnull=False) | Q(collected_by_branch_employee__isnull=False)
            ).filter(
                Q(is_deposited_to_branch=True, deposited_at__date__gte=from_date, deposited_at__date__lte=to_date) |
                Q(Q(is_deposited_to_branch=False) | Q(deposited_at__isnull=True), collection_date__gte=from_date, collection_date__lte=to_date)
            )

            savings_qs = savings_qs.exclude(collection_type='withdrawal')

            if collector_id:
                savings_qs = savings_qs.filter(
                    Q(collected_by_agent__agent_id=collector_id) |
                    Q(collected_by_branch_employee__employee_id=collector_id)
                )

            savings_agent_rows = (
                savings_qs.filter(collected_by_agent__isnull=False)
                .values('collected_by_agent__agent_id', 'collected_by_agent__full_name')
                .annotate(total=Sum('amount'))
            )
            for r in savings_agent_rows:
                agent_id = r.get('collected_by_agent__agent_id')
                if not agent_id:
                    continue
                collector_key = f"agent:{agent_id}"
                if collector_key not in per_collector:
                    per_collector[collector_key] = {
                        'collector_name': r.get('collected_by_agent__full_name') or agent_id,
                        'collector_identity': 'Agent',
                        'collector_code': agent_id,
                        'daily_installment': Decimal('0'),
                        'weekly_installment': Decimal('0'),
                        'saving': Decimal('0'),
                        'others': Decimal('0'),
                        'daily_disbursed': Decimal('0'),
                        'weekly_disbursed': Decimal('0'),
                        'daily_lpf': Decimal('0'),
                        'weekly_lpf': Decimal('0'),
                    }
                per_collector[collector_key]['saving'] += (r.get('total') or Decimal('0'))

            savings_branch_rows = (
                savings_qs.filter(collected_by_branch_employee__isnull=False)
                .values(
                    'collected_by_branch_employee__employee_id',
                    'collected_by_branch_employee__first_name',
                    'collected_by_branch_employee__last_name',
                )
                .annotate(total=Sum('amount'))
            )
            for r in savings_branch_rows:
                emp_id = r.get('collected_by_branch_employee__employee_id')
                if not emp_id:
                    continue
                collector_key = f"branch:{emp_id}"
                full_name = (f"{r.get('collected_by_branch_employee__first_name') or ''} {r.get('collected_by_branch_employee__last_name') or ''}").strip() or emp_id
                if collector_key not in per_collector:
                    per_collector[collector_key] = {
                        'collector_name': full_name,
                        'collector_identity': 'Branch Employee',
                        'collector_code': emp_id,
                        'daily_installment': Decimal('0'),
                        'weekly_installment': Decimal('0'),
                        'saving': Decimal('0'),
                        'others': Decimal('0'),
                        'daily_disbursed': Decimal('0'),
                        'weekly_disbursed': Decimal('0'),
                        'daily_lpf': Decimal('0'),
                        'weekly_lpf': Decimal('0'),
                    }
                per_collector[collector_key]['saving'] += (r.get('total') or Decimal('0'))

            # --- Disbursement amounts per branch employee and frequency ---
            # Disbursements are logged via BranchTransaction -> DisbursementLog.
            from branch.models import BranchTransaction
            from loan.models import LoanEMISchedule

            # Cache loan frequency to avoid repeated queries
            loan_freq_cache = {}
            # Track which (loan, employee) pairs have already been counted
            seen_disbursements = set()

            disb_qs = BranchTransaction.objects.select_related(
                'disbursement_log', 'created_by', 'disbursement_log__loan_id'
            ).filter(
                branch=branch,
                disbursement_log__isnull=False,
                transaction_date__date__gte=from_date,
                transaction_date__date__lte=to_date,
            )

            for bt in disb_qs:
                emp = bt.created_by
                disb_log = bt.disbursement_log
                if not emp or not disb_log:
                    continue

                loan = disb_log.loan_id
                if not loan:
                    continue

                # Skip duplicate disbursement logs for the same loan and employee
                pair_key = (loan.loan_ref_no, emp.employee_id)
                if pair_key in seen_disbursements:
                    continue
                seen_disbursements.add(pair_key)

                # Determine frequency for this loan (daily/weekly) using first EMI schedule
                loan_key = loan.loan_ref_no
                freq = loan_freq_cache.get(loan_key)
                if freq is None:
                    freq = (
                        LoanEMISchedule.objects
                        .filter(loan_application=loan)
                        .order_by('installment_date')
                        .values_list('frequency', flat=True)
                        .first()
                    )
                    loan_freq_cache[loan_key] = freq

                if freq not in ['daily', 'weekly']:
                    continue

                collector_name = emp.get_full_name()
                collector_key = f"branch:{emp.employee_id}"
                collector_identity = 'Branch Employee'
                collector_code = emp.employee_id

                if collector_key not in per_collector:
                    per_collector[collector_key] = {
                        'collector_name': collector_name,
                        'collector_identity': collector_identity,
                        'collector_code': collector_code,
                        'daily_installment': Decimal('0'),
                        'weekly_installment': Decimal('0'),
                        'saving': Decimal('0'),
                        'others': Decimal('0'),
                        'daily_disbursed': Decimal('0'),
                        'weekly_disbursed': Decimal('0'),
                        'daily_lpf': Decimal('0'),
                        'weekly_lpf': Decimal('0'),
                    }

                data = per_collector[collector_key]

                amount = Decimal(disb_log.amount or 0)
                lpf = Decimal(getattr(disb_log, 'tax_charges', 0) or 0)

                if freq == 'daily':
                    data['daily_disbursed'] += amount
                    data['daily_lpf'] += lpf
                elif freq == 'weekly':
                    data['weekly_disbursed'] += amount
                    data['weekly_lpf'] += lpf

            # Build rows for template (one row per collector x product)
            for collector_key, data in per_collector.items():
                collector_name = data['collector_name']
                collector_identity = data.get('collector_identity') or 'Collector'
                collector_code = data.get('collector_code')

                # Daily product row
                if not product_filter or product_filter == 'daily':
                    installment = data['daily_installment']
                    # Avoid double counting savings when showing both Daily + Weekly rows.
                    saving = data['saving'] if not product_filter else data['saving']
                    others = data['others']
                    disbursed = data['daily_disbursed']
                    lpf = data['daily_lpf']
                    total = installment + lpf + saving + others

                    rows.append({
                        'collector_name': collector_name,
                        'collector_identity': collector_identity,
                        'collector_code': collector_code,
                        'product_label': 'Daily',
                        'installment_amount': installment,
                        'lpf_amount': lpf,
                        'saving_amount': saving,
                        'others_amount': others,
                        'total_amount': total,
                        'disbursed_amount': disbursed,
                    })

                    totals['installment'] += installment
                    totals['saving'] += saving
                    totals['others'] += others
                    totals['lpf'] += lpf
                    totals['total'] += total
                    totals['disbursed'] += disbursed

                # Weekly product row
                if not product_filter or product_filter == 'weekly':
                    installment = data['weekly_installment']
                    # Savings is not frequency-based here, show it only once (on Daily row) when no filter is applied.
                    saving = Decimal('0') if not product_filter else data['saving']
                    others = data['others']
                    disbursed = data['weekly_disbursed']
                    lpf = data['weekly_lpf']
                    total = installment + lpf + saving + others

                    rows.append({
                        'collector_name': collector_name,
                        'collector_identity': collector_identity,
                        'collector_code': collector_code,
                        'product_label': 'Weekly',
                        'installment_amount': installment,
                        'lpf_amount': lpf,
                        'saving_amount': saving,
                        'others_amount': others,
                        'total_amount': total,
                        'disbursed_amount': disbursed,
                    })

                    totals['installment'] += installment
                    totals['saving'] += saving
                    totals['others'] += others
                    totals['lpf'] += lpf
                    totals['total'] += total
                    totals['disbursed'] += disbursed

        # --- Expense summary (Expen-Head / Bank / Cash) from BranchTransaction ---
        expense_rows = []
        expense_totals = {
            'bank': 0,
            'cash': 0,
        }

        if branch:
            # Only treat BranchTransaction debits as expenses if their code
            # belongs to ChartOfAccount entries with main_type = 'C'
            from loan.models import ChartOfAccount

            expense_codes = list(
                ChartOfAccount.objects.filter(main_type='C').values_list('code', flat=True)
            )

            # Also always treat specific additional codes as expenses, even if
            # they are not under main_type = 'C' in the chart of accounts.
            for extra_code in ['130', '131', '132', '133', '134', '144']:
                if extra_code not in expense_codes:
                    expense_codes.append(extra_code)

            expense_qs = BranchTransaction.objects.filter(
                branch=branch,
                transaction_type='DEBIT',
                code__in=expense_codes,
                transaction_date__date__gte=from_date,
                transaction_date__date__lte=to_date,
            ).exclude(code__in=['120', '121', '122', '123', '203', '206'])

            per_purpose = {}
            for bt in expense_qs:
                purpose = bt.purpose or 'Unknown'
                mode = (bt.mode or '').upper()
                amount = bt.amount or 0

                if amount == 0:
                    continue

                if purpose not in per_purpose:
                    per_purpose[purpose] = {
                        'bank': 0,
                        'cash': 0,
                    }

                bucket = per_purpose[purpose]

                if mode == 'BANK':
                    bucket['bank'] += amount
                    expense_totals['bank'] += amount
                elif mode == 'CASH':
                    bucket['cash'] += amount
                    expense_totals['cash'] += amount
                else:
                    # If mode is not clearly bank/cash, ignore for this summary
                    continue

            # Convert per_purpose into rows list
            for purpose, data in per_purpose.items():
                expense_rows.append({
                    'exp_head': purpose,
                    'bank_amount': data['bank'],
                    'cash_amount': data['cash'],
                })

            # Optional: sort by purpose for stable display
            expense_rows.sort(key=lambda r: r['exp_head'])

        # --- Opening / Closing balance summary (cash & bank) + "Add" / "Less" sections ---
        fund_opening_cash = 0
        fund_opening_bank = 0
        fund_closing_cash = 0
        fund_closing_bank = 0

        # "Add" buckets used by the summary table
        fund_add_loan_cash = 0
        fund_add_loan_bank = 0
        fund_add_collection_cash = 0
        fund_add_collection_bank = 0
        fund_add_fd_cash = 0
        fund_add_fd_bank = 0
        fund_add_withdraw_cash = 0
        fund_add_withdraw_bank = 0
        # Per user request, the 'Add -> Others' summary row should always be 0
        # in the report, so keep these at 0 regardless of underlying data.
        fund_add_others_cash = 0
        fund_add_others_bank = 0

        # "Less" buckets used by the summary table
        fund_less_disbursement_cash = 0
        fund_less_disbursement_bank = 0
        fund_less_expenses_cash = 0
        fund_less_expenses_bank = 0
        fund_less_loanrepay_cash = 0
        fund_less_loanrepay_bank = 0
        fund_less_saving_return_cash = 0
        fund_less_saving_return_bank = 0
        fund_less_interest_saving_cash = 0
        fund_less_interest_saving_bank = 0
        fund_less_deposit_bank_cash = 0
        fund_less_deposit_bank_bank = 0
        fund_less_others_cash = 0
        fund_less_others_bank = 0

        if branch:
            from branch.models import BranchAccount

            # Closing balances from BranchAccount (current balances)
            cash_closing = (
                BranchAccount.objects
                .filter(branch=branch, type='CASH')
                .aggregate(total=models.Sum('current_balance'))['total']
                or 0
            )
            bank_closing = (
                BranchAccount.objects
                .filter(branch=branch, type='BANK')
                .aggregate(total=models.Sum('current_balance'))['total']
                or 0
            )

            # Net movement in the selected period from BranchTransaction
            movement_cash = 0
            movement_bank = 0

            tx_qs = BranchTransaction.objects.select_related('branch_account').filter(
                branch=branch,
                transaction_date__date__gte=from_date,
                transaction_date__date__lte=to_date,
            )

            fund_add_205_rows = []

            for bt in tx_qs:
                amount = bt.amount or 0
                account = bt.branch_account
                if not account or amount == 0:
                    continue

                is_cash_acct = account.type == 'CASH'
                is_bank_acct = account.type == 'BANK'

                # Movement for opening/closing calculation
                if is_cash_acct:
                    if bt.transaction_type == 'CREDIT':
                        movement_cash += amount
                    elif bt.transaction_type == 'DEBIT':
                        movement_cash -= amount
                elif is_bank_acct:
                    if bt.transaction_type == 'CREDIT':
                        movement_bank += amount
                    elif bt.transaction_type == 'DEBIT':
                        movement_bank -= amount

                # Classification for "Add" / "Less" sections (excluding HQ
                # funds, which are taken directly from FundTransfers below)
                code = (bt.code or '').strip()

                # Collection for the day (daily/weekly EMI + saving: 122, 123, 204)
                # Also treat agent cash/online deposits as part of collection so that
                # the summary matches the collector-wise table.
                if bt.transaction_type == 'CREDIT' and code in ['122', '123', '204']:
                    purpose_norm = (bt.purpose or '').strip().lower()
                    is_fd_deposit = False
                    if code == '204':
                        if purpose_norm in [
                            'savings fd deposit (application)',
                            'savings fd deposit',
                        ]:
                            is_fd_deposit = True

                    if is_fd_deposit:
                        if is_cash_acct:
                            fund_add_fd_cash += amount
                        elif is_bank_acct:
                            fund_add_fd_bank += amount
                    else:
                        if is_cash_acct:
                            fund_add_collection_cash += amount
                        elif is_bank_acct:
                            fund_add_collection_bank += amount
                elif (
                    bt.transaction_type == 'CREDIT'
                    and (bt.purpose or '').strip().lower() == 'agent deposit - online'
                    and is_bank_acct
                ):
                    fund_add_collection_bank += amount
                elif (
                    bt.transaction_type == 'CREDIT'
                    and (bt.purpose or '').strip().lower() == 'agent deposit - cash'
                    and is_cash_acct
                ):
                    fund_add_collection_cash += amount

                # Fixed deposit for the day – intentionally left unmapped (kept as 0)

                # Codes 201, 202, 205, 206, 207, 208 – group under Add
                # section dynamically by (code, purpose).
                if bt.transaction_type == 'CREDIT' and code in ['201', '202', '205', '206', '207', '208']:
                    purpose = bt.purpose or 'Unknown'
                    key_205 = (code, purpose)
                    if 'fund_add_dynamic_per_key' not in locals():
                        fund_add_dynamic_per_key = {}
                    bucket_205 = fund_add_dynamic_per_key.setdefault(key_205, {
                        'code': code,
                        'purpose': purpose,
                        'cash': 0,
                        'bank': 0,
                    })

                    if is_cash_acct:
                        bucket_205['cash'] += amount
                    elif is_bank_acct:
                        bucket_205['bank'] += amount

                # Withdrawal from Bank (Add section): treat DEBIT transactions
                # made via bank/online as cash inflow in the 'Withdrawal from
                # Bank' row, shown under the Cash column. The same amount is
                # mirrored in the 'Deposit to Bank' Less row under the Bank
                # column to keep the movement balanced.
                #
                # IMPORTANT: Debits that are classified as expenses (i.e. their
                # code is in expense_codes used for the Expense summary) must
                # NOT be treated as withdrawals/deposits here, otherwise they
                # would be double-counted.
                tx_mode = (bt.mode or '').strip().lower()
                if (
                    bt.transaction_type == 'DEBIT'
                    and is_bank_acct
                    and tx_mode in ['BANK', 'bank', 'Online', 'online']
                    and (code not in expense_codes)
                ):
                    fund_add_withdraw_cash += amount
                    fund_less_deposit_bank_bank += amount

                # Disbursement for the day (loan disbursements). We use
                # BranchTransaction rows linked to a disbursement_log.
                if bt.transaction_type == 'DEBIT' and bt.disbursement_log_id:
                    if is_cash_acct:
                        fund_less_disbursement_cash += amount
                    elif is_bank_acct:
                        fund_less_disbursement_bank += amount

                # Loan fund re-payment (Less section): BranchTransaction with
                # code '203' and DEBIT should reduce funds under the
                # 'Loan fund re-payment' row instead of being treated as
                # general expenses.
                if bt.transaction_type == 'DEBIT' and code == '203':
                    if is_cash_acct:
                        fund_less_loanrepay_cash += amount
                    elif is_bank_acct:
                        fund_less_loanrepay_bank += amount

                # Saving return (Less section): Savings Withdraw/Close is logged
                # as a DEBIT BranchTransaction with code 206.
                if bt.transaction_type == 'DEBIT' and code == '206':
                    if is_cash_acct:
                        fund_less_saving_return_cash += amount
                    elif is_bank_acct:
                        fund_less_saving_return_bank += amount

                # Expenses for the day are handled separately via expense_totals

                # Others (any other CREDIT not classified above)
                # NOTE: We intentionally do NOT accumulate these into
                # fund_add_others_* because the summary row must show 0.
                # The detailed rows table can still reflect the raw data.
                elif bt.transaction_type == 'CREDIT':
                    pass

            fund_closing_cash = cash_closing
            fund_closing_bank = bank_closing

            # Opening = Closing - net movement during the selected period
            fund_opening_cash = fund_closing_cash - movement_cash
            fund_opening_bank = fund_closing_bank - movement_bank

            # Build dynamic Add rows for codes 201/202/205/206/207/208
            # grouped by (code, purpose)
            if 'fund_add_dynamic_per_key' in locals():
                for (code_val, purpose), data in fund_add_dynamic_per_key.items():
                    total = (data.get('cash') or 0) + (data.get('bank') or 0)
                    fund_add_205_rows.append({
                        'code': code_val,
                        'purpose': purpose,
                        'cash_amount': data.get('cash') or 0,
                        'bank_amount': data.get('bank') or 0,
                        'total_amount': total,
                    })

        # Loan fund received summary: use BranchTransaction entries where
        # code = '203' and transaction_type = 'CREDIT', split by cash/bank.
        if branch:
            loan_fund_qs = BranchTransaction.objects.select_related('branch_account').filter(
                branch=branch,
                transaction_type='CREDIT',
                code='203',
                transaction_date__date__gte=from_date,
                transaction_date__date__lte=to_date,
            )

            # Reset loan buckets to ensure we only count these specific
            # BranchTransaction records.
            fund_add_loan_cash = 0
            fund_add_loan_bank = 0

            for bt in loan_fund_qs:
                amount = bt.amount or 0
                if amount == 0:
                    continue

                acct = bt.branch_account
                if not acct:
                    continue

                if acct.type == 'CASH':
                    fund_add_loan_cash += amount
                elif acct.type == 'BANK':
                    fund_add_loan_bank += amount

        # Add LPF from collector-wise totals into Collection for the day (cash)
        # so that the summary matches the detailed table where LPF is part
        # of the collection total.
        extra_lpf = totals.get('lpf', 0) or 0
        fund_add_collection_cash += extra_lpf

        # Totals for Add section rows
        fund_add_loan_total = fund_add_loan_cash + fund_add_loan_bank
        fund_add_collection_total = fund_add_collection_cash + fund_add_collection_bank
        fund_add_fd_total = fund_add_fd_cash + fund_add_fd_bank
        fund_add_withdraw_total = fund_add_withdraw_cash + fund_add_withdraw_bank

        # Dynamic Add rows (codes 201/202/205/206/207/208) should also
        # contribute to Total Fund available. Aggregate their cash/bank
        # components here.
        fund_add_dynamic_cash = 0
        fund_add_dynamic_bank = 0
        for row in fund_add_205_rows:
            fund_add_dynamic_cash += row.get('cash_amount') or 0
            fund_add_dynamic_bank += row.get('bank_amount') or 0
        fund_add_dynamic_total = fund_add_dynamic_cash + fund_add_dynamic_bank

        # 'Add -> Others' totals are explicitly fixed to 0 for the summary
        fund_add_others_total = 0

        # Map expense_totals into "Expenses for the day" Less bucket
        fund_less_expenses_bank = expense_totals.get('bank', 0) or 0
        fund_less_expenses_cash = expense_totals.get('cash', 0) or 0

        # Totals for Less section rows
        fund_less_disbursement_total = fund_less_disbursement_cash + fund_less_disbursement_bank
        fund_less_expenses_total = fund_less_expenses_cash + fund_less_expenses_bank
        fund_less_loanrepay_total = fund_less_loanrepay_cash + fund_less_loanrepay_bank
        fund_less_saving_return_total = fund_less_saving_return_cash + fund_less_saving_return_bank
        fund_less_interest_saving_total = fund_less_interest_saving_cash + fund_less_interest_saving_bank
        fund_less_deposit_bank_total = fund_less_deposit_bank_cash + fund_less_deposit_bank_bank
        fund_less_others_total = fund_less_others_cash + fund_less_others_bank

        # Total Payment = sum of all Less items
        fund_total_payment_cash = (
            fund_less_disbursement_cash
            + fund_less_expenses_cash
            + fund_less_loanrepay_cash
            + fund_less_saving_return_cash
            + fund_less_interest_saving_cash
            + fund_less_deposit_bank_cash
            + fund_less_others_cash
        )
        fund_total_payment_bank = (
            fund_less_disbursement_bank
            + fund_less_expenses_bank
            + fund_less_loanrepay_bank
            + fund_less_saving_return_bank
            + fund_less_interest_saving_bank
            + fund_less_deposit_bank_bank
            + fund_less_others_bank
        )
        fund_total_payment_total = fund_total_payment_cash + fund_total_payment_bank

        # Total Fund available = Opening balance + all Add items
        fund_total_available_cash = (
            (fund_opening_cash or 0)
            + (fund_add_loan_cash or 0)
            + (fund_add_collection_cash or 0)
            + (fund_add_fd_cash or 0)
            + (fund_add_withdraw_cash or 0)
            + (fund_add_dynamic_cash or 0)
            # 'Add -> Others' is excluded from Total Fund available,
            # because it must display as 0 in the summary.
        )
        fund_total_available_bank = (
            (fund_opening_bank or 0)
            + (fund_add_loan_bank or 0)
            + (fund_add_collection_bank or 0)
            + (fund_add_fd_bank or 0)
            + (fund_add_withdraw_bank or 0)
            + (fund_add_dynamic_bank or 0)
            # 'Add -> Others' is excluded from Total Fund available,
            # because it must display as 0 in the summary.
        )
        fund_total_available_total = fund_total_available_cash + fund_total_available_bank

        # Closing balance for the selected date range, as shown in the
        # summary table, should follow the accounting identity:
        # Closing = Opening + Add - Less  =>  Closing = TotalAvailable - TotalPayment
        fund_closing_cash_display = fund_total_available_cash - fund_total_payment_cash
        fund_closing_bank_display = fund_total_available_bank - fund_total_payment_bank
        fund_closing_total_display = fund_closing_cash_display + fund_closing_bank_display

        context['rows'] = rows
        context['totals'] = totals
        context['expense_rows'] = expense_rows
        context['expense_totals'] = expense_totals
        context['from_date'] = from_date
        context['to_date'] = to_date
        context['product'] = product_filter

        # Values used by the summary table in dailyReceipt-payment.html
        context['fund_opening_cash'] = fund_opening_cash
        context['fund_opening_bank'] = fund_opening_bank
        context['fund_opening_total'] = (fund_opening_cash or 0) + (fund_opening_bank or 0)
        context['fund_opening_remarks'] = ''

        # Use the date-range-based closing values for the summary row
        context['fund_closing_cash'] = fund_closing_cash_display
        context['fund_closing_bank'] = fund_closing_bank_display
        context['fund_closing_total'] = fund_closing_total_display
        context['fund_closing_remarks'] = ''

        # Total Fund available row
        context['fund_total_available_cash'] = fund_total_available_cash
        context['fund_total_available_bank'] = fund_total_available_bank
        context['fund_total_available_total'] = fund_total_available_total
        context['fund_total_available_remarks'] = ''

        # Dynamic Add rows for code 205
        context['fund_add_205_rows'] = fund_add_205_rows

        # Add section values
        context['fund_add_loan_cash'] = fund_add_loan_cash
        context['fund_add_loan_bank'] = fund_add_loan_bank
        context['fund_add_loan_total'] = fund_add_loan_total
        context['fund_add_loan_remarks'] = ''

        context['fund_add_collection_cash'] = fund_add_collection_cash
        context['fund_add_collection_bank'] = fund_add_collection_bank
        context['fund_add_collection_total'] = fund_add_collection_total
        context['fund_add_collection_remarks'] = ''

        context['fund_add_fd_cash'] = fund_add_fd_cash
        context['fund_add_fd_bank'] = fund_add_fd_bank
        context['fund_add_fd_total'] = fund_add_fd_total
        context['fund_add_fd_remarks'] = ''

        context['fund_add_withdraw_cash'] = fund_add_withdraw_cash
        context['fund_add_withdraw_bank'] = fund_add_withdraw_bank
        context['fund_add_withdraw_total'] = fund_add_withdraw_total
        context['fund_add_withdraw_remarks'] = ''

        context['fund_add_others_cash'] = fund_add_others_cash
        context['fund_add_others_bank'] = fund_add_others_bank
        context['fund_add_others_total'] = fund_add_others_total
        context['fund_add_others_remarks'] = ''

        # Less section values
        context['fund_less_disbursement_cash'] = fund_less_disbursement_cash
        context['fund_less_disbursement_bank'] = fund_less_disbursement_bank
        context['fund_less_disbursement_total'] = fund_less_disbursement_total
        context['fund_less_disbursement_remarks'] = ''

        context['fund_less_expenses_cash'] = fund_less_expenses_cash
        context['fund_less_expenses_bank'] = fund_less_expenses_bank
        context['fund_less_expenses_total'] = fund_less_expenses_total
        context['fund_less_expenses_remarks'] = ''

        context['fund_less_loanrepay_cash'] = fund_less_loanrepay_cash
        context['fund_less_loanrepay_bank'] = fund_less_loanrepay_bank
        context['fund_less_loanrepay_total'] = fund_less_loanrepay_total
        context['fund_less_loanrepay_remarks'] = ''

        context['fund_less_saving_return_cash'] = fund_less_saving_return_cash
        context['fund_less_saving_return_bank'] = fund_less_saving_return_bank
        context['fund_less_saving_return_total'] = fund_less_saving_return_total
        context['fund_less_saving_return_remarks'] = ''

        context['fund_less_interest_saving_cash'] = fund_less_interest_saving_cash
        context['fund_less_interest_saving_bank'] = fund_less_interest_saving_bank
        context['fund_less_interest_saving_total'] = fund_less_interest_saving_total
        context['fund_less_interest_saving_remarks'] = ''

        context['fund_less_deposit_bank_cash'] = fund_less_deposit_bank_cash
        context['fund_less_deposit_bank_bank'] = fund_less_deposit_bank_bank
        context['fund_less_deposit_bank_total'] = fund_less_deposit_bank_total
        context['fund_less_deposit_bank_remarks'] = ''

        context['fund_less_others_cash'] = fund_less_others_cash
        context['fund_less_others_bank'] = fund_less_others_bank
        context['fund_less_others_total'] = fund_less_others_total
        context['fund_less_others_remarks'] = ''

        # Total Payment row
        context['fund_total_payment_cash'] = fund_total_payment_cash
        context['fund_total_payment_bank'] = fund_total_payment_bank
        context['fund_total_payment_total'] = fund_total_payment_total
        context['fund_total_payment_remarks'] = ''

        return context