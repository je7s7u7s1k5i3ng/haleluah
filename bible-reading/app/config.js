/* 성경 읽기 앱 V3.0 — 요한순교자 (링크 하나)
   privacyMode 'named' = 실명 + 비밀번호 4자리 필수 · 지체끼리는 날짜별 읽음 표시만 · 목사님만 전체
   adminName = 목사님 계정 이름 (이 이름은 목사님 비밀번호 없이는 가입 불가 — 시트 스크립트가 지킨다)
   ★config.js 를 고쳐 다시 올릴 때는 sw.js 의 CACHE 이름 끝 글자를 올릴 것 */
window.APP_CONFIG = {
  groupName: '요한순교자 · 함께 성경 읽기',
  feedbackPhase: true,   // 의견 모으는 기간 — 둘러보기·의견 버튼을 맨 위에 깜박이로 (끝나면 false)
  groupId: '요한순교자',
  adminName: '황선주',
  planWeeks: 40,
  startDate: '',
  storageKey: 'bibleApp.v3',
  privacyMode: 'named',
  backend: 'sheets',
  sheets: { webAppUrl: 'https://script.google.com/macros/s/AKfycbyQ2mflyh6BqfislEjV544FIGUY5jSZ7lgbbELI7zQoWKOid6XXixV65JkwsSD3CGJzYA/exec' }
};
