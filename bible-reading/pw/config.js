/* 비밀번호 버전 — 성경 읽기 앱 (가입할 때 ★비밀번호가 필수. 다른 멤버(목사님 포함)에게는 가명(비공개#코드)으로만 보인다.)
   privacyMode 가 이 버전의 성격을 정한다:  required = 비밀번호 필수·가명  /  off = 비밀번호 없음·전원 실명
   storageKey  는 ★버전마다 달라야 한다 (같은 주소에서 두 버전을 열어도 기록이 안 섞인다)
   backend     는 지금 'local' = 이 기기에만 저장. 진도를 서로 보려면 백엔드를 붙여야 한다 (README 참고)
   ★config.js 를 고쳐 다시 올릴 때는 sw.js 맨 위 CACHE 이름의 날짜를 올려야 이미 열어 본 기기에도 반영된다 */
window.APP_CONFIG = {
  groupName: '성경 읽기 · 비밀번호 버전 (이름 가림)',
  groupId: '',
  planWeeks: 40,
  startDate: '',
  storageKey: 'bibleApp.v1.pw',
  privacyMode: 'required',
  backend: 'local'
};
