import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from zoneinfo import ZoneInfo

from loan.models import LoanEMISchedule, LoanEMIReschedule


class Command(BaseCommand):
    help = (
        "Updates overdue status and days for unpaid EMIs based on due date. "
        "Intended to run nightly after 12 AM."
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
        parser.add_argument(
            '--loop', action='store_true', default=False,
            help='Run in a loop (useful for testing only; not recommended in production).'
        )
        parser.add_argument(
            '--interval-seconds', type=int, default=120,
            help='Loop interval in seconds when --loop is provided (default: 120 seconds).'
        )
        parser.add_argument(
            '--iterations', type=int, default=0,
            help='Number of loop iterations (0 means infinite) when --loop is provided.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tz_name = options['tz']
        simulate_days = int(options.get('simulate_days') or 0)
        loop = bool(options.get('loop'))
        interval_seconds = int(options.get('interval_seconds') or 120)
        iterations = int(options.get('iterations') or 0)

        tz = ZoneInfo(tz_name)

        if loop:
            count = 0
            self.stdout.write(self.style.NOTICE(
                f"[update_overdue_emis] Loop mode ON: interval={interval_seconds}s, iterations={iterations or 'infinite'}"
            ))
            try:
                while True:
                    count += 1
                    self._run_once(tz, simulate_days, dry_run)
                    if iterations and count >= iterations:
                        break
                    time.sleep(max(1, interval_seconds))
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("[update_overdue_emis] Loop interrupted by user."))
            return
        else:
            self._run_once(tz, simulate_days, dry_run)

    def _run_once(self, tz: ZoneInfo, simulate_days: int, dry_run: bool):
        now = timezone.now().astimezone(tz)
        base_today = now.date()
        today = base_today + timedelta(days=simulate_days)

        self.stdout.write(self.style.NOTICE(
            f"[update_overdue_emis] Start at {now.isoformat()} (local base date={base_today}, simulated date={today}, tz={tz.key})"
        ))

        # Fetch unpaid EMIs with installment_date strictly before today (overdue)
        qs = (
            LoanEMISchedule.objects
            .select_related('loan_application')
            .filter(paid=False, installment_date__lt=today)
            .order_by('installment_date')
        )

        # Also fetch unpaid rescheduled EMIs
        qs_res = (
            LoanEMIReschedule.objects
            .select_related('loan_application')
            .filter(paid=False, installment_date__lt=today)
            .order_by('installment_date')
        )

        updated = 0
        no_change = 0
        total = qs.count() + qs_res.count()
        self.stdout.write(self.style.NOTICE(f"[update_overdue_emis] Processing {total} unpaid EMIs (original + rescheduled)"))

        with transaction.atomic():
            # Original EMIs
            for emi in qs:
                overdue_days = (today - emi.installment_date).days
                is_overdue = overdue_days > 0

                # Skip if already paid (defensive check)
                if emi.paid:
                    continue

                changed = (
                    (emi.overdue_days or 0) != overdue_days or
                    bool(emi.is_overdue) != is_overdue
                )

                if changed:
                    emi.overdue_days = overdue_days
                    emi.is_overdue = is_overdue
                    updated += 1
                    if not dry_run:
                        emi.save(update_fields=['overdue_days', 'is_overdue'])
                else:
                    no_change += 1

            # Rescheduled EMIs
            for remi in qs_res:
                overdue_days = (today - remi.installment_date).days
                is_overdue = overdue_days > 0

                if remi.paid:
                    continue

                changed = (
                    (remi.overdue_days or 0) != overdue_days or
                    bool(remi.is_overdue) != is_overdue
                )

                if changed:
                    remi.overdue_days = overdue_days
                    remi.is_overdue = is_overdue
                    updated += 1
                    if not dry_run:
                        remi.save(update_fields=['overdue_days', 'is_overdue'])
                else:
                    no_change += 1

            if dry_run:
                # Rollback any accidental writes
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"[update_overdue_emis] Completed. Updated={updated}, NoChange={no_change}, TotalChecked={total}."
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("[update_overdue_emis] DRY RUN: No changes were saved to the database."))


# Use this command to update overdue EMIs: python manage.py update_overdue_emis
# Use cornjob scheduling to run this command on a specific time