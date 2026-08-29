(function () {
  'use strict';

  const root = document.getElementById('agent-location-root');
  if (!root || typeof L === 'undefined') return;

  const apiUrl = root.dataset.apiUrl;
  const portal = root.dataset.portal || 'branch';
  const pollMs = parseInt(root.dataset.pollMs || '30000', 10) || 30000;

  const statusEl = document.getElementById('agent-loc-status');
  const searchEl = document.getElementById('agent-loc-search');
  const branchEl = document.getElementById('agent-loc-branch');
  const refreshBtn = document.getElementById('agent-loc-refresh');
  const refreshIconEl = document.getElementById('agent-loc-refresh-icon');
  const listEl = document.getElementById('agent-loc-list');
  const onlineCountEl = document.getElementById('agent-loc-online-count');
  const offlineCountEl = document.getElementById('agent-loc-offline-count');
  const noneCountEl = document.getElementById('agent-loc-none-count');
  const updatedAtEl = document.getElementById('agent-loc-updated-at');

  const map = L.map('agent-loc-map', {
    scrollWheelZoom: true,
    zoomControl: true,
  }).setView([22.57, 88.36], 12);


  // Street map with road / area / landmark labels (Esri World Street Map)
  const streets = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, OpenStreetMap contributors',
    }
  );

  // OpenStreetMap alternative (also shows street / area names when zoomed in)
  const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
  });

  streets.addTo(map);

  L.control
    .layers(
      {
        'Street names (detailed)': streets,
        OpenStreetMap: osm,
      },
      {},
      { collapsed: true, position: 'topright' }
    )
    .addTo(map);

  const markersLayer = L.layerGroup().addTo(map);
  const markerById = {};
  let agentsCache = [];
  let activeAgentId = null;
  let pollTimer = null;
  let searchTimer = null;
  let isLoading = false;

  function setRefreshLoading(loading) {
    isLoading = loading;
    if (!refreshBtn) return;
    refreshBtn.classList.toggle('is-loading', loading);
    refreshBtn.disabled = loading;
  }

  function playRefreshSpinTwice() {
    return new Promise(function (resolve) {
      if (!refreshBtn || !refreshIconEl) {
        resolve();
        return;
      }
      // Restart animation cleanly each refresh
      refreshBtn.classList.remove('is-spinning');
      void refreshIconEl.offsetWidth;
      function onEnd(e) {
        if (e && e.animationName && e.animationName !== 'agent-loc-spin-twice') return;
        refreshIconEl.removeEventListener('animationend', onEnd);
        refreshBtn.classList.remove('is-spinning');
        resolve();
      }
      refreshIconEl.addEventListener('animationend', onEnd);
      refreshBtn.classList.add('is-spinning');
      // Safety if animationend does not fire
      setTimeout(function () {
        refreshIconEl.removeEventListener('animationend', onEnd);
        refreshBtn.classList.remove('is-spinning');
        resolve();
      }, 1800);
    });
  }

  function markerIcon(kind) {
    return L.divIcon({
      className: '',
      html: `<div class="agent-loc-marker agent-loc-marker--${kind}"></div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });
  }

  function statusKind(agent) {
    if (!agent.has_location) return 'none';
    return agent.is_online ? 'online' : 'offline';
  }

  function formatWhen(iso) {
    if (!iso) return 'Never';
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return iso;
      return d.toLocaleString();
    } catch (e) {
      return iso;
    }
  }

  function placeLabel(agent) {
    const area = agent.neighbourhood || agent.suburb || '';
    // Prefer local Area over road / city-only labels
    if (area && area.toLowerCase() !== (agent.city || '').toLowerCase()) {
      if (agent.road && agent.road.toLowerCase() !== area.toLowerCase()) {
        return `${agent.road}, ${area}`;
      }
      return area;
    }
    if (agent.place_name) return agent.place_name;
    const parts = [agent.building, agent.road, agent.city].filter(Boolean);
    if (parts.length) return parts.join(', ');
    return agent.address_text || '';
  }

  function placeDetailHtml(agent) {
    const area = agent.neighbourhood || agent.suburb || '';
    const city = agent.city && area && agent.city.toLowerCase() === area.toLowerCase()
      ? ''
      : (agent.city || '');
    const rows = [
      ['Building', agent.building],
      ['Road', agent.road],
      ['Area', area],
      ['City', city],
      ['District', agent.district],
      ['State', agent.state],
      ['PIN', agent.postcode],
    ].filter((row) => row[1]);

    let html = '';
    if (rows.length) {
      html += '<div class="agent-loc-popup-place">';
      rows.forEach(([label, value]) => {
        html += `<div><span class="k">${escapeHtml(label)}:</span> ${escapeHtml(value)}</div>`;
      });
      html += '</div>';
    }
    if (agent.address_text) {
      html += `<div class="agent-loc-popup-address">${escapeHtml(agent.address_text)}</div>`;
    }
    return html;
  }

  function buildQuery() {
    const params = new URLSearchParams();
    const status = (statusEl && statusEl.value) || 'active';
    if (status) params.set('status', status);
    const q = (searchEl && searchEl.value.trim()) || '';
    if (q) params.set('q', q);
    if (portal === 'hq' && branchEl && branchEl.value) {
      params.set('branch_id', branchEl.value);
    }
    const qs = params.toString();
    return qs ? `${apiUrl}?${qs}` : apiUrl;
  }

  function renderList(agents) {
    listEl.innerHTML = '';
    if (!agents.length) {
      listEl.innerHTML = '<li class="agent-loc-empty">No agents found.</li>';
      return;
    }

    agents.forEach((agent) => {
      const kind = statusKind(agent);
      const place = placeLabel(agent);
      const li = document.createElement('li');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'agent-loc-list-item' + (activeAgentId === agent.agent_id ? ' is-active' : '');
      btn.innerHTML = `
        <span class="agent-loc-dot agent-loc-dot--${kind}"></span>
        <span>
          <div class="name">${escapeHtml(agent.full_name || agent.agent_id)}</div>
          <div class="meta">${escapeHtml(agent.agent_id)} · ${escapeHtml(agent.phone || '')}</div>
          ${
            place
              ? `<div class="meta place">${escapeHtml(place)}</div>`
              : ''
          }
          <div class="meta">${
            portal === 'hq' ? escapeHtml(agent.branch_name || '') + ' · ' : ''
          }Last seen: ${escapeHtml(formatWhen(agent.recorded_at))}</div>
        </span>
      `;
      btn.addEventListener('click', () => focusAgent(agent));
      li.appendChild(btn);
      listEl.appendChild(li);
    });
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function popupHtml(agent) {
    return (
      `<div class="agent-loc-popup">` +
      `<strong>${escapeHtml(agent.full_name)}</strong><br/>` +
      `${escapeHtml(agent.agent_id)}` +
      (portal === 'hq' ? `<br/>${escapeHtml(agent.branch_name || '')}` : '') +
      placeDetailHtml(agent) +
      `<div class="agent-loc-popup-seen">Last seen: ${escapeHtml(formatWhen(agent.recorded_at))}</div>` +
      `</div>`
    );
  }

  function renderMarkers(agents) {
    markersLayer.clearLayers();
    Object.keys(markerById).forEach((k) => delete markerById[k]);

    const bounds = [];
    agents.forEach((agent) => {
      if (agent.latitude == null || agent.longitude == null) return;
      const kind = agent.is_online ? 'online' : 'offline';
      const marker = L.marker([agent.latitude, agent.longitude], {
        icon: markerIcon(kind),
        title: agent.full_name,
      });

      const label = placeLabel(agent) || agent.full_name;
      marker.bindTooltip(
        `<div class="agent-loc-map-label"><b>${escapeHtml(agent.full_name)}</b>` +
          (label ? `<br/><span>${escapeHtml(label)}</span>` : '') +
          `</div>`,
        {
          permanent: true,
          direction: 'top',
          offset: [0, -8],
          opacity: 0.95,
          className: 'agent-loc-tooltip',
        }
      );

      marker.bindPopup(popupHtml(agent), { maxWidth: 320 });
      marker.on('click', () => {
        activeAgentId = agent.agent_id;
        renderList(agents);
      });
      marker.addTo(markersLayer);
      markerById[agent.agent_id] = marker;
      bounds.push([agent.latitude, agent.longitude]);
    });

    if (bounds.length) {
      map.fitBounds(bounds, { padding: [48, 48], maxZoom: 16 });
    }
  }

  function focusAgent(agent) {
    activeAgentId = agent.agent_id;
    renderList(agentsCache);
    const marker = markerById[agent.agent_id];
    if (marker) {
      // Zoom in enough to show building / street labels on the basemap
      map.setView(marker.getLatLng(), Math.max(map.getZoom(), 17));
      marker.openPopup();
    }
  }

  function updateCounts(agents) {
    let online = 0;
    let offline = 0;
    let none = 0;
    agents.forEach((a) => {
      const kind = statusKind(a);
      if (kind === 'online') online += 1;
      else if (kind === 'offline') offline += 1;
      else none += 1;
    });
    onlineCountEl.textContent = String(online);
    offlineCountEl.textContent = String(offline);
    noneCountEl.textContent = String(none);
    updatedAtEl.textContent = 'Updated ' + new Date().toLocaleTimeString();
  }

  async function loadLocations() {
    if (isLoading) return;
    setRefreshLoading(true);
    const spinPromise = playRefreshSpinTwice();
    try {
      const res = await fetch(buildQuery(), {
        headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
        credentials: 'same-origin',
      });
      if (!res.ok) return;
      const data = await res.json();
      if (!data.success) return;
      const agents = data.agents || [];
      agentsCache = agents;
      updateCounts(agents);
      renderList(agents);
      renderMarkers(agents);
    } catch (e) {
      // Silent — do not disrupt portal UX
    } finally {
      // Wait so icon always finishes two full spins
      await spinPromise;
      setRefreshLoading(false);
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(function () {
        loadLocations();
      }, pollMs);
    }
  }

  if (statusEl) statusEl.addEventListener('change', function () { loadLocations(); });
  if (branchEl) branchEl.addEventListener('change', function () { loadLocations(); });
  if (refreshBtn) {
    refreshBtn.addEventListener('click', function () {
      loadLocations();
    });
  }
  if (searchEl) {
    searchEl.addEventListener('input', () => {
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(function () {
        loadLocations();
      }, 350);
    });
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) loadLocations();
  });

  loadLocations();
})();
