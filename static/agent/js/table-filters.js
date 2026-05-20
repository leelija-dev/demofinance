// Expose a tiny helper onto window
window.AgentFilters = (function () {
  /** Canonical YYYY-MM-DD for comparisons (timezone-neutral for plain dates). */
  function normalizeDateText(value) {
    const raw = (value || '').trim();
    if (!raw) return '';

    let s = raw;
    if (s.includes('T')) {
      s = s.split('T')[0].trim();
    }

    let m = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    if (m) {
      const d = String(m[1]).padStart(2, '0');
      const mon = String(m[2]).padStart(2, '0');
      const y = String(m[3]);
      return `${y}-${mon}-${d}`;
    }

    m = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
    if (m) {
      const y = String(m[1]);
      const mon = String(m[2]).padStart(2, '0');
      const d = String(m[3]).padStart(2, '0');
      return `${y}-${mon}-${d}`;
    }

    const parsed = new Date(raw);
    if (!Number.isNaN(parsed.getTime())) {
      const y = String(parsed.getFullYear());
      const mon = String(parsed.getMonth() + 1).padStart(2, '0');
      const d = String(parsed.getDate()).padStart(2, '0');
      return `${y}-${mon}-${d}`;
    }

    return raw.toLowerCase();
  }

  function applyFilters(tableBody, noDataEl, idx, state) {
    if (!tableBody) return;
    const allRows = Array.from(tableBody.querySelectorAll('tr'));
    // Treat rows with '.details-row' as children of the preceding main row
    const mainRows = allRows.filter(r => !r.classList.contains('details-row'));
    let visible = 0;

    const filterDateNorm = state.date ? normalizeDateText(state.date) : '';

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
      if (filterDateNorm) {
        const cell = row.querySelector(`td:nth-child(${idx.date})`);
        const txt = (cell ? cell.textContent.trim() : '');
        okDate = normalizeDateText(txt) === filterDateNorm;
      }

      // Status filter (exact, lowercase)
      let okStatus = true;
      if (state.status && idx.status > 0) {
        const cell = row.querySelector(`td:nth-child(${idx.status})`);
        const cellTxt = (cell ? cell.textContent.trim().toLowerCase() : '');
        okStatus = (cellTxt === state.status);
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
    const noDataEl = noDataSelector ? document.querySelector(noDataSelector) : null;
    const dateInput = dateInputSelector ? document.querySelector(dateInputSelector) : null;
    const loanInput = loanInputSelector ? document.querySelector(loanInputSelector) : null;
    const statusSelect = statusSelectSelector ? document.querySelector(statusSelectSelector) : null;
    const clearBtn = clearBtnSelector ? document.querySelector(clearBtnSelector) : null;
    const searchIcon = searchIconSelector ? document.querySelector(searchIconSelector) : null;
    const clearSearchBtn = clearSearchBtnSelector ? document.querySelector(clearSearchBtnSelector) : null;
    const suggestionsEl = suggestionsBoxSelector ? document.querySelector(suggestionsBoxSelector) : null;

    const state = { date: '', loan: '', status: '' };

    function runFilters() {
      applyFilters(tableBody, noDataEl, columnIndex, state);
    }

    // Allow list pages (e.g. infinite scroll) to re-apply active filters after new rows render
    window.AgentFilters.refresh = runFilters;

    // Setup date picker — use onChange because native "change" is not always fired by flatpickr
    let datePicker = null;
    if (enableDatePicker && typeof flatpickr !== 'undefined' && dateInput) {
      datePicker = flatpickr(dateInput, {
        dateFormat: 'd M Y',
        allowInput: true,
        onChange: (_dates, dateStr) => {
          state.date = (dateStr || dateInput.value || '').trim();
          runFilters();
        },
      });
    }

    function syncDateFromInput() {
      state.date = (dateInput ? dateInput.value : '').trim();
      runFilters();
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
        runFilters();
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
        runFilters();
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
        runFilters();
      });
    }

    if (dateInput) {
      dateInput.addEventListener('input', syncDateFromInput);
      dateInput.addEventListener('change', syncDateFromInput);
      dateInput.addEventListener('blur', syncDateFromInput);
      dateInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') syncDateFromInput();
      });
    }

    if (statusSelect) {
      statusSelect.addEventListener('change', () => {
        state.status = (statusSelect.value || '').trim().toLowerCase();
        runFilters();
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        if (datePicker) {
          try { datePicker.clear(); } catch (e) { /* noop */ }
        } else if (dateInput) {
          dateInput.value = '';
        }
        if (loanInput) loanInput.value = '';
        if (statusSelect) statusSelect.value = '';
        state.date = '';
        state.loan = '';
        state.status = '';
        if (clearSearchBtn) clearSearchBtn.classList.add('hidden');
        if (searchIcon) searchIcon.classList.remove('hidden');
        runFilters();
      });
    }

    runFilters();
  }

  return { init };
})();
