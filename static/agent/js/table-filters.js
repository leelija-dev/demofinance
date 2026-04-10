// Expose a tiny helper onto window
window.AgentFilters = (function() {
  function applyFilters(tableBody, noDataEl, idx, state) {
    if (!tableBody) return;
    const allRows = Array.from(tableBody.querySelectorAll('tr'));
    // Treat rows with '.details-row' as children of the preceding main row
    const mainRows = allRows.filter(r => !r.classList.contains('details-row'));
    let visible = 0;

    mainRows.forEach(row => {
      // Loan filter (substring match)
      let okLoan = true;
      if (state.loan) {
        const cell = row.querySelector(`td:nth-child(${idx.loan})`);
        const txt = (cell ? cell.textContent : '').toLowerCase();
        okLoan = txt.includes(state.loan);
      }

      // Date filter (exact match after display formatting)
      let okDate = true;
      if (state.date) {
        const cell = row.querySelector(`td:nth-child(${idx.date})`);
        const txt = (cell ? cell.textContent.trim() : '');
        okDate = (txt === state.date);
      }

      // Status filter (exact, lowercase)
      let okStatus = true;
      if (state.status && idx.status > 0) {
        const cell = row.querySelector(`td:nth-child(${idx.status})`);
        const txt = (cell ? cell.textContent.trim().toLowerCase() : '');
        okStatus = (txt === state.status);
      }

      const show = okLoan && okDate && okStatus;
      row.style.display = show ? '' : 'none';

      // Sync details row (next sibling with '.details-row') if present
      const detailsRow = row.nextElementSibling;
      if (detailsRow && detailsRow.classList && detailsRow.classList.contains('details-row')) {
        if (!show) {
          detailsRow.style.display = 'none';
          detailsRow.classList.remove('expanded');
        } else {
          // Only show if it was expanded
          detailsRow.style.display = detailsRow.classList.contains('expanded') ? 'table-row' : 'none';
        }
      }

      if (show) visible++;
    });

    if (noDataEl) {
      noDataEl.classList.toggle('hidden', visible > 0);
    }
  }

  function init(opts) {
    const {
      tableBodySelector,
      noDataSelector,
      dateInputSelector,
      loanInputSelector,
      statusSelectSelector,
      clearBtnSelector,
      searchIconSelector,
      clearSearchBtnSelector,
      suggestionsBoxSelector,
      // Function that returns an array of loan refs (strings)
      getLoanRefs = () => [],
      // Column indices (1-based, as used by nth-child)
      columnIndex = { loan: 2, date: 8, status: 9 },
      // Flatpickr present? If yes, we set format to 'd M Y'
      enableDatePicker = true,
    } = opts || {};

    const tableBody = document.querySelector(tableBodySelector);
    const noDataEl = document.querySelector(noDataSelector);
    const dateInput = document.querySelector(dateInputSelector);
    const loanInput = document.querySelector(loanInputSelector);
    const statusSelect = document.querySelector(statusSelectSelector);
    const clearBtn = document.querySelector(clearBtnSelector);
    const searchIcon = document.querySelector(searchIconSelector);
    const clearSearchBtn = document.querySelector(clearSearchBtnSelector);
    const suggestionsEl = document.querySelector(suggestionsBoxSelector);

    const state = { date: '', loan: '', status: '' };

    // Setup date picker
    if (enableDatePicker && typeof flatpickr !== 'undefined' && dateInput) {
      flatpickr(dateInput, { dateFormat: 'd M Y', allowInput: true });
    }

    // Loan suggestions
    function renderSuggestions(filter) {
      if (!suggestionsEl) return;
      const refs = (getLoanRefs() || []);
      const items = (filter ? refs.filter(r => r.toLowerCase().includes(filter)) : refs).slice(0, 50);
      suggestionsEl.innerHTML = items.length
        ? items.map(r => `<div class="px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 suggestion-item" data-value="${r}">${r}</div>`).join('')
        : '<div class="px-3 py-2 text-sm text-gray-500">No matches</div>';
    }
    function showSuggestions() { suggestionsEl && suggestionsEl.classList.remove('hidden'); }
    function hideSuggestions() { suggestionsEl && suggestionsEl.classList.add('hidden'); }

    if (loanInput) {
      loanInput.addEventListener('focus', () => { renderSuggestions(state.loan); showSuggestions(); });
      loanInput.addEventListener('click', () => { renderSuggestions(state.loan); showSuggestions(); });
      loanInput.addEventListener('input', () => {
        state.loan = (loanInput.value || '').trim().toLowerCase();
        if (clearSearchBtn) clearSearchBtn.classList.toggle('hidden', !state.loan);
        if (searchIcon) searchIcon.classList.toggle('hidden', !!state.loan);
        renderSuggestions(state.loan);
        showSuggestions();
        applyFilters(tableBody, noDataEl, columnIndex, state);
      });
    }
    if (suggestionsEl) {
      suggestionsEl.addEventListener('click', e => {
        const el = e.target.closest('.suggestion-item');
        if (!el) return;
        const val = el.getAttribute('data-value') || '';
        if (loanInput) loanInput.value = val;
        state.loan = val.toLowerCase();
        if (clearSearchBtn) clearSearchBtn.classList.remove('hidden');
        if (searchIcon) searchIcon.classList.add('hidden');
        applyFilters(tableBody, noDataEl, columnIndex, state);
        hideSuggestions();
      });
      document.addEventListener('click', e => {
        if (e.target === loanInput || suggestionsEl.contains(e.target)) return;
        hideSuggestions();
      });
    }
    if (clearSearchBtn) {
      clearSearchBtn.addEventListener('click', () => {
        if (loanInput) loanInput.value = '';
        state.loan = '';
        clearSearchBtn.classList.add('hidden');
        if (searchIcon) searchIcon.classList.remove('hidden');
        applyFilters(tableBody, noDataEl, columnIndex, state);
      });
    }

    // Date filter
    if (dateInput) {
      dateInput.addEventListener('change', () => {
        state.date = (dateInput.value || '').trim();
        applyFilters(tableBody, noDataEl, columnIndex, state);
      });
    }

    // Status filter
    if (statusSelect) {
      statusSelect.addEventListener('change', () => {
        state.status = (statusSelect.value || '').trim().toLowerCase();
        applyFilters(tableBody, noDataEl, columnIndex, state);
      });
    }

    // Clear all filters
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        if (dateInput) dateInput.value = '';
        if (loanInput) loanInput.value = '';
        if (statusSelect) statusSelect.value = '';
        state.date = '';
        state.loan = '';
        state.status = '';
        if (clearSearchBtn) clearSearchBtn.classList.add('hidden');
        if (searchIcon) searchIcon.classList.remove('hidden');
        applyFilters(tableBody, noDataEl, columnIndex, state);
      });
    }

    // Initial apply so "No data" reflects current table
    applyFilters(tableBody, noDataEl, columnIndex, state);
  }

  return { init };
})();