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
            'deductions_deleted': 0,
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

            # Delete user-created products/config (only those specifically created by trial user)
            'one_time_deposits_deleted': 0,
            'daily_products_deleted': 0,
        }

        with transaction.atomic():
            # ================================================================
            # DELETE LOAN-RELATED DATA (cascade from loan apps)
            # ================================================================
            if loan_ref_nos:
                # --- Customer-level data (shared across loans per customer) ---
                # Get all customer IDs from these loan applications
                loan_app_objects = list(loan_apps)  # materialize

                # 1. CustomerDocument (one-to-one with loan application)
                qs = CustomerDocument.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_documents_deleted'] += count

                # 2. CustomerLoanDetail
                qs = CustomerLoanDetail.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_loan_details_deleted'] += count

                # 3. CustomerAddress
                qs = CustomerAddress.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_addresses_deleted'] += count

                # 4. CustomerDetail
                qs = CustomerDetail.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_details_deleted'] += count

                # 5. CustomerAccount (references customer detail, but we can filter via loan_application)
                qs = CustomerAccount.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['customer_accounts_deleted'] += count

                # 6. LoanEMISchedule
                qs = LoanEMISchedule.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_emi_schedules_deleted'] += count

                # 7. LoanEMIReschedule
                qs = LoanEMIReschedule.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_emi_reschedules_deleted'] += count

                # 8. LoanPeriod
                qs = LoanPeriod.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_periods_deleted'] += count

                # 9. DisbursementLog
                qs = DisbursementLog.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['disbursement_logs_deleted'] += count

                # 10. DocumentRequest
                qs = DocumentRequest.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['document_requests_deleted'] += count

                # 11. DocumentReupload
                qs = DocumentReupload.objects.filter(document_request__loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['document_reuploads_deleted'] += count

                # 12. DocumentReview
                qs = DocumentReview.objects.filter(document_request__loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['document_reviews_deleted'] += count

                # 13. EmiAgentAssign
                qs = EmiAgentAssign.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['emi_agent_assigns_deleted'] += count

                # 14. EmiCollectionDetail
                qs = EmiCollectionDetail.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['emi_collection_details_deleted'] += count

                # 15. LoanCloseRequest
                qs = LoanCloseRequest.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_close_requests_deleted'] += count

                # 16. LoanRescheduleLog
                qs = LoanRescheduleLog.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['loan_reschedule_logs_deleted'] += count

                # 17. Deductions (user-created ones under these loans)
                qs = Deductions.objects.filter(loan_application__in=loan_ref_nos)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['deductions_deleted'] += count

                # 18. Finally, delete LoanApplication itself
                count = len(loan_ref_nos)
                if count:
                    if not dry_run:
                        loan_apps.delete()
                    stats['loan_applications_deleted'] += count

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
            # ================================================================
            if branch_ids:
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

                # 4. LoanApplicationDraft (linked via user_id - agent/branch IDs under these branches)
                #    We can't easily filter by branch, so skip. But we can filter by branch_ids
                #    through the branch employee IDs. For now, delete drafts related to these branches.
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
            # ================================================================
            for trial_user in expired_trial_users:
                # 1. HeadquartersTransactions
                qs = HeadquartersTransactions.objects.filter(created_by=trial_user)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['hq_transactions_deleted'] += count

                # 2. FundTransfers (where created_by matches transaction ID)
                #    These are linked via hq_transaction or branch_transaction.
                #    Delete by created_by matching trial user's transaction IDs
                user_txn_ids = list(
                    HeadquartersTransactions.objects.filter(created_by=trial_user)
                    .values_list('transaction_id', flat=True)
                )
                if user_txn_ids:
                    qs = FundTransfers.objects.filter(created_by__in=user_txn_ids)
                    count = qs.count()
                    if count:
                        if not dry_run:
                            qs.delete()
                        stats['fund_transfers_deleted'] += count

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

            # ================================================================
            # DELETE USER-CREATED PRODUCTS/CONFIG (only trial-user-created ones)
            # ================================================================
            for trial_user in expired_trial_users:
                # OneTimeDeposit
                qs = OneTimeDeposit.objects.filter(created_by=trial_user)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['one_time_deposits_deleted'] += count

                # DailyProduct
                qs = DailyProduct.objects.filter(created_by=trial_user)
                count = qs.count()
                if count:
                    if not dry_run:
                        qs.delete()
                    stats['daily_products_deleted'] += count

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
        _print_stat(self, stats, 'deductions_deleted', 'Deductions')
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

        self.stdout.write(self.style.NOTICE("  [TRIAL-USER-CREATED PRODUCTS DELETED]"))
        _print_stat(self, stats, 'one_time_deposits_deleted', 'OneTimeDeposits')
        _print_stat(self, stats, 'daily_products_deleted', 'DailyProducts')

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