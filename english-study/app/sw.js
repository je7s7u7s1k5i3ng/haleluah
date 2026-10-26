/* 영어 공부 - 서비스 워커 (성경 읽기 앱 V3.9 방식 그대로) */
const CACHE = 'english-cache-app-20261027a';   // 2026-10-27 쉐도잉 5문장 단계(단계 끝 통독) · 이음 읽기(앞 장 마지막 문장 → 이 장 첫 문장) · 장 단위 쉐도잉(권역) · 소리 나는 동안 자막 따라가기 안전망 / 2026-10-23 우리말 자막 전부 개역한글 정본 · 전 책 음량 -19 LUFS 통일 /   // 2026-10-22 쉐도잉 끝까지 쌓으면 다음 장으로 이어서 / 쉐도잉 누적 반복 모드(1 → 1~2 → 1~3 …) / 창세기 50장(색번호 1,236세트 · 음량 올림) 추가 / 쭉 듣기 장 넘김 끊김 수정(다음 장 미리 받기) · 절 구간 반복 / 2026-10-11 마지막 읽은·들은 곳 자동 저장 · 켜면 그 자리로 자동 열기 / 2026-10-09 18권 전부 색번호 (188장 · 4279세트) · 게스트 입장 · 공부 탭 책·장 고르기 · 관리 화면 자세히(서버 V1.1 올린 뒤 채워짐)
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
