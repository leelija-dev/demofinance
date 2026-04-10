from django.apps import AppConfig


class LoanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loan'

    def ready(self):
        # Auto-run a lightweight updater only in development server
        # This will run every 120 seconds to update overdue EMI flags.
        # It is guarded to avoid double start with Django's autoreloader.
        import os
        from django.conf import settings
        if not getattr(settings, 'DEBUG', False):
            return
        # In dev, runserver starts the app twice; RUN_MAIN ensures we only start in the reloader main process
        if os.environ.get('RUN_MAIN') != 'true':
            return

        import threading
        import time
        from django.utils import timezone
        from zoneinfo import ZoneInfo
        from datetime import timedelta
        from loan.models import LoanEMISchedule, LoanEMIReschedule

        def _update_once():
            try:
                tz = ZoneInfo(getattr(settings, 'TIME_ZONE', 'Asia/Kolkata'))
                now = timezone.now().astimezone(tz)
                today = now.date()
                
                # Find all unpaid EMIs with due date before today
                qs = (
                    LoanEMISchedule.objects
                    .select_related('loan_application')
                    .filter(paid=False, installment_date__lt=today)
                    .order_by('installment_date')
                )
                
                updated = 0
                for emi in qs:
                    overdue_days = (today - emi.installment_date).days
                    is_overdue = overdue_days > 0
                    
                    # Skip if already paid (defensive check)
                    if emi.paid:
                        continue
                        
                    # Only update if values have changed
                    if (emi.overdue_days or 0) != overdue_days or bool(emi.is_overdue) != is_overdue:
                        emi.overdue_days = overdue_days
                        emi.is_overdue = is_overdue
                        emi.save(update_fields=['overdue_days', 'is_overdue'])
                        updated += 1

                # Also update rescheduled EMIs using the same logic
                qs_res = (
                    LoanEMIReschedule.objects
                    .select_related('loan_application')
                    .filter(paid=False, installment_date__lt=today)
                    .order_by('installment_date')
                )

                for remi in qs_res:
                    overdue_days = (today - remi.installment_date).days
                    is_overdue = overdue_days > 0

                    if remi.paid:
                        continue

                    if (remi.overdue_days or 0) != overdue_days or bool(remi.is_overdue) != is_overdue:
                        remi.overdue_days = overdue_days
                        remi.is_overdue = is_overdue
                        remi.save(update_fields=['overdue_days', 'is_overdue'])
                        updated += 1
                
                if updated > 0:
                    print(f"[Auto-Update] Updated {updated} EMIs with overdue status")
                    
                    overdue_days = (today - emi.installment_date).days
                    is_overdue = overdue_days > 0
                    # Apply late fee from first day beyond grace: threshold = grace_days + 1
                    if (not emi.paid) and is_overdue and (overdue_days >= (grace_days + 1)) and (fee_value > 0):
                        late_fee = Decimal('0.00')
                        delta = max(0, overdue_days - grace_days)
                        if frequency == 'daily':
                            periods = delta
                        elif frequency == 'weekly':
                            periods = delta // 7
                        else:  # monthly
                            from datetime import timedelta
                            start_date = emi.installment_date + timedelta(days=grace_days)
                            months = (today.year - start_date.year) * 12 + (today.month - start_date.month)
                            if today.day < start_date.day:
                                months -= 1
                            periods = max(0, months)
                        if periods > 0:
                            inst_amt = Decimal(str(emi.installment_amount))
                            if fee_type == 'percentage':
                                per_period_fee = (inst_amt * fee_value / Decimal('100.00'))
                            else:
                                per_period_fee = fee_value
                            late_fee = (per_period_fee * periods).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
                        emi.overdue_days = overdue_days
                        emi.is_overdue = is_overdue
                        emi.late_fee = late_fee
                        emi.save(update_fields=['overdue_days', 'is_overdue', 'late_fee'])
            except Exception:
                # Silently ignore errors in dev loop to avoid crashing runserver
                pass

        def _loop():
            daily_at = getattr(settings, 'EMI_OVERDUE_DEV_DAILY_AT', '00:05')  # format HH:MM
            use_daily = bool(daily_at)
            interval = int(getattr(settings, 'EMI_OVERDUE_DEV_INTERVAL_SECONDS', 60))

            # Track last run date to avoid multiple runs per day in daily mode
            last_run_date = {'date': None}

            while True:
                try:
                    if use_daily:
                        # Daily mode: run once per day after the configured time (default 00:05)
                        try:
                            target_hour, target_minute = [int(p) for p in str(daily_at).split(':', 1)]
                        except Exception:
                            target_hour, target_minute = 0, 5
                        tz = ZoneInfo(getattr(settings, 'TIME_ZONE', 'Asia/Kolkata'))
                        now = timezone.now().astimezone(tz)
                        if last_run_date['date'] != now.date():
                            if (now.hour > target_hour) or (now.hour == target_hour and now.minute >= target_minute):
                                _update_once()
                                last_run_date['date'] = now.date()
                        # Poll every 30s to catch the window soon after the target time
                        time.sleep(30)
                    else:
                        # Interval mode: run every N seconds
                        _update_once()
                        time.sleep(max(1, interval))
                except Exception:
                    # Never crash the loop in dev
                    time.sleep(max(1, interval))

        # Start daemon thread
        t = threading.Thread(target=_loop, name='emi-overdue-dev-updater', daemon=True)
        t.start()
