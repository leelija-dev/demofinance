document.addEventListener('DOMContentLoaded', function () {
    setTimeout(()=>{
        applyCollectedStateToTable();
    }, 3000)
    
    // const searchInput = document.getElementById('loanSearch');
    // const suggestionsContainer = document.getElementById('loanSuggestions');
    let loansData = [];

    // Check if loan_ref_no is passed via URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const loanRefNo = urlParams.get('loan_ref_no');
    
    // Initial load of loans
    fetchLoans();

    // If loan_ref_no is provided in URL, auto-load that loan's EMI schedule
    if (loanRefNo) {
        // searchInput.value = loanRefNo;
        fetchEmiSchedules(loanRefNo);
    }

    // Show suggestions on input focus or click
    // searchInput.addEventListener('focus', showSuggestions);
    // searchInput.addEventListener('click', showSuggestions);

    // Hide suggestions when clicking outside
    // document.addEventListener('click', function (e) {
    //     if (!searchInput.contains(e.target) && !suggestionsContainer.contains(e.target)) {
    //         suggestionsContainer.classList.add('hidden');
    //     }
    // });

    // Fetch loans for the dropdown
    function fetchLoans() {
        fetch('{% url "branch:api_emi_statement" %}')
            .then(response => response.json())
            .then(data => {
                loansData = data;
                // console.log('Loan data loaded:', loansData);
            })
            .catch(error => {
                console.error('Error fetching loan data:', error);
            });
    }

    // Show loan suggestions in the search dropdown
    function showSuggestions() {
        if (loansData.length === 0) return;

        // const searchTerm = searchInput.value.toLowerCase();
        // const filteredLoans = loansData.filter(loan =>
        //     loan.loan_ref_no.toLowerCase().includes(searchTerm) ||
        //     (loan.customer_name && loan.customer_name.toLowerCase().includes(searchTerm))
        // );

        if (filteredLoans.length > 0) {
            suggestionsContainer.innerHTML = filteredLoans.map(loan => `
                <div class="flex justify-between px-4 py-2 hover:bg-gray-100 cursor-pointer" 
                     onclick="selectLoan('${loan.loan_ref_no}')">
                    <div class="font-medium">${loan.loan_ref_no}</div>
                    <div>-</div>
                    <div class="text-sm text-gray-500">${loan.customer_name || 'N/A'}</div>
                </div>
            `).join('');
            suggestionsContainer.classList.remove('hidden');
        } else {
            suggestionsContainer.innerHTML = '<div class="px-4 py-2 text-gray-500">No matching loans found</div>';
            suggestionsContainer.classList.remove('hidden');
        }
    }

    // Update suggestions while typing
    // searchInput.addEventListener('input', showSuggestions);

    // Select a loan from suggestions
    window.selectLoan = function (loanRefNo) {
        // searchInput.value = loanRefNo;
        suggestionsContainer.classList.add('hidden');
        fetchEmiSchedules(loanRefNo);
    };

    // Initialize agent assignments
    setTimeout(() => {
        document.querySelectorAll('[id^="agent-display-"]').forEach(display => {
            const loanRefNo = display.id.replace('agent-display-', '');
            const select = document.getElementById(`agent-select-${loanRefNo}`);
            if (select && select.value) {
                const selectedOption = select.options[select.selectedIndex];
                if (selectedOption && selectedOption.text) {
                    updateAgentAssignmentUI(loanRefNo, selectedOption.text);
                }
            }
        });
    }, 500);

    // ---- fetching emi collected detail ---- //
    fetch('/branch/api/emi-collected-detail/')
        .then(response => response.json())
        .then(data => {
            // Build a Map of collected emi_ids and store globally
            window.EMI_STATUS_BY_ID = new Map((data || []).map(item => [String(item.emi_id), item.status]));
            window.COLLECTED_EMI_IDS = new Set((data || []).map(item => String(item.emi_id)));
            window.COLLECTED_EMI_AMOUNTS = new Map((data || []).map(item => [String(item.emi_id), item.amount_received]));
            window.COLLECTED_EMI_PRINCIPAL_AMOUNTS = new Map((data || []).map(item => [String(item.emi_id), item.principal_received]));
            window.COLLECTED_EMI_INTEREST_AMOUNTS = new Map((data || []).map(item => [String(item.emi_id), item.interest_received]));
            window.SCHEDULE_INSTALLMENT_AMOUNTS = new Map((data || []).map(item => [String(item.emi_id), item.installment_amount]));
            window.SCHEDULE_PRINCIPAL_AMOUNTS = new Map((data || []).map(item => [String(item.emi_id), item.principal_amount]));
            window.SCHEDULE_INTEREST_AMOUNTS = new Map((data || []).map(item => [String(item.emi_id), item.interest_amount]));
            window.COLLECTED_EMI_BY_BRANCH = new Map((data || []).map(item => [String(item.emi_id), item.collected_by_branch]));
            // console.log('collected by branch-', window.COLLECTED_EMI_BY_BRANCH);
            
            // Apply to any currently rendered table
            applyCollectedStateToTable();
            // console.log('emi collect data-', data);
    })

    // ------- fetching all paid emi scedule --------- //
    fetch('/branch/api/paid-emi-scedule/')
    .then(response => response.json())
    .then(data => {
        // console.log('paid emi scedule-', data);
        // Make count globally accessible
        window.PAID_EMI_COUNT = (data && typeof data.count === 'number') ? data.count : 0;
        window.PAID_EMI_DATA = data.results;
    })

    fetch(`/branch/api/loan-emi-remaining/${encodeURIComponent(loanRefNo)}/`)
    .then(response => response.json())
    .then(data => {
        // console.log('remaining emi scedule----',  window.REMAINING_EMI_DATA = data);
        window.REMAINING_EMI_DATA = data;
        // Make count globally accessible
        // window.REMAINING_EMI_COUNT = (data && typeof data.count === 'number') ? data.count : 0;
        // window.REMAINING_EMI_DATA = data.results;
    })

    // ------- fetching all paid emi scedule based on loan_ref_no --------- //
    if (loanRefNo) {
        fetch(`/branch/api/loan-emi-collected/${encodeURIComponent(loanRefNo)}/`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return response.json();
            })
            .then(data => {
                // data is { count, results } per API
                const items = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
                // console.log('one item emi--', items[0].installment_amount);
                const singleInstallmentAmount = items[0].installment_amount;

                const toNum = v => {
                    const n = typeof v === 'string' ? parseFloat(v) : (typeof v === 'number' ? v : 0);
                    return Number.isFinite(n) ? n : 0;
                };
                const sumBy = (arr, key) => arr.reduce((acc, it) => acc + toNum(it?.[key]), 0);

                const paidEmiSum = sumBy(items, 'installment_amount');
                const paidPrincipalSum = sumBy(items, 'principal_amount');
                const paidInterestSum = sumBy(items, 'interest_amount');

                // Update header counters
                const emiEl = document.getElementById('collected-emi-amount');
                const prinEl = document.getElementById('collected-principal-amount');
                const intEl = document.getElementById('collected-interest-amount');
                if (emiEl) emiEl.textContent = `₹ ${paidEmiSum.toFixed(2)}`;
                if (prinEl) prinEl.textContent = `₹ ${paidPrincipalSum.toFixed(2)}`;
                if (intEl) intEl.textContent = `₹ ${paidInterestSum.toFixed(2)}`;

                // Expose globally if needed elsewhere
                window.PAID_EMI_SUM_BY_LOAN = {
                    loanRefNo,
                    total_installment_amount: paidEmiSum,
                    total_principal_amount: paidPrincipalSum,
                    total_interest_amount: paidInterestSum,
                    single_installment_amount: singleInstallmentAmount,
                };

                // console.log('paid emi scedule based on loan_ref_no-', data);
            })
            .catch(err => {
                console.error('Failed to fetch paid EMI schedule by loan_ref_no:', err);
            });
    }

    
});