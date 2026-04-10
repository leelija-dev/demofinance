(function () {
  function _toIntOrNull(v) {
    const s = (v == null) ? '' : String(v).trim();
    if (!s) return null;
    const n = parseInt(s, 10);
    return Number.isFinite(n) ? n : null;
  }

  function createInfiniteScroll(options) {
    const opts = options || {};

    const containerSelector = opts.containerSelector || '#emi-collect-tbody';
    const sentinelSelector = opts.sentinelSelector || '#emi-scroll-sentinel';
    const noDataSelector = opts.noDataSelector || '#no-emi-collect';
    const loadingSelector = opts.loadingSelector || null;
    const rootSelector = opts.rootSelector || null;

    // Declare first to avoid any ReferenceError in case this file is concatenated/modified in a way
    // that reorders statements in production builds.
    let rootEl = null;

    const containerEl = document.querySelector(containerSelector);
    const sentinelEl = document.querySelector(sentinelSelector);
    const noDataEl = noDataSelector ? document.querySelector(noDataSelector) : null;
    const loadingEl = loadingSelector ? document.querySelector(loadingSelector) : null;
    rootEl = opts.rootEl || (rootSelector ? document.querySelector(rootSelector) : null);

    function _isScrollable(el) {
      if (!el) return false;
      try {
        return (el.scrollHeight - el.clientHeight) > 2;
      } catch (e) {
        return false;
      }
    }

    if (!containerEl || !sentinelEl) {
      return {
        destroy: function () { },
        loadNextPage: function () { },
      };
    }

    let nextPage = _toIntOrNull(sentinelEl.dataset.nextPage);
    let hasNext = sentinelEl.dataset.hasNext === '1' || sentinelEl.dataset.hasNext === 'true';
    let isLoading = false;

    function setLoading(on) {
      if (!loadingEl) return;
      if (on) {
        loadingEl.classList.remove('hidden');
      } else {
        loadingEl.classList.add('hidden');
      }
    }

    function syncNoDataMessage() {
      if (!noDataEl) return;
      const hasRows = !!containerEl.querySelector('tr');
      if (!hasRows) {
        noDataEl.classList.remove('hidden');
      } else {
        noDataEl.classList.add('hidden');
      }
    }

    async function loadNextPage() {
      if (!hasNext || !nextPage || isLoading) return;
      isLoading = true;
      setLoading(true);

      try {
        const url = (typeof opts.buildUrl === 'function')
          ? opts.buildUrl(nextPage)
          : ((opts.url || '') + '?page=' + encodeURIComponent(nextPage));

        const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!res.ok) throw new Error('HTTP ' + res.status);

        const html = await res.text();
        if (!html || !html.trim()) {
          hasNext = false;
          nextPage = null;
          return;
        }

        containerEl.insertAdjacentHTML('beforeend', html);
        nextPage += 1;

        if (typeof opts.afterAppend === 'function') {
          try { opts.afterAppend(containerEl); } catch (e) { }
        }
      } catch (err) {
        if (typeof opts.onError === 'function') {
          try { opts.onError(err); } catch (e) { }
        } else {
          // non-blocking
          console.error('Infinite scroll failed:', err);
        }
      } finally {
        isLoading = false;
        setLoading(false);
        syncNoDataMessage();
      }
    }

    syncNoDataMessage();
    setLoading(false);

    const io = new IntersectionObserver(function (entries) {
      const entry = entries && entries[0];
      if (entry && entry.isIntersecting) {
        loadNextPage();
      }
    }, { root: _isScrollable(rootEl) ? rootEl : null, rootMargin: opts.rootMargin || '200px', threshold: 0 });

    io.observe(sentinelEl);

    return {
      destroy: function () {
        try { io.disconnect(); } catch (e) { }
      },
      loadNextPage: loadNextPage,
    };
  }

  window.LoanInfiniteScroll = window.LoanInfiniteScroll || {};
  window.LoanInfiniteScroll.create = createInfiniteScroll;
})();
