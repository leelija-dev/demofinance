from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction
from django.utils import timezone

from loan.models import (
    LoanApplication,
    LoanPeriod,
    LoanEMISchedule,
    LoanRescheduleLog,
    LoanEMIReschedule,
    EmiAgentAssign,
)


def _round_2(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


@transaction.atomic
def reschedule_loan_for_branch(loan_ref_no, branch_employee, penalty_rate=None, reschedule_length=None, remarks=''):
    """Reschedule a loan after original maturity for daily/weekly loans.

    Business rules:
    - Only allowed after last EMI date (maturity) has passed.
    - Only when there is outstanding balance (unpaid EMI + unpaid late fee).
    - Max 3 reschedules per LoanPeriod.
    - Daily: default 30 days at 6%%.
    - Weekly: default 5 weeks at 3%%.
    - New installment cannot be less than original installment; if it is,
      keep original size and extend the number of installments.
    """
    loan = LoanApplication.objects.select_for_update().get(loan_ref_no=loan_ref_no)

    period = loan.periods.order_by('-created_at').first()
    if not period:
        # Auto-create a minimal LoanPeriod based on existing EMI schedules and loan details
        emi_qs = loan.emi_schedules.all()
        if not emi_qs.exists():
            raise ValueError("No LoanPeriod found for this loan.")

        # Derive realizable amount and installment size from EMI schedules
        agg = emi_qs.aggregate(
            total=models.Sum('installment_amount'),
        )
        realizable_amount = agg['total'] or Decimal('0.00')
        number_of_installments = emi_qs.count()
        first_emi = emi_qs.order_by('installment_date').first()
        installment_size = first_emi.installment_amount if first_emi else Decimal('0.00')

        # Try to derive loan_amount and rate from loan_details; fall back to realizable/0
        details = loan.loan_details.order_by('-submitted_at').first()
        if details:
            loan_amount = details.loan_amount
            rate_of_interest = details.interest_rate.rate_of_interest if details.interest_rate else Decimal('0.00')
        else:
            loan_amount = realizable_amount
            rate_of_interest = Decimal('0.00')

        period = LoanPeriod.objects.create(
            loan_application=loan,
            loan_amount=loan_amount,
            rate_of_interest=rate_of_interest,
            installment_size=installment_size,
            realizable_amount=realizable_amount,
            number_of_installments=number_of_installments,
        )

    original_installment = period.original_installment_size or period.installment_size

    # Determine the original frequency. Prefer the stored value on LoanPeriod,
    # but if it's missing (older records), infer it from the first EMI schedule.
    first_emi = loan.emi_schedules.order_by('installment_date').first()
    if period.original_frequency:
        original_freq = period.original_frequency
    else:
        inferred_freq = getattr(first_emi, 'frequency', None) if first_emi else None
        original_freq = inferred_freq or 'daily'

    # Derive original principal/interest split from the first EMI (for ratio)
    if first_emi and first_emi.installment_amount:
        principal_ratio = (first_emi.principal_amount or Decimal('0.00')) / first_emi.installment_amount
        interest_ratio = (first_emi.interest_amount or Decimal('0.00')) / first_emi.installment_amount
    else:
        principal_ratio = Decimal('1.00')
        interest_ratio = Decimal('0.00')

    if original_freq == 'daily':
        default_rate = Decimal('6.00')
        default_length = 30
        reschedule_unit = 'days'
    elif original_freq == 'weekly':
        default_rate = Decimal('3.00')
        default_length = 5
        reschedule_unit = 'weeks'
    else:
        raise ValueError("Reschedule is supported only for daily and weekly loans.")

    penalty_rate = Decimal(str(penalty_rate)) if penalty_rate is not None else default_rate
    reschedule_length = int(reschedule_length or default_length)

    if period.reschedule_count >= 3:
        raise ValueError("Maximum 3 reschedules already used for this loan.")

    last_emi = loan.emi_schedules.order_by('-installment_date').first()
    if not last_emi:
        raise ValueError("No EMI schedule found for this loan.")

    today = timezone.now().date()
    if today <= last_emi.installment_date:
        raise ValueError("Reschedule is allowed only after the loan period has expired.")

    # ------------------------------------------------------------------
    # Backend guard for repeated reschedules (Option A logic).
    # If there is an existing latest reschedule snapshot (LoanEMIReschedule),
    # we only allow a NEW reschedule when:
    #   - the latest reschedule EMI period has expired (today > last reschedule EMI date), AND
    #   - there are unpaid rescheduled EMIs.
    # Otherwise, we block another reschedule even if the frontend button is
    # somehow triggered.
    # ------------------------------------------------------------------
    from loan.models import LoanRescheduleLog, LoanEMIReschedule

    latest_log = (
        LoanRescheduleLog.objects
        .filter(loan_application=loan)
        .order_by('-created_at')
        .first()
    )

    if latest_log is not None:
        res_emis_qs = LoanEMIReschedule.objects.filter(reschedule_log=latest_log).order_by('installment_date')
        if res_emis_qs.exists():
            last_res_emi = res_emis_qs.order_by('-installment_date').first()
            last_res_date = last_res_emi.installment_date

            # If we are still within the reschedule period, disallow new reschedule
            if today <= last_res_date:
                raise ValueError(
                    "Reschedule is allowed only after the current reschedule period has expired."
                )

            # Once the reschedule period has expired, require unpaid rescheduled EMIs
            unpaid_res_qs = res_emis_qs.filter(paid=False)
            if not unpaid_res_qs.exists():
                raise ValueError("No unpaid rescheduled EMIs to reschedule again.")

            # When rescheduled EMIs exist and period has expired, base outstanding
            # on the unpaid rescheduled EMIs (installment + late_fee)
            outstanding = unpaid_res_qs.aggregate(
                total=models.Sum('installment_amount') + models.Sum('late_fee')
            )['total'] or Decimal('0.00')
            outstanding = _round_2(outstanding)

            # Remove agent assignments only for the rescheduled EMIs that are being rescheduled again
            EmiAgentAssign.objects.filter(
                reschedule_emi__in=unpaid_res_qs,
            ).delete()
        else:
            # No snapshot EMIs for this log; fall back to original schedule
            unpaid_qs = loan.emi_schedules.filter(paid=False)
            outstanding = unpaid_qs.aggregate(
                total=models.Sum('installment_amount') + models.Sum('late_fee')
            )['total'] or Decimal('0.00')
            outstanding = _round_2(outstanding)

            # Remove agent assignments only for original EMIs that are being rescheduled
            EmiAgentAssign.objects.filter(
                emi__in=unpaid_qs,
            ).delete()
    else:
        # No previous reschedule logs; use original EMI schedule to compute outstanding
        unpaid_qs = loan.emi_schedules.filter(paid=False)
        outstanding = unpaid_qs.aggregate(
            total=models.Sum('installment_amount') + models.Sum('late_fee')
        )['total'] or Decimal('0.00')
        outstanding = _round_2(outstanding)

        # Remove agent assignments only for original EMIs that are being rescheduled
        EmiAgentAssign.objects.filter(
            emi__in=unpaid_qs,
        ).delete()

    if outstanding <= 0:
        raise ValueError("No outstanding balance to reschedule.")

    penalty_amount = _round_2(outstanding * penalty_rate / Decimal('100'))
    new_balance = _round_2(outstanding + penalty_amount)

    if reschedule_length <= 0:
        raise ValueError("Reschedule length must be positive.")

    new_installment_raw = new_balance / Decimal(reschedule_length)

    if new_installment_raw >= original_installment:
        # Normal case: evenly spread over the chosen reschedule length
        new_installment = _round_2(new_installment_raw)
        new_num_inst = reschedule_length
    else:
        # If the computed installment is lower than the previous EMI,
        # keep the EMI count at the floor of (new_balance / original_installment)
        # and recalculate the EMI amount as new_balance / new_num_inst so that
        # each EMI is slightly higher than the previous EMI.
        q = int(new_balance / original_installment)
        if q <= 0:
            q = 1
        new_num_inst = q
        new_installment = _round_2(new_balance / Decimal(new_num_inst))

    # ------------------------------------------------------------------
    # Option A: integer base EMIs with a final adjusted installment.
    # We keep new_balance fixed (outstanding + penalty),
    # use an integer base installment for most EMIs, and allow
    # the last EMI to be adjusted separately. Business has requested
    # that the last EMI also be an integer amount, rounded with
    # .5 up (>= .5 -> round up, < .5 -> round down).
    # ------------------------------------------------------------------
    base_integer_installment = None
    base_installments_count = None
    last_installment_amount = None

    if new_balance > 0 and new_num_inst > 0:
        # Start from the current per-EMI value and snap to integer
        base_integer_installment = new_installment.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        if base_integer_installment <= 0:
            base_integer_installment = Decimal('1')

        # How many full integer EMIs can we pay with this base amount?
        base_installments_count = int(new_balance // base_integer_installment)
        if base_installments_count <= 0:
            base_installments_count = 1

        used_by_base = base_integer_installment * base_installments_count
        last_installment_amount = new_balance - used_by_base

        # Total installments = base_installments_count + (1 extra if there is remainder)
        if last_installment_amount > Decimal('0.005'):
            new_num_inst = base_installments_count + 1
            # Round the last EMI to an integer with .5 up logic so that
            # examples like 136.60 -> 137 and 136.40 -> 136.
            last_installment_amount = last_installment_amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            if last_installment_amount <= 0:
                last_installment_amount = Decimal('1')
        else:
            last_installment_amount = Decimal('0.00')
            new_num_inst = base_installments_count

        # Store the base integer amount as the representative new_installment
        new_installment = base_integer_installment

    # Start the new rescheduled EMIs from the day after today (reschedule date)
    start_date = today
    delta_days = 1 if original_freq == 'daily' else 7

    # Build schedule rows purely for logging/snapshot purposes.
    # We intentionally do NOT modify existing LoanEMISchedule rows here.
    schedule_rows = []
    for i in range(1, new_num_inst + 1):
        # First installment is always the next day after today.
        # Subsequent installments are spaced by delta_days (1 for daily, 7 for weekly)
        offset_days = 1 + (i - 1) * delta_days
        installment_date = start_date + timezone.timedelta(days=offset_days)

        # Decide the installment amount for this row:
        # - For the first N-1 installments, use the base integer EMI
        # - For the last one, if there is a remainder, use last_installment_amount
        if (
            last_installment_amount
            and base_integer_installment is not None
            and i == new_num_inst
        ):
            inst_amount = last_installment_amount
        else:
            inst_amount = base_integer_installment or new_installment

        principal_per_inst = _round_2(inst_amount * principal_ratio)
        interest_per_inst = _round_2(inst_amount * interest_ratio)

        schedule_rows.append({
            'installment_date': installment_date,
            'frequency': original_freq,
            'installment_amount': inst_amount,
            'principal_amount': principal_per_inst,
            'interest_amount': interest_per_inst,
        })

    # Determine the new reschedule number for this loan based on how many
    # times it has already been rescheduled. This ensures that
    # LoanRescheduleLog.reschedule_no and LoanPeriod.reschedule_count
    # always reflect the actual Nth reschedule for the loan (1, 2, 3, ...)
    existing_logs_count = LoanRescheduleLog.objects.filter(loan_application=loan).count()
    reschedule_no = existing_logs_count + 1

    # Update the base period metadata and create a new LoanPeriod snapshot
    # representing this rescheduled term. This allows us to distinguish
    # original vs rescheduled periods for the same loan.
    period.reschedule_count = reschedule_no
    if period.original_installment_size is None:
        period.original_installment_size = original_installment
    if period.original_frequency is None:
        period.original_frequency = original_freq
    period.save(update_fields=[
        'reschedule_count',
        'original_installment_size',
        'original_frequency',
    ])

    from loan.models import LoanPeriod as LoanPeriodModel

    # Find the most recent period with remaining amounts by walking up the chain
    latest_period = period
    while latest_period.original_period and latest_period.remaining_balance is None:
        latest_period = latest_period.original_period

    # Create new period with remaining amounts from latest period that has values.
    # Carry forward the computed reschedule_no so this snapshot reflects
    # the actual reschedule number (1, 2, 3, ...).
    new_period = LoanPeriodModel.objects.create(
        loan_application=loan,
        loan_amount=period.loan_amount,
        rate_of_interest=period.rate_of_interest,
        installment_size=new_installment,
        realizable_amount=new_balance,
        number_of_installments=new_num_inst,
        # Carry forward remaining amounts from latest period with values
        remaining_balance=latest_period.remaining_balance if latest_period.remaining_balance is not None else Decimal('0'),
        remaining_principal=latest_period.remaining_principal if latest_period.remaining_principal is not None else Decimal('0'),
        remaining_interest=latest_period.remaining_interest if latest_period.remaining_interest is not None else Decimal('0'),
        reschedule_count=reschedule_no,
        original_installment_size=period.original_installment_size,
        original_frequency=period.original_frequency,
        is_reschedule=True,
        original_period=period,
    )

    log = LoanRescheduleLog.objects.create(
        loan_application=loan,
        period=new_period,
        reschedule_no=reschedule_no,
        old_outstanding=outstanding,
        penalty_rate=penalty_rate,
        penalty_amount=penalty_amount,
        new_total_balance=new_balance,
        new_installment_amount=new_installment,
        new_number_of_installments=new_num_inst,
        reschedule_unit=reschedule_unit,
        reschedule_length=reschedule_length,
        remarks=remarks or '',
        created_by=branch_employee,
    )

    # Create EMI reschedule snapshot linked to this log
    for row in schedule_rows:
        LoanEMIReschedule.objects.create(
            loan_application=loan,
            reschedule_log=log,
            installment_date=row['installment_date'],
            frequency=row['frequency'],
            installment_amount=row['installment_amount'],
            principal_amount=row['principal_amount'],
            interest_amount=row['interest_amount'],
        )

    # Mark existing EMI schedules for this loan as rescheduled (flag only; no amount/date change)
    LoanEMISchedule.objects.filter(loan_application=loan).update(reschedule=1)

    return {
        "loan_ref_no": loan.loan_ref_no,
        "outstanding": str(outstanding),
        "penalty_rate": str(penalty_rate),
        "penalty_amount": str(penalty_amount),
        "new_balance": str(new_balance),
        "new_installment": str(new_installment),
        "new_number_of_installments": new_num_inst,
        "reschedule_count": reschedule_no,
        "frequency": original_freq,
    }
