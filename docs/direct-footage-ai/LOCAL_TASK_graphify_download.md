# LOCAL_TASK — Graphify(그래피파이) 오픈소스 내려받기 · 설치

상태: CANDIDATE. 클라우드에서 소스를 받아 G드라이브에 올렸고, PC 설치와 실행은 아직 안 했습니다.
작성: 2026-11-11

## 0. 무엇인가
- 이름은 Graphify이고 PyPI 패키지 이름은 `graphifyy`입니다. 저장소는 https://github.com/Graphify-Labs/graphify 이고, Apache-2.0 무료 오픈소스입니다.
- 받은 판본: v0.9.106, 커밋 `35d1d2038b9e`, 2026-11-10.
- 하는 일: 폴더 안의 코드·문서·PDF·이미지·영상을 지식 그래프로 묶어 줍니다. 클로드 코드나 안티그래비티가 파일을 하나씩 뒤지지 않고 그래프에 물어볼 수 있습니다.
- 영상과 음성은 PC에서 faster-whisper로 받아쓰기합니다. 그래서 `[video]` 추가 설치가 필요합니다.
- README 위쪽의 'Graphify Cloud(토큰 80% 절감, 14일 체험)'는 따로 파는 유료 서비스입니다. 쓰지 않습니다.

## 1. 받을 위치
`J:\프로그램 관리\직접 촬영 영상 AI로 화면 화려하게 하는 방법 프로그램\영상제작 종류별 샘플\graphify\`

## 2. PC에 줄 한 줄 지시
```
G드라이브 '원격 컴퓨터 제어_전달_20261031' 폴더의 graphify_v0.9.106_src.zip 을
J:\프로그램 관리\직접 촬영 영상 AI로 화면 화려하게 하는 방법 프로그램\영상제작 종류별 샘플\ 에 풀고,
저장소 docs/direct-footage-ai/LOCAL_TASK_graphify_download.md 3번 순서대로 설치·확인까지 해줘
```

## 3. 순서 (PC)
1. 압축 파일 SHA-256이 `63d0bba55d4d7ad59b1e81ce68d2b9c4c077c06203e27d2076d2440f65cb5cb9` 인지 확인합니다 (`certutil -hashfile 파일 SHA256`). 다르면 멈춥니다.
2. 위 1번 위치에 풉니다. 결과는 `...\영상제작 종류별 샘플\graphify\README.md` 처럼 됩니다. 샘플 폴더에 이미 있던 파일은 건드리지 않습니다.
3. uv가 없으면 설치합니다: `winget install astral-sh.uv`
4. 영상 받아쓰기 기능까지 받은 소스와 같은 판본으로 설치합니다: `uv tool install "graphifyy[video]==0.9.106"`
   - 내려받은 소스 폴더는 원본 보관용입니다. 설치는 같은 판본의 공식 패키지로 합니다.
5. 클로드 코드에 스킬을 등록합니다: `graphify install --platform windows`
   - 안티그래비티에서도 쓰려면 `graphify antigravity install` 을 실행합니다.
6. 확인: `uv tool list` 에 `graphifyy v0.9.106` 이 보이고, `graphify --help` 가 실행되는지 봅니다.

## 4. 샘플 폴더에 쓰기 (실행은 사장님 확인 후)
- 샘플 폴더에서 클로드 코드를 열고 `/graphify .` 를 입력합니다.
- 결과는 그 폴더의 `graphify-out\` 에 생깁니다. 원본 영상은 바꾸지 않습니다.
- 주의할 점:
  - 영상이 많으면 받아쓰기에 시간이 오래 걸립니다.
  - 이미지·영상의 의미 분석은 클로드 모델 토큰을 씁니다.
  - 노드가 5,000개를 넘으면 그래프 화면이 무거워집니다.
- 빼야 할 큰 폴더가 있으면 `.graphifyignore` 에 적습니다.
- J 작업 흔적 0 헌법 때문에, `graphify-out\` 을 J에 둘지 결과 폴더로 옮길지는 사장님이 정합니다.

## 5. 미확인 (HOLD)
- '영상제작 종류별 샘플' 폴더 안의 실제 파일 수와 용량
- PC의 Python과 uv 판본
- 받아쓰기 정확도 (한국어 영상)
