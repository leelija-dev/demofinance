(function () {
    const initInfiniteScroll = (options) => {
        const tbodyId = options?.tbodyId;
        const sentinelId = options?.sentinelId;
        const rootMargin = options?.rootMargin || '200px';

        const tbody = tbodyId ? document.getElementById(tbodyId) : null;
        if (!tbody) return;

        let isLoading = false;
        let observer = null;

        const buildUrl = (page) => {
            if (typeof options?.buildUrl === 'function') {
                return options.buildUrl(page);
            }
            const url = new URL(window.location.href);
            url.searchParams.set('partial', '1');
            url.searchParams.set('page', String(page));
            return url.toString();
        };

        const loadMore = async () => {
            if (isLoading) return;

            const row = sentinelId ? document.getElementById(sentinelId) : null;
            if (!row) return;

            const nextPage = parseInt(row.getAttribute('data-next-page') || '0', 10);
            if (!nextPage) return;

            isLoading = true;

            try {
                const res = await fetch(buildUrl(nextPage), { headers: { 'X-Requested-With': 'fetch' } });
                const html = await res.text();

                const existing = sentinelId ? document.getElementById(sentinelId) : null;
                if (existing) existing.remove();

                tbody.insertAdjacentHTML('beforeend', html);

                attachObserver();
            } catch (e) {
                isLoading = false;
            }

            isLoading = false;
        };

        const attachObserver = () => {
            const row = sentinelId ? document.getElementById(sentinelId) : null;
            if (!row) return;

            if (observer) observer.disconnect();
            observer = new IntersectionObserver(
                (entries) => {
                    entries.forEach((entry) => {
                        if (!entry.isIntersecting) return;
                        loadMore();
                    });
                },
                { root: null, rootMargin, threshold: 0 }
            );

            observer.observe(row);
        };

        attachObserver();
    };

    window.initInfiniteScroll = initInfiniteScroll;
})();
