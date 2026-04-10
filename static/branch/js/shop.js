// static/branch/js/shop.js

// Utility: get CSRF token from cookies
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}


// Search + category filter
(function initShopFilters() {
  const searchInput = document.getElementById('shop-search-input');
  const categorySelect = document.getElementById('shop-category-select');
  const activeToggle = document.getElementById('shop-active-toggle');
  const rows = () => Array.from(document.querySelectorAll('#shop-table-body tr[data-shop-id]'));

  if (!searchInput && !categorySelect && !activeToggle) return;

  const applyFilters = () => {
    const q = (searchInput?.value || '').trim().toLowerCase();
    const cat = (categorySelect?.value || '').trim().toLowerCase();
    const showActiveOnly = activeToggle?.checked ?? true; // Default to true (show active only)

    let visible = 0;
    rows().forEach((row) => {
      const rowCat = (row.dataset.category || '').toLowerCase();
      const rowSearch = (row.dataset.search || '').toLowerCase();
      const isActive = !row.classList.contains('opacity-60');
      
      const okCat = !cat || rowCat === cat;
      const okSearch = !q || rowSearch.includes(q);
      // When toggle is checked (true), show only active shops. When unchecked (false), show all shops
      const okActive = showActiveOnly ? isActive : true;
      const show = okCat && okSearch && okActive;
      
      row.classList.toggle('hidden', !show);
      if (show) visible += 1;
    });

    // Update count if element exists (optional)
    const countEl = document.getElementById('shop-count');
    if (countEl) {
      countEl.textContent = visible ? `${visible} shop${visible === 1 ? '' : 's'}` : 'No shops';
    }
  };

  searchInput?.addEventListener('input', applyFilters);
  categorySelect?.addEventListener('change', applyFilters);
  
  // Toggle event handler
  if (activeToggle) {
    activeToggle.addEventListener('change', (e) => {
      console.log('Toggle changed:', e.target.checked);
      applyFilters();
      // Update toggle text
      const toggleText = document.getElementById('toggle-text');
      if (toggleText) {
        toggleText.textContent = e.target.checked ? 'Active shops only' : 'All shops';
      }
      // Update URL parameter
      const url = new URL(window.location.href);
      if (e.target.checked) {
        url.searchParams.set('show_active', 'true');
      } else {
        url.searchParams.delete('show_active');
      }
      window.history.replaceState({}, '', url.toString());
    });
  }
  
  // Initialize toggle state from URL parameter
  const urlParams = new URLSearchParams(window.location.search);
  const showActiveParam = urlParams.get('show_active');
  if (showActiveParam === 'false' && activeToggle) {
    activeToggle.checked = false;
    const toggleText = document.getElementById('toggle-text');
    if (toggleText) {
      toggleText.textContent = 'All shops';
    }
  }
  
  // Apply filters on page load
  setTimeout(applyFilters, 100);
})();

// View Shop Details modal
function viewShopDetails(triggerEl) {
  console.log('viewShopDetails called with:', triggerEl);
  
  const container = triggerEl?.closest('tr') || triggerEl?.closest('div[data-shop-id]');
  if (!container) {
    console.log('No container found');
    return;
  }

  const shopId = container.dataset.shopId || '';
  const name = container.dataset.shopName || '';
  const status = container.dataset.shopStatus || '';
  const category = container.dataset.shopCategory || '';
  const owner = container.dataset.shopOwner || '';
  const email = container.dataset.shopEmail || '';
  const contact = container.dataset.shopContact || '';
  const bankCount = container.dataset.shopBankCount || '';
  const address = container.dataset.shopAddress || '';

  console.log('Shop data:', { shopId, name, status, category, owner, email, contact, bankCount, address });

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) {
      el.textContent = value && String(value).trim() ? value : '-';
      console.log(`Set ${id} to:`, value);
    } else {
      console.log(`Element not found: ${id}`);
    }
  };

  setText('shop-detail-id', shopId);
  setText('shop-detail-name', name);
  setText('shop-detail-status', status ? status.charAt(0).toUpperCase() + status.slice(1) : '');
  setText('shop-detail-category', category);
  setText('shop-detail-owner', owner);
  setText('shop-detail-email', email);
  setText('shop-detail-contact', contact);
  setText('shop-detail-bank-count', bankCount);
  setText('shop-detail-address', address);

  const modal = document.getElementById('shopDetailsModal');
  if (modal) {
    modal.classList.remove('hidden');
    console.log('Modal opened');
  } else {
    console.log('Modal not found');
  }
}

function closeViewShopDetailsModal() {
  document.getElementById('shopDetailsModal')?.classList.add('hidden');
}

// View Shop Bank Accounts
function viewShopBankAccounts(triggerEl, shopName) {
  // Handle both call styles: viewShopBankAccounts(button) or viewShopBankAccounts(shopId, shopName)
  let shopId, name;
  if (typeof triggerEl === 'object' && triggerEl.closest) {
    // Called with button element
    const container = triggerEl?.closest('tr') || triggerEl?.closest('div[data-shop-id]');
    if (!container) return;
    shopId = container.dataset.shopId || '';
    name = shopName || container.dataset.shopName || '';
  } else {
    // Called with shopId and shopName parameters
    shopId = triggerEl;
    name = shopName;
  }

  document.getElementById('bankAccountsModal')?.classList.remove('hidden');

  fetch(`/branch/api/shop-bank-accounts/?shop_id=${encodeURIComponent(shopId)}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken') || '',
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
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3 3 3 0 00-3-3H6a3 3 0 00-3 3 3 0 003 3z"></path>
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
  document.getElementById('bankAccountsModal')?.classList.add('hidden');
}

function closeModal(modalId) {
  document.getElementById(modalId)?.classList.add('hidden');
}
