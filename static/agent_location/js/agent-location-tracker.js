/**
 * Agent location tracker — posts GPS while the agent portal tab is visible.
 * Isolated module; does not depend on other agent JS.
 */
(function () {
  'use strict';

  // Only run on agent portal pages (excluding login)
  if (!window.location.pathname.startsWith('/agent/')) return;
  if (window.location.pathname.indexOf('/agent/login') === 0) return;
  if (!navigator.geolocation) return;

  const PING_URL = '/agent/location/api/ping/';
  const INTERVAL_MS = 180000; // 3 minutes
  const MIN_ACCURACY_M = 500;

  let timer = null;
  let inFlight = false;

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  function sendPosition(position) {
    if (inFlight) return;
    const coords = position && position.coords;
    if (!coords) return;
    if (coords.accuracy && coords.accuracy > MIN_ACCURACY_M) return;

    inFlight = true;
    fetch(PING_URL, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken') || '',
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy: coords.accuracy,
        recorded_at: new Date().toISOString(),
      }),
    })
      .catch(function () {})
      .finally(function () {
        inFlight = false;
      });
  }

  function requestOnce() {
    if (document.hidden) return;
    navigator.geolocation.getCurrentPosition(sendPosition, function () {}, {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 60000,
    });
  }

  function start() {
    requestOnce();
    if (timer) clearInterval(timer);
    timer = setInterval(requestOnce, INTERVAL_MS);
  }

  function stop() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) stop();
    else start();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
