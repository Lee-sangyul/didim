const CACHE = "didim-shell-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

// API 요청은 항상 네트워크로 보낸다 (상담 데이터는 로컬 DB가 최신 상태를 갖고 있어야 함, SSE 스트림은 캐시 대상이 아님).
self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/")) return;

  // 페이지 자체(HTML)는 네트워크를 우선 사용해 항상 최신 화면을 보여주고, 오프라인일 때만 캐시로 대체한다.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          caches.open(CACHE).then((cache) => cache.put(request, response.clone()));
          return response;
        })
        .catch(() => caches.open(CACHE).then((cache) => cache.match(request)))
    );
    return;
  }

  // 정적 자산은 캐시를 우선 보여주고 백그라운드에서 최신본으로 갱신한다.
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(request);
      const network = fetch(request)
        .then((response) => {
          if (response.ok) cache.put(request, response.clone());
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
