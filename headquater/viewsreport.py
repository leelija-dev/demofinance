from django.views.generic import TemplateView
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from django.db.models import Q, Sum
from decimal import Decimal
from datetime import datetime

from headquater.models import Branch


####---------------------------------####
      # Daily Reports and Payments (HQ - Branch Wise) #
####---------------------------------####
class HQDailyReceiptsPaymentsView(TemplateView):
    template_name = 'hq/report/dailyReceipt-payment.html'

    def dispatch(self, request, *args, **kwargs):
        """Ensure only logged-in HQ users can access this view."""
        if not request.user.is_authenticated:
            login_url = reverse('hq:login')
            return redirect(f"{login_url}?next={request.path}")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # 1) Basic filters from GET
        from_date_str = request.GET.get('from_date')
        to_date_str = request.GET.get('to_date')
        branch_id = request.GET.get('branch')  # branch_id for filtering
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

        # 2) Branch list (for dropdown) - only branches created by this HQ user
        branches_qs = Branch.objects.filter(created_by=request.user).order_by('branch_name')
        context['branches'] = branches_qs
        context['branch_id'] = branch_id

        # 3) Build data from EmiCollectionDetail (EMI collections) - Branch Wise
        from loan.models import EmiCollectionDetail, LoanEMISchedule
        from savings.models import SavingsCollection

        rows = []
        totals = {
            'installment': Decimal('0'),
            'lpf': Decimal('0'),
            'saving': Decimal('0'),
            'others': Decimal('0'),
            'total': Decimal('0'),
            'disbursed': Decimal('0'),
        }

        # Filter by branch if specified
        branch_filter = {}
        if branch_id:
            branch_filter['loan_application__branch_id'] = branch_id

        # Get branches created by this HQ user for data isolation
        hq_branch_ids = Branch.objects.filter(created_by=request.user).values_list('branch_id', flat=True)

        collections = EmiCollectionDetail.objects.select_related(
            'collected_by_agent', 'collected_by_branch', 'emi', 'reschedule_emi', 'loan_application', 'loan_application__branch'
        ).filter(
            status__in=['verified'],
            collected=True,
            loan_application__branch_id__in=hq_branch_ids,  # Only this HQ's branches
        ).filter(
            Q(verified_at__date__gte=from_date, verified_at__date__lte=to_date) |
            Q(verified_at__isnull=True, collected_at__date__gte=from_date, collected_at__date__lte=to_date)
        ).exclude(
            collected_by_agent__isnull=True,
            collected_by_branch__isnull=True,
        )

        # Apply branch filter
        if branch_id:
            collections = collections.filter(loan_application__branch_id=branch_id)

        # Aggregate per branch and frequency (daily/weekly)
        per_branch = {}
        loan_freq_cache = {}

        for col in collections:
            branch = col.loan_application.branch
            if not branch:
                continue

            branch_key = f"branch:{branch.branch_id}"
            branch_name = branch.branch_name
            branch_code = branch.branch_id

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

            if branch_key not in per_branch:
                per_branch[branch_key] = {
                    'branch_name': branch_name,
                    'branch_code': branch_code,
                    'branch_id': branch.branch_id,
                    'daily_installment': Decimal('0'),
                    'weekly_installment': Decimal('0'),
                    'saving': Decimal('0'),
                    'others': Decimal('0'),
                    'daily_disbursed': Decimal('0'),
                    'weekly_disbursed': Decimal('0'),
                    'daily_lpf': Decimal('0'),
                    'weekly_lpf': Decimal('0'),
                }

            data = per_branch[branch_key]

            # Installment amount with penalty
            installment_component = (Decimal(col.amount_received or 0) + Decimal(col.penalty_received or 0))

            if freq == 'daily':
                data['daily_installment'] += installment_component
            elif freq == 'weekly':
                data['weekly_installment'] += installment_component

        # --- Savings collections (RD/FD) per branch ---
        savings_qs = SavingsCollection.objects.filter(
            is_collected=True,
            branch_id__in=hq_branch_ids,  # Only this HQ's branches
        ).filter(
            Q(collected_by_agent__isnull=False) | Q(collected_by_branch_employee__isnull=False)
        ).filter(
            Q(is_deposited_to_branch=True, deposited_at__date__gte=from_date, deposited_at__date__lte=to_date) |
            Q(Q(is_deposited_to_branch=False) | Q(deposited_at__isnull=True), collection_date__gte=from_date, collection_date__lte=to_date)
        )

        savings_qs = savings_qs.exclude(collection_type='withdrawal')

        # Apply branch filter
        if branch_id:
            savings_qs = savings_qs.filter(branch_id=branch_id)

        # Aggregate savings per branch
        savings_branch_rows = (
            savings_qs.values('branch__branch_id', 'branch__branch_name')
            .annotate(total=Sum('amount'))
        )
        for r in savings_branch_rows:
            branch_id_val = r.get('branch__branch_id')
            if not branch_id_val:
                continue
            branch_key = f"branch:{branch_id_val}"
            branch_name = r.get('branch__branch_name') or f"Branch {branch_id_val}"
            
            if branch_key not in per_branch:
                per_branch[branch_key] = {
                    'branch_name': branch_name,
                    'branch_code': branch_id_val,
                    'branch_id': branch_id_val,
                    'daily_installment': Decimal('0'),
                    'weekly_installment': Decimal('0'),
                    'saving': Decimal('0'),
                    'others': Decimal('0'),
                    'daily_disbursed': Decimal('0'),
                    'weekly_disbursed': Decimal('0'),
                    'daily_lpf': Decimal('0'),
                    'weekly_lpf': Decimal('0'),
                }
            per_branch[branch_key]['saving'] += (r.get('total') or Decimal('0'))

        # --- Disbursement amounts per branch and frequency ---
        from branch.models import BranchTransaction

        loan_freq_cache = {}
        seen_disbursements = set()

        disb_qs = BranchTransaction.objects.select_related(
            'disbursement_log', 'branch', 'disbursement_log__loan_id'
        ).filter(
            disbursement_log__isnull=False,
            transaction_date__date__gte=from_date,
            transaction_date__date__lte=to_date,
            branch_id__in=hq_branch_ids,  # Only this HQ's branches
        )

        # Apply branch filter
        if branch_id:
            disb_qs = disb_qs.filter(branch_id=branch_id)

        for bt in disb_qs:
            branch = bt.branch
            disb_log = bt.disbursement_log
            if not branch or not disb_log:
                continue

            loan = disb_log.loan_id
            if not loan:
                continue

            # Skip duplicate disbursement logs for the same loan and branch
            pair_key = (loan.loan_ref_no, branch.id)
            if pair_key in seen_disbursements:
                continue
            seen_disbursements.add(pair_key)

            # Determine frequency for this loan
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

            branch_key = f"branch:{branch.branch_id}"
            branch_name = branch.branch_name
            branch_code = branch.branch_id

            if branch_key not in per_branch:
                per_branch[branch_key] = {
                    'branch_name': branch_name,
                    'branch_code': branch_code,
                    'branch_id': branch.branch_id,
                    'daily_installment': Decimal('0'),
                    'weekly_installment': Decimal('0'),
                    'saving': Decimal('0'),
                    'others': Decimal('0'),
                    'daily_disbursed': Decimal('0'),
                    'weekly_disbursed': Decimal('0'),
                    'daily_lpf': Decimal('0'),
                    'weekly_lpf': Decimal('0'),
                }

            data = per_branch[branch_key]

            amount = Decimal(disb_log.amount or 0)
            lpf = Decimal(getattr(disb_log, 'tax_charges', 0) or 0)

            if freq == 'daily':
                data['daily_disbursed'] += amount
                data['daily_lpf'] += lpf
            elif freq == 'weekly':
                data['weekly_disbursed'] += amount
                data['weekly_lpf'] += lpf

        # Build rows for template (one row per branch x product)
        for branch_key, data in per_branch.items():
            branch_name = data['branch_name']
            branch_identity = 'Branch'
            branch_code = data.get('branch_code')
            branch_id_val = data.get('branch_id')

            # Daily product row
            if not product_filter or product_filter == 'daily':
                installment = data['daily_installment']
                saving = data['saving'] if not product_filter else data['saving']
                others = data['others']
                disbursed = data['daily_disbursed']
                lpf = data['daily_lpf']
                total = installment + lpf + saving + others

                rows.append({
                    'collector_name': branch_name,
                    'collector_identity': branch_identity,
                    'collector_code': branch_code,
                    'collector_id': branch_id_val,
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
                saving = Decimal('0') if not product_filter else data['saving']
                others = data['others']
                disbursed = data['weekly_disbursed']
                lpf = data['weekly_lpf']
                total = installment + lpf + saving + others

                rows.append({
                    'collector_name': branch_name,
                    'collector_identity': branch_identity,
                    'collector_code': branch_code,
                    'collector_id': branch_id_val,
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

        # Only treat BranchTransaction debits as expenses if their code
        # belongs to ChartOfAccount entries with main_type = 'C'
        from loan.models import ChartOfAccount

        expense_codes = list(
            ChartOfAccount.objects.filter(main_type='C').values_list('code', flat=True)
        )

        # Also always treat specific additional codes as expenses
        for extra_code in ['130', '131', '132', '133', '134', '144']:
            if extra_code not in expense_codes:
                expense_codes.append(extra_code)

        expense_qs = BranchTransaction.objects.filter(
            transaction_type='DEBIT',
            code__in=expense_codes,
            transaction_date__date__gte=from_date,
            transaction_date__date__lte=to_date,
            branch_id__in=hq_branch_ids,  # Only this HQ's branches
        ).exclude(code__in=['120', '121', '122', '123', '203', '206'])

        # Apply branch filter
        if branch_id:
            expense_qs = expense_qs.filter(branch_id=branch_id)

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
                continue

        for purpose, data in per_purpose.items():
            expense_rows.append({
                'exp_head': purpose,
                'bank_amount': data['bank'],
                'cash_amount': data['cash'],
            })

        expense_rows.sort(key=lambda r: r['exp_head'])

        # --- Opening / Closing balance summary ---
        fund_opening_cash = 0
        fund_opening_bank = 0
        fund_closing_cash = 0
        fund_closing_bank = 0

        # "Add" buckets
        fund_add_loan_cash = 0
        fund_add_loan_bank = 0
        fund_add_collection_cash = 0
        fund_add_collection_bank = 0
        fund_add_fd_cash = 0
        fund_add_fd_bank = 0
        fund_add_withdraw_cash = 0
        fund_add_withdraw_bank = 0
        fund_add_others_cash = 0
        fund_add_others_bank = 0

        # "Less" buckets
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

        from branch.models import BranchAccount

        # Calculate closing balances and movement - only for this HQ's branches
        cash_closing = (
            BranchAccount.objects
            .filter(type='CASH', branch_id__in=hq_branch_ids)
            .aggregate(total=Sum('current_balance'))['total']
            or 0
        )
        bank_closing = (
            BranchAccount.objects
            .filter(type='BANK', branch_id__in=hq_branch_ids)
            .aggregate(total=Sum('current_balance'))['total']
            or 0
        )

        # Apply branch filter
        if branch_id:
            cash_closing = (
                BranchAccount.objects
                .filter(branch_id=branch_id, type='CASH')
                .aggregate(total=Sum('current_balance'))['total']
                or 0
            )
            bank_closing = (
                BranchAccount.objects
                .filter(branch_id=branch_id, type='BANK')
                .aggregate(total=Sum('current_balance'))['total']
                or 0
            )

        movement_cash = 0
        movement_bank = 0

        tx_qs = BranchTransaction.objects.select_related('branch_account').filter(
            transaction_date__date__gte=from_date,
            transaction_date__date__lte=to_date,
            branch_id__in=hq_branch_ids,  # Only this HQ's branches
        )

        # Apply branch filter
        if branch_id:
            tx_qs = tx_qs.filter(branch_id=branch_id)

        fund_add_205_rows = []
        fund_add_dynamic_per_key = {}

        for bt in tx_qs:
            amount = bt.amount or 0
            account = bt.branch_account
            if not account or amount == 0:
                continue

            is_cash_acct = account.type == 'CASH'
            is_bank_acct = account.type == 'BANK'

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

            code = (bt.code or '').strip()

            # Collection for the day
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

            # Codes 201, 202, 205, 206, 207, 208 – group under Add section
            if bt.transaction_type == 'CREDIT' and code in ['201', '202', '205', '206', '207', '208']:
                purpose = bt.purpose or 'Unknown'
                key_205 = (code, purpose)
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

            # Withdrawal from Bank
            tx_mode = (bt.mode or '').strip().lower()
            if (
                bt.transaction_type == 'DEBIT'
                and is_bank_acct
                and tx_mode in ['BANK', 'bank', 'Online', 'online']
                and (code not in expense_codes)
            ):
                fund_add_withdraw_cash += amount
                fund_less_deposit_bank_bank += amount

            # Disbursement
            if bt.transaction_type == 'DEBIT' and bt.disbursement_log_id:
                if is_cash_acct:
                    fund_less_disbursement_cash += amount
                elif is_bank_acct:
                    fund_less_disbursement_bank += amount

            # Loan fund re-payment
            if bt.transaction_type == 'DEBIT' and code == '203':
                if is_cash_acct:
                    fund_less_loanrepay_cash += amount
                elif is_bank_acct:
                    fund_less_loanrepay_bank += amount

            # Saving return
            if bt.transaction_type == 'DEBIT' and code == '206':
                if is_cash_acct:
                    fund_less_saving_return_cash += amount
                elif is_bank_acct:
                    fund_less_saving_return_bank += amount

        fund_closing_cash = cash_closing
        fund_closing_bank = bank_closing

        fund_opening_cash = fund_closing_cash - movement_cash
        fund_opening_bank = fund_closing_bank - movement_bank

        # Build dynamic Add rows
        for (code_val, purpose), data in fund_add_dynamic_per_key.items():
            total = (data.get('cash') or 0) + (data.get('bank') or 0)
            fund_add_205_rows.append({
                'code': code_val,
                'purpose': purpose,
                'cash_amount': data.get('cash') or 0,
                'bank_amount': data.get('bank') or 0,
                'total_amount': total,
            })

        # Loan fund received summary
        loan_fund_qs = BranchTransaction.objects.select_related('branch_account').filter(
            transaction_type='CREDIT',
            code='203',
            transaction_date__date__gte=from_date,
            transaction_date__date__lte=to_date,
        )

        if branch_id:
            loan_fund_qs = loan_fund_qs.filter(branch_id=branch_id)

        fund_add_loan_cash = 0
        fund_add_loan_bank = 0

        for bt in loan_fund_qs:
            amount = bt.amount or 0
            account = bt.branch_account
            if not account or amount == 0:
                continue

            if account.type == 'CASH':
                fund_add_loan_cash += amount
            elif account.type == 'BANK':
                fund_add_loan_bank += amount

        fund_less_expenses_cash = expense_totals['cash']
        fund_less_expenses_bank = expense_totals['bank']

        # Add context
        context.update({
            'from_date': from_date,
            'to_date': to_date,
            'product': product_filter,
            'rows': rows,
            'totals': totals,
            'expense_rows': expense_rows,
            'expense_totals': expense_totals,
            'fund_opening_cash': fund_opening_cash,
            'fund_opening_bank': fund_opening_bank,
            'fund_closing_cash': fund_closing_cash,
            'fund_closing_bank': fund_closing_bank,
            'fund_add_loan_cash': fund_add_loan_cash,
            'fund_add_loan_bank': fund_add_loan_bank,
            'fund_add_collection_cash': fund_add_collection_cash,
            'fund_add_collection_bank': fund_add_collection_bank,
            'fund_add_fd_cash': fund_add_fd_cash,
            'fund_add_fd_bank': fund_add_fd_bank,
            'fund_add_withdraw_cash': fund_add_withdraw_cash,
            'fund_add_withdraw_bank': fund_add_withdraw_bank,
            'fund_add_others_cash': fund_add_others_cash,
            'fund_add_others_bank': fund_add_others_bank,
            'fund_add_205_rows': fund_add_205_rows,
            'fund_less_disbursement_cash': fund_less_disbursement_cash,
            'fund_less_disbursement_bank': fund_less_disbursement_bank,
            'fund_less_expenses_cash': fund_less_expenses_cash,
            'fund_less_expenses_bank': fund_less_expenses_bank,
            'fund_less_loanrepay_cash': fund_less_loanrepay_cash,
            'fund_less_loanrepay_bank': fund_less_loanrepay_bank,
            'fund_less_saving_return_cash': fund_less_saving_return_cash,
            'fund_less_saving_return_bank': fund_less_saving_return_bank,
            'fund_less_interest_saving_cash': fund_less_interest_saving_cash,
            'fund_less_interest_saving_bank': fund_less_interest_saving_bank,
            'fund_less_deposit_bank_cash': fund_less_deposit_bank_cash,
            'fund_less_deposit_bank_bank': fund_less_deposit_bank_bank,
            'fund_less_others_cash': fund_less_others_cash,
            'fund_less_others_bank': fund_less_others_bank,
        })

        return context
