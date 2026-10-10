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
  audioBase: 'https://pub-f04ff4ec924944709d64e0b325a9cce9.r2.dev/audio/',   // 성경 듣기 소리 (Cloudflare R2 · 버킷 yohan · 2026-10-07)
  // 홈 맨 앞 소개 영상 (2026-10-10) — 영상은 R2 video/ 에 · 썸네일은 앱 img/ · 영상을 바꿀 땐 이 세 줄(+R2 에 새 파일)만 고친다
  introVideo: {
    src: 'https://pub-f04ff4ec924944709d64e0b325a9cce9.r2.dev/video/hanna-samuel-intro-V1.1.mp4',
    poster: 'img/intro-poster.jpg',
    title: '🎬 한나와 사무엘',
    note: '사무엘상 1~3장 · 소리 없이 입술만 움직이던 한나의 기도에서 사무엘의 첫 말까지 · 3분 45초'
  },
  backend: 'sheets',
  sheets: { webAppUrl: 'https://script.google.com/macros/s/AKfycbyQ2mflyh6BqfislEjV544FIGUY5jSZ7lgbbELI7zQoWKOid6XXixV65JkwsSD3CGJzYA/exec' }
};
