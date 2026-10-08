/* 영어 공부 웹 앱 V0.1 — 사장님 + 초대한 소수 (링크 하나)
   ★config.js 를 고쳐 다시 올릴 때는 sw.js 의 CACHE 이름 끝 글자를 올릴 것 */
window.APP_CONFIG = {
  appName: '영어 공부 · 함께 듣고 읽기',
  storageKey: 'engStudy.v1',
  audioBase: 'https://pub-f04ff4ec924944709d64e0b325a9cce9.r2.dev/audio-en/',   // 영어 낭독 소리 (Cloudflare R2 · 버킷 yohan · audio-en/)
  backend: 'sheets',   // 총 관리 시트에 기록 (2026-10-08 연결 · Apps Script 영어공부 기록 V1.0)
  sheets: { webAppUrl: 'https://script.google.com/macros/s/AKfycbxzxioCSmZc_0lYHEvLE1IHICXJWxY6evWd0e9a0fRI42z3AJ9X2edl_pGji7CRt6bi/exec' }
};
