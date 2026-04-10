const CACHE_NAME = "ksundaram-app-v1.2";
const urlsToCache = [
  "/",
  "/agent", // Explicitly cache start_url
  "manifest.json",
  "main/images/ksundaram-logo.png", // Or your renamed icons
  "main/css/output.css", // Add key CSS/JS
  "branch/css/style.css",
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      console.log("Opened cache");
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener("fetch", function (event) {
  event.respondWith(
    caches.match(event.request).then(function (response) {
      if (response) {
        return response;
      }
      return fetch(event.request);
    })
  );
});
