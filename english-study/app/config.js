/* 영어 공부 웹 앱 V0.1 — 사장님 + 초대한 소수 (링크 하나)
   ★config.js 를 고쳐 다시 올릴 때는 sw.js 의 CACHE 이름 끝 글자를 올릴 것 */
window.APP_CONFIG = {
  appName: '영어 공부 · 함께 듣고 읽기',
  storageKey: 'engStudy.v1',
  audioBase: 'https://pub-f04ff4ec924944709d64e0b325a9cce9.r2.dev/audio-en/',   // 영어 낭독 소리 (Cloudflare R2 · 버킷 yohan · audio-en/)
  audioVer: { '23_53': 2, '46_13': 2, '19_19': 2, '19_40': 2, '19_91': 2, '19_110': 2, '45_08': 2, '58_11': 2 },   // ★R2 에서 같은 이름으로 소리를 덮어쓴 장은 여기 판 번호를 올린다 (R2 는 1년 캐시라 안 올리면 폰이 옛 소리를 튼다) · 23_53 = 2026-11-20 이사야 53장 v4 교체 · 46_13 = 2026-11-17 고린도전서 13장 v4 교체 · 19_19·19_40·19_91·19_110·45_08·58_11 = 2026-11-28 시편 19·40·91·110 · 로마서 8 · 히브리서 11 v4 교체
  backend: 'sheets',   // 총 관리 시트에 기록 (2026-10-08 연결 · Apps Script 영어공부 기록 V1.0)
  sheets: { webAppUrl: 'https://script.google.com/macros/s/AKfycbxzxioCSmZc_0lYHEvLE1IHICXJWxY6evWd0e9a0fRI42z3AJ9X2edl_pGji7CRt6bi/exec' }
};
