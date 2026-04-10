(function () {
    const modal = document.getElementById('withdrawModal');
    const cfg = document.getElementById('withdrawModalConfig');
    const apiUrl = cfg ? (cfg.getAttribute('data-api-url') || '').trim() : '';

    const closeBtn = document.getElementById('withdrawModalClose');
    const cancelBtn = document.getElementById('withdrawCancel');
    const form = document.getElementById('withdrawForm');

    const accountIdEl = document.getElementById('withdrawAccountId');
    const applicationIdEl = document.getElementById('withdrawApplicationId');
    const amountEl = document.getElementById('withdrawAmount');

    const customerEl = document.getElementById('withdrawCustomer');
    const principalEl = document.getElementById('withdrawPrincipal');
    const interestBoxEl = document.getElementById('withdrawInterestBox');
    const interestEl = document.getElementById('withdrawInterest');
    const payableEl = document.getElementById('withdrawPayable');

    const dateEl = document.getElementById('withdrawDate');
    const paymentModeEl = document.getElementById('withdrawPaymentMode');
    const receiptNoEl = document.getElementById('withdrawReceiptNo');
    const noteEl = document.getElementById('withdrawNote');
    const submitBtn = document.getElementById('withdrawSubmit');

    if (!modal || !form || !apiUrl) return;

    const openModal = () => modal.classList.remove('hidden');
    const closeModal = () => modal.classList.add('hidden');

    const getCookie = (name) => {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    };

    const setToday = () => {
        const d = new Date();
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        dateEl.value = `${yyyy}-${mm}-${dd}`;
    };

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    const bindButtons = () => {
        document.querySelectorAll('.js-withdraw-open').forEach((btn) => {
            if (btn.dataset.bound === '1') return;
            btn.dataset.bound = '1';

            btn.addEventListener('click', () => {
                const accountId = (btn.getAttribute('data-account-id') || '').trim();
                const applicationId = (btn.getAttribute('data-application-id') || '').trim();
                const customerName = (btn.getAttribute('data-customer-name') || '').trim();
                const payableTotal = (btn.getAttribute('data-payable-total') || '0').trim();
                const payablePrincipal = (btn.getAttribute('data-payable-principal') || '0').trim();
                const payableInterest = (btn.getAttribute('data-payable-interest') || '0').trim();

                accountIdEl.value = accountId;
                applicationIdEl.value = applicationId;
                amountEl.value = payableTotal;

                customerEl.textContent = customerName || applicationId || accountId;
                principalEl.textContent = `₹${payablePrincipal}`;
                interestEl.textContent = `₹${payableInterest}`;
                payableEl.textContent = `₹${payableTotal}`;

                const interestNum = parseFloat(payableInterest);
                if (!interestNum || interestNum <= 0) {
                    interestBoxEl.classList.add('hidden');
                } else {
                    interestBoxEl.classList.remove('hidden');
                }

                receiptNoEl.value = '';
                noteEl.value = '';
                if (paymentModeEl) paymentModeEl.value = (paymentModeEl.value || 'cash');
                setToday();
                submitBtn.disabled = false;
                openModal();
            });
        });
    };

    bindButtons();

    const tbody = document.getElementById('withdrawCloseTbody') || document.getElementById('branchCollectionsTbody');
    if (tbody && typeof MutationObserver !== 'undefined') {
        const obs = new MutationObserver(() => bindButtons());
        obs.observe(tbody, { childList: true, subtree: true });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const amount = parseFloat(amountEl.value);
        if (!amount || amount <= 0) return;
        if (!dateEl.value) return;

        submitBtn.disabled = true;

        try {
            const res = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') || '',
                },
                body: JSON.stringify({
                    account_id: accountIdEl.value,
                    expected_collection_id: '',
                    collection_type: 'withdrawal',
                    amount: amountEl.value,
                    collection_date: dateEl.value,
                    payment_mode: paymentModeEl.value,
                    receipt_no: receiptNoEl.value,
                    note: noteEl.value,
                }),
            });

            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.success) {
                submitBtn.disabled = false;
                if (typeof window.showToast === 'function') {
                    window.showToast(data.detail || data.message || 'Withdraw failed.', 'error');
                }
                return;
            }

            closeModal();
            if (typeof window.showToast === 'function') {
                window.showToast('Withdraw completed.', 'success');
            }
            window.location.reload();
        } catch (err) {
            submitBtn.disabled = false;
            if (typeof window.showToast === 'function') {
                window.showToast('Withdraw failed.', 'error');
            }
        }
    });
})();
