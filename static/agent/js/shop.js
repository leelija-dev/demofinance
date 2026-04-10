// Shop Modal Functions
function openAddShopModal() {
  document.getElementById('add-shop-modal')?.classList.remove('hidden');
}

function closeAddShopModal() {
  document.getElementById('add-shop-modal')?.classList.add('hidden');
  document.getElementById('add-shop-form')?.reset();
}

function submitAddShopForm() {
  const form = document.getElementById('add-shop-form');
  if (!form) return;

  // Create JSON object from form data
  const formData = new FormData(form);
  const data = {};
  for (let [key, value] of formData.entries()) {
    data[key] = value;
  }

  fetch('/agent/api/shops/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify(data),
  })
    .then(async (response) => {
      const contentType = response.headers.get('content-type') || '';
      const isJson = contentType.includes('application/json');

      if (isJson) {
        const payload = await response.json();
        return { ok: response.ok, payload };
      }

      const text = await response.text();
      return {
        ok: response.ok,
        payload: {
          success: false,
          message: text || `Request failed with status ${response.status}`,
        },
      };
    })
    .then(({ ok, payload }) => {
      if (ok && payload && payload.success) {
        location.reload();
        return;
      }

      alert(payload?.message || 'Failed to add shop. Please try again.');
    })
    .catch((error) => {
      console.error('Error adding shop:', error);
      alert('An error occurred while adding the shop. Please try again.');
    });
}

// Shop Bank Account Modal Functions
function openAddShopBankModal(shopId, shopName) {
  const shopIdEl = document.getElementById('bank-modal-shop-id');
  const shopNameEl = document.getElementById('bank-modal-shop-name');
  if (shopIdEl) shopIdEl.value = shopId;
  if (shopNameEl) shopNameEl.textContent = shopName;
  document.getElementById('add-shop-bank-modal')?.classList.remove('hidden');
}

let currentBankAccountsShopId = null;
let currentBankAccountsShopName = '';

let currentShopDetailsShopId = null;
let lastLoadedLoansShopId = null;
let lastLoadedTransactionsShopId = null;

function openAddShopBankModalFromView() {
  if (!currentBankAccountsShopId) return;
  closeViewShopBankModal();
  openAddShopBankModal(currentBankAccountsShopId, currentBankAccountsShopName);
}

function closeAddShopBankModal() {
  document.getElementById('add-shop-bank-modal')?.classList.add('hidden');
  document.getElementById('add-shop-bank-form')?.reset();
}

function submitAddShopBankForm() {
  const form = document.getElementById('add-shop-bank-form');
  if (!form) return;

  const formData = new FormData(form);

  const data = {};
  for (const [key, value] of formData.entries()) {
    data[key] = value;
  }
  data.shop_id = document.getElementById('bank-modal-shop-id')?.value;

  if (!data.shop_id || !String(data.shop_id).trim()) {
    alert('Shop ID is missing. Please close the modal and open it again from the correct shop card.');
    return;
  }

  const requiredFields = ['account_holder_name', 'bank_name', 'account_number', 'ifsc_code'];
  for (const field of requiredFields) {
    if (!data[field] || !String(data[field]).trim()) {
      alert(`${field.replaceAll('_', ' ')} is required.`);
      return;
    }
  }

  console.log('Submitting shop bank account payload:', data);

  fetch('/agent/api/shop-bank-accounts/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify(data),
  })
    .then(async (response) => {
      const contentType = response.headers.get('content-type') || '';
      const isJson = contentType.includes('application/json');

      if (isJson) {
        const payload = await response.json();
        return { ok: response.ok, payload };
      }

      const text = await response.text();
      return { ok: response.ok, payload: { success: false, message: text } };
    })
    .then(({ ok, payload }) => {
      if (ok && payload && payload.success) {
        location.reload();
        return;
      }

      alert(payload?.message || 'Failed to add bank account. Please try again.');
    })
    .catch((error) => {
      console.error('Error adding bank account:', error);
      alert('An error occurred while adding bank account. Please try again.');
    });
}

// View Shop Bank Accounts Functions
function viewShopBankAccounts(shopId, shopName) {
  currentBankAccountsShopId = shopId;
  currentBankAccountsShopName = shopName;

  const titleName = document.getElementById('view-bank-modal-shop-name');
  if (titleName) titleName.textContent = shopName;

  document.getElementById('view-shop-bank-modal')?.classList.remove('hidden');

  fetch(`/agent/api/shop-bank-accounts/?shop_id=${encodeURIComponent(shopId)}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
  })
    .then((response) => response.json())
    .then((data) => {
      const bankAccountsList = document.getElementById('bank-accounts-list');
      if (!bankAccountsList) return;

      if (data.success && Array.isArray(data.bank_accounts) && data.bank_accounts.length > 0) {
        let html = '<div class="space-y-4">';

        data.bank_accounts.forEach((account) => {
          html += `
          <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p class="text-sm font-medium text-gray-600 dark:text-gray-400">Account Holder</p>
                <p class="text-gray-900 dark:text-white font-medium">${account.account_holder_name ?? ''}</p>
              </div>
              <div>
                <p class="text-sm font-medium text-gray-600 dark:text-gray-400">Bank Name</p>
                <p class="text-gray-900 dark:text-white font-medium">${account.bank_name ?? ''}</p>
              </div>
              <div>
                <p class="text-sm font-medium text-gray-600 dark:text-gray-400">Account Number</p>
                <p class="text-gray-900 dark:text-white font-medium">${account.account_number ?? ''}</p>
              </div>
              <div>
                <p class="text-sm font-medium text-gray-600 dark:text-gray-400">IFSC Code</p>
                <p class="text-gray-900 dark:text-white font-medium">${account.ifsc_code ?? ''}</p>
              </div>
              <div>
                <p class="text-sm font-medium text-gray-600 dark:text-gray-400">Current Balance</p>
                <p class="text-gray-900 dark:text-white font-medium">${account.current_balance ?? ''}</p>
              </div>
            </div>
            <div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
              <p class="text-sm text-gray-500 dark:text-gray-400">
                Created: ${account.created_at ? new Date(account.created_at).toLocaleDateString() : ''}
              </p>
            </div>
          </div>
        `;
        });

        html += '</div>';
        bankAccountsList.innerHTML = html;
      } else {
        bankAccountsList.innerHTML = `
        <div class="text-center py-8">
          <div class="text-gray-400 dark:text-gray-500">
            <svg class="mx-auto h-12 w-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3 3 3 0 00-3-3H6a3 3 0 00-3 3 3 3 0 003 3z"></path>
            </svg>
            <p class="text-lg font-medium mb-2">No bank accounts found</p>
            <p class="text-sm">This shop doesn't have any bank accounts yet.</p>
          </div>
        </div>
      `;
      }
    })
    .catch((error) => {
      console.error('Error fetching bank accounts:', error);
      const bankAccountsList = document.getElementById('bank-accounts-list');
      if (!bankAccountsList) return;

      bankAccountsList.innerHTML = `
      <div class="text-center py-8">
        <div class="text-red-400 dark:text-red-500">
          <svg class="mx-auto h-12 w-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          <p class="text-lg font-medium mb-2">Error loading bank accounts</p>
          <p class="text-sm">Please try again later.</p>
        </div>
      </div>
    `;
    });
}

function closeViewShopBankModal() {
  document.getElementById('view-shop-bank-modal')?.classList.add('hidden');
}

function viewShopDetails(triggerEl) {
  const container = triggerEl?.closest('tr') || triggerEl?.closest('div[data-shop-id]');
  if (!container) return;

  currentShopDetailsShopId = container.dataset.shopId || null;
  lastLoadedLoansShopId = null;
  lastLoadedTransactionsShopId = null;

  const name = container.dataset.shopName || '';
  const status = container.dataset.shopStatus || '';
  const category = container.dataset.shopCategory || '';
  const owner = container.dataset.shopOwner || '';
  const email = container.dataset.shopEmail || '';
  const contact = container.dataset.shopContact || '';
  const bankCount = container.dataset.shopBankCount || '';
  const address = container.dataset.shopAddress || '';

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value && value.trim() ? value : '-';
  };

  setText('shop-detail-name', name);
  setText('shop-detail-status', status ? status.charAt(0).toUpperCase() + status.slice(1) : '');
  setText('shop-detail-category', category);
  setText('shop-detail-owner', owner);
  setText('shop-detail-email', email);
  setText('shop-detail-contact', contact);
  setText('shop-detail-bank-count', bankCount);
  setText('shop-detail-address', address);

  document.getElementById('view-shop-details-modal')?.classList.remove('hidden');

  // Default tab when opening
  switchShopDetailsTab('details');
}

function closeViewShopDetailsModal() {
  document.getElementById('view-shop-details-modal')?.classList.add('hidden');
  currentShopDetailsShopId = null;
  lastLoadedLoansShopId = null;
  lastLoadedTransactionsShopId = null;
  const listEl = document.getElementById('shop-loans-list');
  if (listEl) listEl.innerHTML = '';
  const loadingEl = document.getElementById('shop-loans-loading');
  if (loadingEl) loadingEl.classList.add('hidden');

  const txListEl = document.getElementById('shop-transactions-list');
  if (txListEl) txListEl.innerHTML = '';
  const txLoadingEl = document.getElementById('shop-transactions-loading');
  if (txLoadingEl) txLoadingEl.classList.add('hidden');
}

function switchShopDetailsTab(tabName) {
  // Hide all panels
  document.querySelectorAll('.shop-details-panel').forEach(panel => {
    panel.classList.add('hidden');
  });
  
  // Reset all tabs to inactive state
  document.querySelectorAll('.shop-details-tab').forEach(tab => {
    tab.classList.remove('text-blue-600', 'border-blue-600');
    tab.classList.add('text-gray-500', 'border-transparent');
  });
  
  // Show selected panel
  const selectedPanel = document.getElementById(`shop-details-panel-${tabName}`);
  if (selectedPanel) {
    selectedPanel.classList.remove('hidden');
  }
  
  // Activate selected tab
  const selectedTab = document.getElementById(`shop-details-tab-${tabName}`);
  if (selectedTab) {
    selectedTab.classList.remove('text-gray-500', 'border-transparent');
    selectedTab.classList.add('text-blue-600', 'border-blue-600');
  }

  if (tabName === 'loans') {
    loadShopLoansForCurrentShop();
  }

  if (tabName === 'transactions') {
    loadShopTransactionsForCurrentShop();
  }
}

function loadShopTransactionsForCurrentShop() {
  if (!currentShopDetailsShopId) return;

  if (lastLoadedTransactionsShopId === currentShopDetailsShopId) return;
  lastLoadedTransactionsShopId = null;

  const listEl = document.getElementById('shop-transactions-list');
  const loadingEl = document.getElementById('shop-transactions-loading');
  if (!listEl) return;

  listEl.innerHTML = '';
  if (loadingEl) loadingEl.classList.remove('hidden');

  fetch(`/agent/api/shop-transactions/?shop_id=${encodeURIComponent(currentShopDetailsShopId)}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
  })
    .then((res) => res.json())
    .then((data) => {
      if (loadingEl) loadingEl.classList.add('hidden');

      if (!data || !data.success) {
        lastLoadedTransactionsShopId = null;
        listEl.innerHTML = `
          <div class="text-center py-8">
            <div class="text-red-400 dark:text-red-500">
              <p class="text-sm">${data?.message || 'Failed to load transactions.'}</p>
            </div>
          </div>
        `;
        return;
      }

      lastLoadedTransactionsShopId = currentShopDetailsShopId;

      const txs = Array.isArray(data.transactions) ? data.transactions : [];
      if (txs.length === 0) {
        listEl.innerHTML = `
          <div class="text-center py-8">
            <div class="text-gray-400 dark:text-gray-500">
              <p class="text-sm">No transactions found for this shop.</p>
            </div>
          </div>
        `;
        return;
      }

      listEl.innerHTML = txs
        .map((tx) => {
          const dt = tx.transaction_date ? new Date(tx.transaction_date).toLocaleString() : '';
          const amount = tx.amount ? `₹${tx.amount}` : '';
          const type = tx.transaction_type || '';
          const loanRef = tx.loan_ref_no || '';
          const purpose = tx.purpose || '';
          const desc = tx.description || '';
          const acct = tx.branch_account
            ? `${tx.branch_account.bank_name || ''} ${tx.branch_account.account_number || ''}`
            : '';

          return `
            <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">${type} ${amount}</div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">${purpose}${loanRef ? ` • ${loanRef}` : ''}</div>
                </div>
                <div class="text-right">
                  <div class="text-xs text-gray-500 dark:text-gray-400">${dt}</div>
                  <div class="text-xs text-gray-700 dark:text-gray-200">${acct}</div>
                </div>
              </div>
              ${desc ? `<div class="mt-2 text-xs text-gray-600 dark:text-gray-300">${desc}</div>` : ''}
            </div>
          `;
        })
        .join('');
    })
    .catch((err) => {
      if (loadingEl) loadingEl.classList.add('hidden');
      lastLoadedTransactionsShopId = null;
      console.error('Error fetching shop transactions:', err);
      listEl.innerHTML = `
        <div class="text-center py-8">
          <div class="text-red-400 dark:text-red-500">
            <p class="text-sm">Error loading transactions. Please try again later.</p>
          </div>
        </div>
      `;
    });
}

function loadShopLoansForCurrentShop() {
  if (!currentShopDetailsShopId) return;

  if (lastLoadedLoansShopId === currentShopDetailsShopId) return;
  lastLoadedLoansShopId = null;

  const listEl = document.getElementById('shop-loans-list');
  const loadingEl = document.getElementById('shop-loans-loading');
  if (!listEl) return;

  listEl.innerHTML = '';
  if (loadingEl) loadingEl.classList.remove('hidden');

  fetch(`/agent/api/shop-loans/?shop_id=${encodeURIComponent(currentShopDetailsShopId)}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
  })
    .then((res) => res.json())
    .then((data) => {
      if (loadingEl) loadingEl.classList.add('hidden');

      if (!data || !data.success) {
        lastLoadedLoansShopId = null;
        listEl.innerHTML = `
          <div class="text-center py-8">
            <div class="text-red-400 dark:text-red-500">
              <p class="text-sm">${data?.message || 'Failed to load loans.'}</p>
            </div>
          </div>
        `;
        return;
      }

      lastLoadedLoansShopId = currentShopDetailsShopId;

      const loans = Array.isArray(data.loans) ? data.loans : [];
      if (loans.length === 0) {
        listEl.innerHTML = `
          <div class="text-center py-8">
            <div class="text-gray-400 dark:text-gray-500">
              <p class="text-sm">No loan applications found for this shop.</p>
            </div>
          </div>
        `;
        return;
      }

      listEl.innerHTML = loans
        .map((loan) => {
          const submitted = loan.submitted_at ? new Date(loan.submitted_at).toLocaleString() : '';
          const amount = loan.loan_amount ? `₹${loan.loan_amount}` : '';
          const emi = loan.emi_amount ? `₹${loan.emi_amount}` : '';
          const status = loan.status ? String(loan.status).replaceAll('_', ' ') : '';
          return `
            <div class="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 border border-gray-200 dark:border-gray-600">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">${loan.loan_ref_no || ''}</div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">${loan.customer_name || ''}</div>
                </div>
                <div class="text-right">
                  <div class="text-xs text-gray-500 dark:text-gray-400">${submitted}</div>
                  <div class="text-xs text-gray-700 dark:text-gray-200">${status}</div>
                </div>
              </div>
              <div class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                <div class="text-gray-700 dark:text-gray-200">Loan Amount: <span class="font-medium">${amount}</span></div>
                <div class="text-gray-700 dark:text-gray-200">EMI: <span class="font-medium">${emi}</span></div>
              </div>
            </div>
          `;
        })
        .join('');
    })
    .catch((err) => {
      if (loadingEl) loadingEl.classList.add('hidden');
      lastLoadedLoansShopId = null;
      console.error('Error fetching shop loans:', err);
      listEl.innerHTML = `
        <div class="text-center py-8">
          <div class="text-red-400 dark:text-red-500">
            <p class="text-sm">Error loading loans. Please try again later.</p>
          </div>
        </div>
      `;
    });
}

// Edit Shop Functions
function editShop(triggerEl) {
  const container = triggerEl?.closest('tr') || triggerEl?.closest('div[data-shop-id]');
  if (!container) return;

  const shopId = container.dataset.shopId || '';
  const name = container.dataset.shopName || '';
  const owner = container.dataset.shopOwner || '';
  const email = container.dataset.shopEmail || '';
  const contact = container.dataset.shopContact || '';
  const category = container.dataset.shopCategory || '';
  const address = container.dataset.shopAddress || '';

  const setFieldValue = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.value = value || '';
  };

  setFieldValue('edit-shop-id', shopId);
  setFieldValue('edit-shop-name', name);
  setFieldValue('edit-shop-owner', owner);
  setFieldValue('edit-shop-email', email);
  setFieldValue('edit-shop-contact', contact);
  setFieldValue('edit-shop-category', category);
  setFieldValue('edit-shop-address', address);

  document.getElementById('edit-shop-modal')?.classList.remove('hidden');
}

function closeEditShopModal() {
  document.getElementById('edit-shop-modal')?.classList.add('hidden');
  document.getElementById('edit-shop-form')?.reset();
}

function submitEditShopForm() {
  const form = document.getElementById('edit-shop-form');
  if (!form) return;

  const formData = new FormData(form);
  const shopId = formData.get('shop_id');
  if (!shopId) {
    alert('Shop ID is required.');
    return;
  }

  const data = {};
  for (const [key, value] of formData.entries()) {
    if (key !== 'shop_id') data[key] = value;
  }

  fetch(`/agent/api/shops/${encodeURIComponent(shopId)}/`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify(data),
  })
    .then((response) => response.json())
    .then((resp) => {
      if (resp.success) {
        location.reload();
      } else {
        alert(resp.message || 'Failed to update shop. Please try again.');
      }
    })
    .catch((error) => {
      console.error('Error updating shop:', error);
      alert('An error occurred while updating the shop. Please try again.');
    });
}

// Delete Shop Functions
let currentDeleteShopId = null;

function deleteShop(triggerEl) {
  const container = triggerEl?.closest('tr') || triggerEl?.closest('div[data-shop-id]');
  if (!container) return;

  const shopId = container.dataset.shopId;
  if (!shopId) return;

  currentDeleteShopId = shopId;

  // Reset modal state
  document.getElementById('delete-confirmation').checked = false;
  document.getElementById('confirm-delete-btn').disabled = true;

  // Show loading state
  document.getElementById('delete-shop-id').textContent = shopId;
  document.getElementById('delete-shop-name').textContent = 'Loading...';
  document.getElementById('delete-shop-owner').textContent = 'Loading...';
  document.getElementById('delete-shop-status').textContent = 'Loading...';
  document.getElementById('delete-bank-count').textContent = '...';
  document.getElementById('delete-loan-count').textContent = '...';
  document.getElementById('delete-recent-loans').classList.add('hidden');
  document.getElementById('delete-bank-accounts').classList.add('hidden');

  // Open modal
  document.getElementById('delete-shop-modal')?.classList.remove('hidden');

  // Fetch shop activities
  fetch(`/agent/api/shops/${encodeURIComponent(shopId)}/delete/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        const shop = data.shop;
        const activities = data.activities;

        // Update shop info
        document.getElementById('delete-shop-id').textContent = shop.shop_id;
        document.getElementById('delete-shop-name').textContent = shop.name || '-';
        document.getElementById('delete-shop-owner').textContent = shop.owner_name || '-';
        document.getElementById('delete-shop-status').textContent = shop.status ? shop.status.charAt(0).toUpperCase() + shop.status.slice(1) : '-';

        // Update counts
        document.getElementById('delete-bank-count').textContent = activities.bank_accounts_count;
        document.getElementById('delete-loan-count').textContent = activities.loan_applications_count;

        // Show recent loans if any
        if (activities.recent_loans && activities.recent_loans.length > 0) {
          document.getElementById('delete-recent-loans').classList.remove('hidden');
          const loansList = document.getElementById('delete-loans-list');
          loansList.innerHTML = activities.recent_loans.map(loan => `
            <div class="bg-gray-50 dark:bg-gray-700 rounded p-2 text-xs">
              <div class="flex justify-between">
                <span class="font-medium">${loan.loan_ref_no}</span>
                <span class="text-gray-500">${loan.submitted_at}</span>
              </div>
              <div class="mt-1 text-gray-600 dark:text-gray-400">
                ${loan.customer_name} • ₹${loan.amount} • ${loan.status}
              </div>
            </div>
          `).join('');
        }

        // Show bank accounts if any
        if (activities.bank_accounts && activities.bank_accounts.length > 0) {
          document.getElementById('delete-bank-accounts').classList.remove('hidden');
          const banksList = document.getElementById('delete-banks-list');
          banksList.innerHTML = activities.bank_accounts.map(account => `
            <div class="bg-gray-50 dark:bg-gray-700 rounded p-2 text-xs">
              <div class="flex justify-between items-center">
                <span class="font-medium">${account.bank_name}</span>
                <div class="flex items-center gap-2">
                  <span class="text-gray-500">****${account.account_number}</span>
                  ${account.is_primary ? '<span class="bg-blue-100 text-blue-800 px-1 py-0.5 rounded text-xs">Primary</span>' : ''}
                </div>
              </div>
            </div>
          `).join('');
        }
      } else {
        alert(data.message || 'Failed to fetch shop details.');
        closeDeleteShopModal();
      }
    })
    .catch((error) => {
      console.error('Error fetching shop activities:', error);
      alert('An error occurred while fetching shop details. Please try again.');
      closeDeleteShopModal();
    });
}

function closeDeleteShopModal() {
  document.getElementById('delete-shop-modal')?.classList.add('hidden');
  currentDeleteShopId = null;
}

function confirmDeleteShop() {
  if (!currentDeleteShopId) return;

  const confirmationChecked = document.getElementById('delete-confirmation').checked;
  if (!confirmationChecked) {
    alert('Please confirm that you understand the shop will be marked as inactive.');
    return;
  }

  const confirmBtn = document.getElementById('confirm-delete-btn');
  confirmBtn.disabled = true;
  confirmBtn.textContent = 'Deleting...';

  fetch(`/agent/api/shops/${encodeURIComponent(currentDeleteShopId)}/delete/`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        alert(data.message);
        location.reload();
      } else {
        alert(data.message || 'Failed to delete shop. Please try again.');
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Delete Shop';
      }
    })
    .catch((error) => {
      console.error('Error deleting shop:', error);
      alert('An error occurred while deleting the shop. Please try again.');
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Delete Shop';
    });
}

// Helper function to get CSRF token
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === `${name}=`) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Debounce helper function
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

function initShopSearchAndFilter() {
  const searchInput = document.getElementById('shop-search-input');
  const categorySelect = document.getElementById('shop-category-select');
  const shopCount = document.getElementById('shop-count');
  const tableBody = document.getElementById('shop-table-body');
  const mobileCards = document.querySelector('.md\\:hidden.space-y-4');

  if (!searchInput || !categorySelect || !shopCount || !tableBody) return;

  function filterShops() {
    const searchTerm = searchInput.value.toLowerCase().trim();
    const selectedCategory = categorySelect.value.toLowerCase().trim();

    const tableRows = tableBody.querySelectorAll('tr');
    const mobileCardDivs = mobileCards ? mobileCards.querySelectorAll(':scope > div:not(.text-center)') : [];

    let visibleCount = 0;

    tableRows.forEach((row) => {
      if (row.querySelector('td[colspan]')) return;

      const rowCategory = (row.dataset.category || '').toLowerCase();
      const rowSearch = (row.dataset.search || '').toLowerCase();

      const matchesSearch = !searchTerm || rowSearch.includes(searchTerm);
      const matchesCategory = !selectedCategory || rowCategory === selectedCategory;

      if (matchesSearch && matchesCategory) {
        row.style.display = '';
        visibleCount++;
      } else {
        row.style.display = 'none';
      }
    });

    mobileCardDivs.forEach((card) => {
      const cardCategory = (card.dataset.category || '').toLowerCase();
      const cardSearch = (card.dataset.search || '').toLowerCase();

      const matchesSearch = !searchTerm || cardSearch.includes(searchTerm);
      const matchesCategory = !selectedCategory || cardCategory === selectedCategory;

      card.style.display = matchesSearch && matchesCategory ? '' : 'none';
    });

    shopCount.textContent = visibleCount === 1 ? '1 shop' : `${visibleCount} shops`;

    const emptyTableCell = tableBody.querySelector('tr td[colspan]');
    const emptyTableRow = emptyTableCell ? emptyTableCell.closest('tr') : null;
    const emptyMobileDiv = mobileCards?.querySelector('.text-center.py-12');

    if (visibleCount === 0) {
      if (emptyTableRow) emptyTableRow.style.display = '';
      if (emptyMobileDiv) emptyMobileDiv.style.display = '';
    } else {
      if (emptyTableRow) emptyTableRow.style.display = 'none';
      if (emptyMobileDiv) emptyMobileDiv.style.display = 'none';
    }
  }

  searchInput.addEventListener('input', debounce(filterShops, 300));
  categorySelect.addEventListener('change', filterShops);
}

// Expose functions globally for inline onclick handlers
window.openAddShopModal = openAddShopModal;
window.closeAddShopModal = closeAddShopModal;
window.submitAddShopForm = submitAddShopForm;
window.openAddShopBankModal = openAddShopBankModal;
window.openAddShopBankModalFromView = openAddShopBankModalFromView;
window.closeAddShopBankModal = closeAddShopBankModal;
window.submitAddShopBankForm = submitAddShopBankForm;
window.viewShopBankAccounts = viewShopBankAccounts;
window.closeViewShopBankModal = closeViewShopBankModal;
window.viewShopDetails = viewShopDetails;
window.closeViewShopDetailsModal = closeViewShopDetailsModal;
window.switchShopDetailsTab = switchShopDetailsTab;
window.editShop = editShop;
window.closeEditShopModal = closeEditShopModal;
window.submitEditShopForm = submitEditShopForm;
window.deleteShop = deleteShop;
window.closeDeleteShopModal = closeDeleteShopModal;
window.confirmDeleteShop = confirmDeleteShop;

document.addEventListener('DOMContentLoaded', () => {
  initShopSearchAndFilter();
  
  // Delete modal checkbox listener
  const confirmationCheckbox = document.getElementById('delete-confirmation');
  const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
  
  if (confirmationCheckbox && confirmDeleteBtn) {
    confirmationCheckbox.addEventListener('change', (e) => {
      confirmDeleteBtn.disabled = !e.target.checked;
    });
  }
  
  // Delete button click listener
  if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener('click', confirmDeleteShop);
  }
  
  // Show active/inactive shops toggle listener
  const showInactiveCheckbox = document.getElementById('show-inactive-shops');
  const toggleTrack = document.getElementById('shop-status-toggle-track');
  const toggleKnob = document.getElementById('shop-status-toggle-knob');
  
  if (showInactiveCheckbox && toggleTrack && toggleKnob) {
    const updateToggleUI = (isActive) => {
      toggleTrack.classList.remove('bg-green-600', 'bg-gray-300', 'dark:bg-gray-600');
      toggleTrack.classList.add(isActive ? 'bg-green-600' : 'bg-gray-300');
      if (!isActive) {
        toggleTrack.classList.add('dark:bg-gray-600');
      }

      toggleKnob.classList.remove('translate-x-0', 'translate-x-5');
      toggleKnob.classList.add(isActive ? 'translate-x-5' : 'translate-x-0');
    };

    // Set initial state based on URL parameter (default is checked = active shops)
    const urlParams = new URLSearchParams(window.location.search);
    const showActive = urlParams.get('show_active') !== 'false';  // Default to true
    showInactiveCheckbox.checked = showActive;
    updateToggleUI(showActive);
    
    // Add change listener
    showInactiveCheckbox.addEventListener('change', (e) => {
      const newUrl = new URL(window.location);
      if (e.target.checked) {
        // Switch ON = show active shops
        newUrl.searchParams.set('show_active', 'true');
        updateToggleUI(true);
      } else {
        // Switch OFF = show inactive shops
        newUrl.searchParams.set('show_active', 'false');
        updateToggleUI(false);
      }
      window.location.href = newUrl.toString();
    });
  }
});