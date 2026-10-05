/* 옛 주소(pw·open)의 서비스워커 정리 — 옛 화면이 남지 않게 캐시를 지우고 스스로 해제한 뒤 새 주소로 */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((ks) => Promise.all(ks.map((k) => caches.delete(k))))
      .then(() => self.registration.unregister())
      .then(() => self.clients.matchAll())
      .then((cs) => cs.forEach((c) => c.navigate(c.url)))
  );
});
