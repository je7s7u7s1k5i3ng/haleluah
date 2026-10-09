/* 영어 공부 - 서비스 워커 (성경 읽기 앱 V3.9 방식 그대로) */
const CACHE = 'english-cache-app-20261009b';   // 2026-10-09 마태복음 28장 색번호 (801세트) · 누가복음 24장 (858세트)
const ASSETS = ['./', 'index.html', 'manifest.json', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => Promise.allSettled(ASSETS.map((u) => c.add(new Request(u, { cache: 'reload' }))))));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.indexOf('/audio/') >= 0 && url.pathname.endsWith('.m4a')) return;   // 소리 파일은 건드리지 않는다 (아이폰 구간 요청 그대로)

  // 화면·설정·데이터는 인터넷 먼저 (새로 올린 것이 바로 보이게) → 끊기면 저장본
  const p = url.pathname;
  if (req.mode === 'navigate' || p.endsWith('/') || p.endsWith('.html') || p.endsWith('config.js') || p.endsWith('manifest.json') || p.indexOf('/data/') >= 0) {
    e.respondWith(
      fetch(req.url, { cache: 'no-store', credentials: 'same-origin' })
        .then((res) => { if (res.ok) { const cp = res.clone(); caches.open(CACHE).then((c) => c.put(req.url, cp)); } return res; })
        .catch(() => caches.open(CACHE).then((c) => c.match(req.url, { ignoreSearch: true }).then((hit) => hit || c.match('./'))))
    );
    return;
  }

  // 그 외(그림 등): 캐시 우선
  e.respondWith(
    caches.open(CACHE).then((c) => c.match(req).then((hit) => hit || fetch(req).then((res) => { if (res.ok) c.put(req, res.clone()); return res; })))
  );
});
