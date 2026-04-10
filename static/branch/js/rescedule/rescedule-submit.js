window.openRescheduleModal = function () {
    const modal = document.getElementById('reschedule-modal');
    if (!modal) return;
    modal.classList.remove('hidden');

    const meta = window.RESCHEDULE_META || {};
    const outstanding = Number(meta.outstanding_balance ?? meta.remaining_balance ?? 0);
    const count = Number(meta.reschedule_count || 0);
    const freq = meta.frequency || null;
    const prevEmi = Number(meta.previous_installment_amount || 0);

    // Dynamically update the Reschedule Period label based on loan frequency
    const periodLabelEl = document.getElementById('reschedule-period-label');
    if (periodLabelEl) {
        let unitText = 'Days';
        if (freq === 'weekly') {
            unitText = 'Weekly';
        } else if (freq === 'monthly') {
            unitText = 'Monthly';
        } else {
            unitText = 'Days'; // default / daily
        }
        periodLabelEl.textContent = `Reschedule Period (${unitText})`;
    }

    // Prefill basic fields
    const outEl = document.getElementById('reschedule-outstanding');
    if (outEl) outEl.value = outstanding.toFixed(2);
    const countEl = document.getElementById('reschedule-count');
    if (countEl) countEl.value = count + 1; // show count after this reschedule

    // Decide default penalty rate and period based on frequency
    let rate = 6.0;
    let length = 30;
    if (freq === 'weekly') {
        // Weekly loans: 5 weeks at 3%
        rate = 3.0;
        length = 5;
    }

    const rateEl = document.getElementById('reschedule-penalty-rate');
    if (rateEl) rateEl.value = rate.toFixed(2);
    const periodEl = document.getElementById('reschedule-period');
    if (periodEl) periodEl.value = String(length);

    const errorEl = document.getElementById('reschedule-error');
    if (errorEl) {
        errorEl.classList.add('hidden');
        errorEl.textContent = '';
    }

    // Calculate initial preview
    updateReschedulePreview();

    // Add event listeners for dynamic updates
    const penaltyRateEl = document.getElementById('reschedule-penalty-rate');
    const periodInputEl = document.getElementById('reschedule-period');
    
    if (penaltyRateEl) {
        penaltyRateEl.removeEventListener('input', updateReschedulePreview);
        penaltyRateEl.addEventListener('input', updateReschedulePreview);
    }
    
    if (periodInputEl) {
        periodInputEl.removeEventListener('input', updateReschedulePreview);
        periodInputEl.addEventListener('input', updateReschedulePreview);
    }
};

function updateReschedulePreview() {
    const meta = window.RESCHEDULE_META || {};
    const outstanding = Number(document.getElementById('reschedule-outstanding').value || 0);
    const rate = Number(document.getElementById('reschedule-penalty-rate').value || 0);
    const periodVal = Number(document.getElementById('reschedule-period').value || 0);
    const prevEmi = Number(meta.previous_installment_amount || 0);
    
    // Calculate penalty and new balance
    const penalty = outstanding * rate / 100;
    const newBalance = outstanding + penalty;
    
    // Business rule for EMIs:
    // Only apply the 30/prevEmi logic when New Total Balance is GREATER than previous EMI amount.
    // Otherwise, use a single installment equal to New Total Balance.
    let emiCount = 0;
    let newInstallment = 0;

    if (newBalance > 0) {
        if (prevEmi > 0 && newBalance > prevEmi) {
            // Use current Reschedule Period as base EMI count (default 30 for daily, 5 for weekly)
            const baseCount = periodVal > 0 ? periodVal : 30;
            const baseInstallment = newBalance / baseCount;

            if (baseInstallment < prevEmi) {
                // Fallback: use previous EMI amount to determine count
                // Example: 958.24 / 113 ≈ 8.48 -> emiCount = 8, and
                // the extra 0.48 is distributed across these EMIs
                emiCount = Math.floor(newBalance / prevEmi);
                if (emiCount < 1) emiCount = 1;
                newInstallment = newBalance / emiCount;
            } else {
                // Use fixed EMIs based on the chosen period
                emiCount = baseCount;
                newInstallment = baseInstallment;
            }
        } else {
            // When New Total Balance is not greater than previous EMI, use a single EMI
            emiCount = 1;
            newInstallment = newBalance;
        }
    }

    // Option A: integer base EMI, last EMI adjusted to match total balance
    // We keep New Total Balance fixed (outstanding + penalty),
    // use an integer base installment for most EMIs, and allow
    // the last EMI to be different (possibly decimal) if needed.
    let baseInstallmentInt = 0;
    let totalInstallments = 0;
    if (newBalance > 0 && emiCount > 0) {
        // Start from the current per-EMI value and snap to integer
        baseInstallmentInt = Math.round(newBalance / emiCount);
        if (baseInstallmentInt < 1) {
            baseInstallmentInt = 1;
        }

        // How many full integer EMIs can we pay with this base amount?
        const baseCount = Math.floor(newBalance / baseInstallmentInt) || 1;
        const usedByBase = baseInstallmentInt * baseCount;
        const lastAmount = newBalance - usedByBase;

        // Total installments = baseCount + (1 extra if there is remainder)
        if (lastAmount > 0.005) {
            totalInstallments = baseCount + 1;
        } else {
            totalInstallments = baseCount;
        }
    }

    // Update EMI count field
    const emiCountEl = document.getElementById('reschedule-emi-count');
    if (emiCountEl) emiCountEl.value = totalInstallments || emiCount;
    
    // Update preview fields
    const penEl = document.getElementById('reschedule-penalty-amount');
    if (penEl) penEl.value = penalty.toFixed(2);
    
    const newBalEl = document.getElementById('reschedule-new-balance');
    if (newBalEl) newBalEl.value = newBalance.toFixed(2);
    
    const newInstEl = document.getElementById('reschedule-new-installment');
    if (newInstEl) newInstEl.value = Number.isFinite(baseInstallmentInt) && baseInstallmentInt > 0
        ? baseInstallmentInt
        : (Number.isFinite(newInstallment) ? Math.round(newInstallment) : 0);
}

window.closeRescheduleModal = function () {
    const modal = document.getElementById('reschedule-modal');
    if (!modal) return;
    modal.classList.add('hidden');
};

window.handleRescheduleConfirm = function () {
    const btn = document.getElementById('reschedule-confirm-btn');
    if (!btn || btn.disabled) return;

    const errorEl = document.getElementById('reschedule-error');
    if (errorEl) {
        errorEl.classList.add('hidden');
        errorEl.textContent = '';
    }

    const outstanding = Number(document.getElementById('reschedule-outstanding').value || 0);
    const rate = Number(document.getElementById('reschedule-penalty-rate').value || 0);
    const remarks = document.getElementById('reschedule-remarks').value || '';
    
    // Get the new total balance from the preview (already calculated)
    const newBalanceEl = document.getElementById('reschedule-new-balance');
    const newBalance = newBalanceEl ? Number(newBalanceEl.value || 0) : 0;
    
    // Get the number of reschedule EMIs (calculated based on new balance / previous EMI)
    const emiCountEl = document.getElementById('reschedule-emi-count');
    const emiCount = emiCountEl ? Number(emiCountEl.value || 0) : 0;

    if (outstanding <= 0) {
        if (errorEl) {
            errorEl.textContent = 'Outstanding balance must be positive.';
            errorEl.classList.remove('hidden');
        }
        return;
    }
    
    if (emiCount <= 0) {
        if (errorEl) {
            errorEl.textContent = 'Could not calculate number of installments. Please check the values.';
            errorEl.classList.remove('hidden');
        }
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Rescheduling...';

    const payload = {
        penalty_rate: rate,
        reschedule_length: emiCount, // Use the calculated number of EMIs
        remarks: remarks,
    };

    fetch(`/branch/api/loan-reschedule/${encodeURIComponent(window.loanRefNo)}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify(payload),
    })
    .then(res => res.json().then(data => ({ ok: res.ok, data })))
    .then(({ ok, data }) => {
        if (!ok) {
            throw new Error(data.detail || 'Failed to reschedule loan');
        }
        // Success
        if (window.showToast) {
            window.showToast('Loan rescheduled successfully.', 'success');
        }
        closeRescheduleModal();
        // Refresh EMI schedule
        if (window.loanRefNo && typeof fetchEmiSchedules === 'function') {
            fetchEmiSchedules(window.loanRefNo);
        }
    })
    .catch(err => {
        console.error('Reschedule error:', err);
        if (errorEl) {
            errorEl.textContent = err.message || 'An unexpected error occurred while rescheduling the loan.';
            errorEl.classList.remove('hidden');
        }
    })
    .finally(() => {
        btn.disabled = false;
        btn.textContent = 'Reschedule Loan';
    });
};