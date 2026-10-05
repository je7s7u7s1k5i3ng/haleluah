/* 성경 읽기 - 서비스 워커 (오프라인 지원) */
const CACHE = 'bible-cache-app-20261005o';
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

  // V3.9 화면·설정·목록은 인터넷 먼저 (새로 올린 것이 바로 보이게) → 끊기면 저장본
  const p = url.pathname;
  if (req.mode === 'navigate' || p.endsWith('/') || p.endsWith('.html') || p.endsWith('config.js') || p.endsWith('manifest.json')) {
    e.respondWith(
      fetch(req.url, { cache: 'no-store', credentials: 'same-origin' })   // 화면 이동 요청에 옵션을 붙이면 크롬이 거부 → 주소로 다시 요청
        .then((res) => { if (res.ok) { const cp = res.clone(); caches.open(CACHE).then((c) => c.put(req.url, cp)); } return res; })   // 복사본은 바로 떠 둔다
        .catch(() => caches.open(CACHE).then((c) => c.match(req.url, { ignoreSearch: true }).then((hit) => hit || c.match('./'))))
    );
    return;
  }

  // 그 외(그림 등): 캐시 우선, 없으면 네트워크 후 캐시 저장
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
