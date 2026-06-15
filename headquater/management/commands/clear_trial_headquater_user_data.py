from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model

from headquater.models import (
    Branch,
    HeadquartersWallet,
    HeadquartersTransactions,
    FundTransfers,
)
from branch.models import (
    BranchAccount,
    BranchTransaction,
    AgentDeposit,
    AgentDepositDenomination,
)
from loan.models import (
    LoanApplication,
    CustomerDetail,
    CustomerAddress,
    CustomerLoanDetail,
    CustomerDocument,
    CustomerAccount,
    DocumentRequest,
    DocumentReupload,
    DocumentReview,
    LoanPeriod,
    Deductions,
    DisbursementLog,
    ProductCategory,
    ProductSubCategory,
    Product,
    LoanEMISchedule,
    LoanRescheduleLog,
    LoanEMIReschedule,
    EmiAgentAssign,
    EmiCollectionDetail,
    LoanCloseRequest,
    LoanApplicationDraft,
    ShopBankAccount,
)
from savings.models import (
    SavingsAccountApplication,
    SavingsCollection,
    SavingsAgentAssign,
    OneTimeDeposit,
    DailyProduct,
)

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Permanently deletes transactional data (loan applications, savings "
        "accounts, transactions, etc.) created by expired trial headquarter "
        "users. Does NOT delete the user itself, branches, agents, employees, "
        "or master data. Only resets current_balance on accounts/wallets."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Compute and log changes without saving to the database.'
        )
        parser.add_argument(
            '--tz', type=str, default='Asia/Kolkata',
            help='IANA timezone name for date computations (default: Asia/Kolkata)'
        )
        parser.add_argument(
            '--simulate-days', type=int, default=0,
            help='For testing: advance the logical "today" by N days (e.g., 1 to simulate next day).'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tz_name = options['tz']
        simulate_days = int(options.get('simulate_days') or 0)

        tz = ZoneInfo(tz_name)
        now = timezone.now().astimezone(tz)
        cutoff = now + timedelta(days=simulate_days)

        # 7-day grace period: only clean users whose trial expired more than 7 days ago
        grace_period_days = 7
        cleanup_threshold = cutoff - timedelta(days=grace_period_days)

        self.stdout.write(self.style.NOTICE(
            f"[clear_trial_headquater_user_data] Start at {now.isoformat()} "
            f"(local time={cutoff}, tz={tz.key})"
        ))
        self.stdout.write(self.style.NOTICE(
            f"[clear_trial_headquater_user_data] Grace period = {grace_period_days} day(s). "
            f"Cleaning users whose trial expiry was before {cleanup_threshold.date()}"
        ))

        # Find expired trial users past grace period
        expired_trial_users = User.objects.filter(
            trial_expiry_date__isnull=False,
            trial_expiry_date__lt=cleanup_threshold,
        )

        total_users = expired_trial_users.count()
        self.stdout.write(self.style.NOTICE(
            f"[clear_trial_headquater_user_data] Found {total_users} expired trial user(s)"
        ))

        if total_users == 0:
            self.stdout.write(self.style.SUCCESS("No users to process. Exiting."))
            return

        # Collect all branches created by these trial users
        branches = Branch.objects.filter(created_by__in=expired_trial_users)
        branch_ids = list(branches.values_list('branch_id', flat=True))
        self.stdout.write(f"  Branches under trial users: {len(branch_ids)}")

        # Collect all loan applications across those branches
        loan_apps = LoanApplication.objects.filter(branch__in=branch_ids)
        loan_ref_nos = list(loan_apps.values_list('loan_ref_no', flat=True))
        self.stdout.write(f"  Loan applications found: {len(loan_ref_nos)}")

        # Collect all savings applications across those branches
        sav_apps = SavingsAccountApplication.objects.filter(branch__in=branch_ids)
        sav_app_ids = list(sav_apps.values_list('application_id', flat=True))
        self.stdout.write(f"  Savings applications found: {len(sav_app_ids)}")

        stats = {
            # Reset balance only
            'branch_accounts_reset': 0,
            'shop_bank_accounts_reset': 0,
            'hq_wallets_reset': 0,

            # Delete all (loan-related)
            'customer_details_deleted': 0,
            'customer_addresses_deleted': 0,
            'customer_loan_details_deleted': 0,
            'customer_documents_deleted': 0,
            'customer_accounts_deleted': 0,
            'loan_emi_schedules_deleted': 0,
            'loan_emi_reschedules_deleted': 0,
            'loan_periods_deleted': 0,
            'disbursement_logs_deleted': 0,
            'document_requests_deleted': 0,
            'document_reuploads_deleted': 0,
            'document_reviews_deleted': 0,
            'emi_agent_assigns_deleted': 0,
            'emi_collection_details_deleted': 0,
            'loan_close_requests_deleted': 0,
            'loan_application_drafts_deleted': 0,
            'loan_reschedule_logs_deleted': 0,
            'loan_applications_deleted': 0,

            # Delete all (savings-related)
            'savings_collections_deleted': 0,
            'savings_agent_assigns_deleted': 0,
            'savings_accounts_deleted': 0,

            # Delete all (branch transactional)
            'agent_deposits_deleted': 0,
            'agent_deposit_denominations_deleted': 0,
            'branch_transactions_deleted': 0,

            # Delete all (HQ transactional)
            'hq_transactions_deleted': 0,
            'fund_transfers_deleted': 0,
        }

        with transaction.atomic():
            # ================================================================
            # DELETE LOAN-RELATED DATA
            # Deletion order matters:
            #   1. Delete child rows that FK to LoanApplication
            #   2. Delete LoanApplication itself
            #   3. Delete CustomerDetail (LoanApplication has FK customer→CustomerDetail,
            #      so CustomerDetail can only be deleted AFTER LoanApplication is gone
            #      to avoid FK nullification)
            # ================================================================
            if loan_ref_nos:
                # --- STEP 1: Delete children of LoanApplication ---

                # 1a. CustomerDocument (OneToOne FK to LoanApplication)
                qs = CustomerDocument.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_documents_deleted'] += count

                # 1b. CustomerLoanDetail (FK to LoanApplication)
                qs = CustomerLoanDetail.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_loan_details_deleted'] += count

                # 1c. CustomerAddress (FK to LoanApplication + OneToOne to CustomerDetail)
                qs = CustomerAddress.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_addresses_deleted'] += count

                # 1d. CustomerAccount (OneToOne FK to LoanApplication)
                qs = CustomerAccount.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_accounts_deleted'] += count

                # 1e. LoanEMISchedule (FK to LoanApplication)
                qs = LoanEMISchedule.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_emi_schedules_deleted'] += count

                # 1f. LoanEMIReschedule (FK to LoanApplication)
                qs = LoanEMIReschedule.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_emi_reschedules_deleted'] += count

                # 1g. LoanPeriod (FK to LoanApplication)
                qs = LoanPeriod.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_periods_deleted'] += count

                # 1h. DisbursementLog (FK loan_id to LoanApplication)
                qs = DisbursementLog.objects.filter(loan_id__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['disbursement_logs_deleted'] += count

                # 1i. DocumentRequest (FK to LoanApplication)
                qs = DocumentRequest.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['document_requests_deleted'] += count

                # 1j. DocumentReupload (FK to LoanApplication)
                qs = DocumentReupload.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['document_reuploads_deleted'] += count

                # 1k. DocumentReview (FK to LoanApplication)
                qs = DocumentReview.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['document_reviews_deleted'] += count

                # 1l. EmiAgentAssign (FK via emi__loan_application or reschedule_emi__loan_application)
                from django.db.models import Q
                qs = EmiAgentAssign.objects.filter(
                    Q(emi__loan_application__in=loan_ref_nos) |
                    Q(reschedule_emi__loan_application__in=loan_ref_nos)
                )
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['emi_agent_assigns_deleted'] += count

                # 1m. EmiCollectionDetail (FK to LoanApplication)
                qs = EmiCollectionDetail.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['emi_collection_details_deleted'] += count

                # 1n. LoanCloseRequest (FK to LoanApplication)
                qs = LoanCloseRequest.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_close_requests_deleted'] += count

                # 1o. LoanRescheduleLog (FK to LoanApplication)
                qs = LoanRescheduleLog.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_reschedule_logs_deleted'] += count

                # 1p. Deductions — master data (no loan_application FK), skipped

                # --- STEP 2: Delete LoanApplication itself ---
                count = len(loan_ref_nos)
                if count:
                    if not dry_run:
                        loan_apps.delete()
                    stats['loan_applications_deleted'] += count

                # --- STEP 3: Delete CustomerDetail (reverse FK: LoanApplication.customer)
                #     Only now safe because LoanApplications referencing these customers are gone.
                qs = CustomerDetail.objects.filter(
                    loan_applications__isnull=True,
                    branch__in=branch_ids,
                )
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_details_deleted'] += count

            # ================================================================
            # DELETE SAVINGS-RELATED DATA
            # ================================================================
            if sav_app_ids:
                # 1. SavingsCollection
                qs = SavingsCollection.objects.filter(account__in=sav_app_ids)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['savings_collections_deleted'] += count

                # 2. SavingsAgentAssign
                qs = SavingsAgentAssign.objects.filter(account__in=sav_app_ids)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['savings_agent_assigns_deleted'] += count

                # 3. Delete SavingsAccountApplication
                count = len(sav_app_ids)
                if count:
                    if not dry_run:
                        sav_apps.delete()
                    stats['savings_accounts_deleted'] += count

            # ================================================================
            # DELETE BRANCH TRANSACTIONAL DATA (under trial user's branches)
            #
            # FundTransfers FK to BranchTransaction via branch_transaction field.
            # Delete FundTransfers that reference these BranchTransactions FIRST,
            # then delete BranchTransaction itself.
            # ================================================================
            if branch_ids:
                # 0. Delete FundTransfers linked to these branch transactions FIRST
                #    (before BranchTransactions are deleted)
                qs = FundTransfers.objects.filter(
                    branch_transaction__branch__in=branch_ids
                )
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['fund_transfers_deleted'] += count

                # 1. AgentDepositDenomination (cascade from AgentDeposit)
                qs = AgentDepositDenomination.objects.filter(deposit__branch__in=branch_ids)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['agent_deposit_denominations_deleted'] += count

                # 2. AgentDeposit
                qs = AgentDeposit.objects.filter(branch__in=branch_ids)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['agent_deposits_deleted'] += count

                # 3. BranchTransaction
                qs = BranchTransaction.objects.filter(branch__in=branch_ids)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['branch_transactions_deleted'] += count

                # 4. LoanApplicationDraft — delete drafts by branch employee IDs and agent IDs
                from branch.models import BranchEmployee
                branch_emp_ids = list(
                    BranchEmployee.objects.filter(branch__in=branch_ids)
                    .values_list('employee_id', flat=True)
                )
                qs = LoanApplicationDraft.objects.filter(
                    user_type='branch',
                    user_id__in=branch_emp_ids
                )
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_application_drafts_deleted'] += count

                # Also delete agent drafts under these branches
                from agent.models import Agent
                agent_ids = list(
                    Agent.objects.filter(branch__in=branch_ids)
                    .values_list('agent_id', flat=True)
                )
                if agent_ids:
                    qs = LoanApplicationDraft.objects.filter(
                        user_type='agent',
                        user_id__in=agent_ids
                    )
                    count = qs.count()
                    if count:
                        if not dry_run:
                            qs.delete()
                        stats['loan_application_drafts_deleted'] += count

            # ================================================================
            # DELETE HQ TRANSACTIONAL DATA (created by trial user)
            #
            # FundTransfers has:
            #   - created_by (CharField storing transaction_id string)
            #   - hq_transaction (FK to HeadquartersTransactions, on_delete=SET_NULL)
            #
            # Delete FundTransfers FIRST (while we still have the transaction IDs),
            # then delete HeadquartersTransactions.
            # ================================================================
            for trial_user in expired_trial_users:
                # Step 1: Collect HQ transaction IDs created by this trial user
                #         BEFORE deleting them (needed for FundTransfers.created_by lookup)
                user_txn_ids = list(
                    HeadquartersTransactions.objects.filter(created_by=trial_user)
                    .values_list('transaction_id', flat=True)
                )

                # Step 2: Delete FundTransfers linked to these transactions.
                #         FundTransfers.created_by stores the transaction_id (CharField).
                #         Also delete FundTransfers that FK to these HQ transactions.
                if user_txn_ids:
                    qs = FundTransfers.objects.filter(
                        Q(created_by__in=user_txn_ids) |
                        Q(hq_transaction__in=user_txn_ids)
                    )
                    count = qs.count()
                    if count:
                        if not dry_run:
                            qs.delete()
                        stats['fund_transfers_deleted'] += count

                # Step 3: Now delete HeadquartersTransactions
                qs = HeadquartersTransactions.objects.filter(created_by=trial_user)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['hq_transactions_deleted'] += count

            # ================================================================
            # RESET CURRENT BALANCE (not delete)
            # ================================================================
            # 1. BranchAccount - reset current_balance to 0
            qs = BranchAccount.objects.filter(branch__in=branch_ids)
            count = qs.count()
            if count:
                if not dry_run:
                    qs.update(current_balance=0)
                stats['branch_accounts_reset'] += count

            # 2. ShopBankAccount - reset current_balance to 0
            qs = ShopBankAccount.objects.filter(shop__branch__in=branch_ids)
            count = qs.count()
            if count:
                if not dry_run:
                    qs.update(current_balance=0)
                stats['shop_bank_accounts_reset'] += count

            # 3. HeadquartersWallet - reset balance to 0 for trial user created wallets
            for trial_user in expired_trial_users:
                qs = HeadquartersWallet.objects.filter(created_by=trial_user)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.update(balance=0)
                    stats['hq_wallets_reset'] += count

            if dry_run:
                transaction.set_rollback(True)

        # Summary
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("  CLEAR TRIAL HQ USER DATA - SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        self.stdout.write(self.style.NOTICE("  [BALANCE RESET (kept records, zeroed balance)]"))
        _print_stat(self, stats, 'branch_accounts_reset', 'BranchAccounts reset')
        _print_stat(self, stats, 'shop_bank_accounts_reset', 'ShopBankAccounts reset')
        _print_stat(self, stats, 'hq_wallets_reset', 'HQWallets reset')

        self.stdout.write(self.style.NOTICE("  [LOAN-RELATED DATA DELETED]"))
        _print_stat(self, stats, 'loan_applications_deleted', 'LoanApplications')
        _print_stat(self, stats, 'customer_details_deleted', 'CustomerDetails')
        _print_stat(self, stats, 'customer_addresses_deleted', 'CustomerAddresses')
        _print_stat(self, stats, 'customer_loan_details_deleted', 'CustomerLoanDetails')
        _print_stat(self, stats, 'customer_documents_deleted', 'CustomerDocuments')
        _print_stat(self, stats, 'customer_accounts_deleted', 'CustomerAccounts')
        _print_stat(self, stats, 'loan_emi_schedules_deleted', 'LoanEMISchedules')
        _print_stat(self, stats, 'loan_emi_reschedules_deleted', 'LoanEMIReschedules')
        _print_stat(self, stats, 'loan_periods_deleted', 'LoanPeriods')
        _print_stat(self, stats, 'disbursement_logs_deleted', 'DisbursementLogs')
        _print_stat(self, stats, 'document_requests_deleted', 'DocumentRequests')
        _print_stat(self, stats, 'document_reuploads_deleted', 'DocumentReuploads')
        _print_stat(self, stats, 'document_reviews_deleted', 'DocumentReviews')
        _print_stat(self, stats, 'emi_agent_assigns_deleted', 'EmiAgentAssigns')
        _print_stat(self, stats, 'emi_collection_details_deleted', 'EmiCollectionDetails')
        _print_stat(self, stats, 'loan_close_requests_deleted', 'LoanCloseRequests')
        _print_stat(self, stats, 'loan_reschedule_logs_deleted', 'LoanRescheduleLogs')
        _print_stat(self, stats, 'loan_application_drafts_deleted', 'LoanApplicationDrafts')

        self.stdout.write(self.style.NOTICE("  [SAVINGS-RELATED DATA DELETED]"))
        _print_stat(self, stats, 'savings_accounts_deleted', 'SavingsAccounts')
        _print_stat(self, stats, 'savings_collections_deleted', 'SavingsCollections')
        _print_stat(self, stats, 'savings_agent_assigns_deleted', 'SavingsAgentAssigns')

        self.stdout.write(self.style.NOTICE("  [BRANCH TRANSACTIONAL DATA DELETED]"))
        _print_stat(self, stats, 'branch_transactions_deleted', 'BranchTransactions')
        _print_stat(self, stats, 'agent_deposits_deleted', 'AgentDeposits')
        _print_stat(self, stats, 'agent_deposit_denominations_deleted', 'AgentDepositDenominations')

        self.stdout.write(self.style.NOTICE("  [HQ TRANSACTIONAL DATA DELETED]"))
        _print_stat(self, stats, 'hq_transactions_deleted', 'HQTransactions')
        _print_stat(self, stats, 'fund_transfers_deleted', 'FundTransfers')

        self.stdout.write(self.style.SUCCESS("=" * 60))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "[clear_trial_headquater_user_data] DRY RUN: No changes were saved to the database."
            ))


def _print_stat(self, stats, key, label):
    val = stats.get(key, 0)
    if val:
        self.stdout.write(self.style.SUCCESS(f"    {label}: {val}"))
    else:
        self.stdout.write(f"    {label}: 0")