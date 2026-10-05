/* 성경 읽기 - 서비스 워커 (오프라인 지원) */
const CACHE = 'bible-cache-open-20261005n';
const ASSETS = ['./', 'index.html', 'manifest.json', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => Promise.allSettled(ASSETS.map((u) => c.add(new Request(u, { cache: 'reload' })))))   // ★브라우저 10분 캐시를 건너뛰고 새 파일을 받는다
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // bible.json 은 한 번 받으면 캐시 우선 (용량이 큼)
  if (url.pathname.endsWith('bible.json')) {
    e.respondWith(
      caches.open(CACHE).then((c) =>
        c.match(req).then(
          (hit) =>
            hit ||
            fetch(req)
              .then((res) => {
                if (res.ok) c.put(req, res.clone());
                return res;
              })
              .catch(() => c.match('./'))
        )
      )
    );
    return;
  }

  // 그 외: 캐시 우선, 없으면 네트워크 후 캐시 저장
  e.respondWith(
    caches.open(CACHE).then((c) =>
      c.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) c.put(req, res.clone());
            return res;
          })
      )
    )
  );
});
