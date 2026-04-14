# Unreal 전쟁 시나리오 자동화 파이프라인

Unreal Engine 5 + ElevenLabs + FFmpeg 을 조합해, 시나리오 JSON 한 개에서
**쇼츠(1080x1920@60) / 롱폼(1920x1080@60) MP4** 를 자동 생성한다.

```
scenarios/*.json  ──▶  ElevenLabs TTS (대사+타임스탬프)
                  ──▶  Unreal Remote Control (레벨/캐릭터/카메라/이펙트)
                  ──▶  Movie Render Queue (PNG 시퀀스)
                  ──▶  FFmpeg (오디오 믹싱 + 자막 내장 + MP4)
                  ──▶  output/final/<title>.mp4
```

## 파일 구조

```
war_pipeline/
├── pipeline/
│   ├── config.py           # .env 로딩, 포맷 프리셋
│   ├── scenario.py         # Pydantic 시나리오 스키마
│   ├── tts.py              # ElevenLabs + 문자 단위 타임스탬프
│   ├── subtitle.py         # SRT 생성
│   ├── unreal_rc.py        # Remote Control REST 클라이언트
│   ├── scene_builder.py    # 시나리오 -> Unreal 스크립트 호출
│   ├── render.py           # Movie Render Queue 트리거
│   ├── composer.py         # FFmpeg 합성
│   └── orchestrator.py     # 전체 파이프라인 실행
├── scripts/
│   ├── test_rc_connection.py   # Unreal RC 연결 테스트
│   ├── run_pipeline.py         # CLI 진입점
│   └── tts_preview.py          # TTS+자막+믹스만 (UE 없이)
├── scenarios/
│   └── sample_scenario.json
├── unreal_python/
│   └── war_setup.py        # ⚠️ UE 프로젝트 Content/Python/ 로 복사
├── output/                 # 자동 생성: audio/renders/final
├── requirements.txt
├── .env.example
└── README.md
```

## 사전 준비

### 1. Unreal Engine 5 (5.3+ 권장)

- 다음 플러그인 **활성화**
  - `Remote Control API`
  - `Movie Render Queue`
  - `Python Editor Script Plugin`
  - `Niagara`
- **Project Settings**
  - Plugins > Web Remote Control
    - HTTP Server Port = `30010`
    - WebSocket Server Port = `30020`
    - Auto Start Web Control On Boot = ON
  - Python > **Enable Remote Execution** = ON
- 에디터 Cmd 창에서 서버 수동 기동 (자동 시작 설정 안 했을 때):
  ```
  WebControl.StartServer
  ```

### 2. 프로젝트 Python 스크립트 배치

`unreal_python/war_setup.py` 를 UE 프로젝트의
`<UE Project>/Content/Python/war_setup.py` 로 **복사** 한다.
(Remote Control 의 ExecutePythonCommand 가 `import war_setup` 할 수 있어야 한다.)

### 3. 캐릭터 에셋 (Mixamo)

1. [Mixamo](https://www.mixamo.com) 에서 캐릭터 + 애니메이션 FBX 다운로드
   - 옵션: `Format = FBX Binary`, `Skin = With Skin`, `FPS = 60`
2. UE 로 임포트
   - `Content/Characters/` 에 SkeletalMesh 임포트
   - `Content/Animations/Mixamo/<Female|Male>/` 에 애니메이션 시퀀스
3. 각 캐릭터의 **블루프린트** 생성
   - 경로 예: `/Game/Characters/BP_Sniper_Female_01`
   - `SkeletalMeshComponent` 설정, `AnimInstance` 바인딩
4. `scenarios/*.json` 의 `blueprint` / `idle_anim` 경로가 이 경로를 가리켜야 한다.

### 4. 배경/에셋 (Fab)

- Fab 무료 밀리터리 팩 → `/Game/Maps/Battlefield_Desert` (또는 원하는 이름)
- Niagara 이펙트 경로는 시나리오 `effects[].system` 에 지정
  - 프로젝트 내장 스타터 이펙트나 Niagara 내장 `Explosion/Smoke` 사용 가능

### 5. MRQ 프리셋

없으면 `war_setup.py` 가 자동 생성하지만, 품질을 올리려면 직접 만들어두는 걸 추천:

| 이름 | 해상도 | 출력 |
|---|---|---|
| `Preset_AutoWar` (쇼츠) | 1080x1920 @ 60fps | PNG Sequence |
| `Preset_AutoWar_LF` (롱폼) | 1920x1080 @ 60fps | PNG Sequence |

### 6. ElevenLabs

- https://elevenlabs.io 에서 API 키 발급
- (한국어 시나리오면) `eleven_multilingual_v2` 모델 권장
- 원하는 Voice ID 확인 후 `.env` 에 기록

### 7. FFmpeg

```bash
# macOS
brew install ffmpeg
# Ubuntu
sudo apt install ffmpeg
# Windows
winget install Gyan.FFmpeg
```

### 8. Python 패키지

```bash
cd war_pipeline
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # 그리고 API 키 기입
```

## 실행

### A. Unreal 연결 체크

UE 에디터를 먼저 켠 다음:

```bash
python scripts/test_rc_connection.py
```

성공 출력 예:
```
INFO rc-test: 서버 정보: { "HttpServerRunning": true, ... }
INFO rc-test: 성공. Remote Control 연결 정상.
```

### B. TTS 만 먼저 — 타이밍 감 잡기

```bash
python scripts/tts_preview.py scenarios/sample_scenario.json
# -> output/audio/<title>/mix.m4a, subs.srt
```

### C. 전체 파이프라인 실행

```bash
python scripts/run_pipeline.py scenarios/sample_scenario.json
# 쇼츠 (기본)

python scripts/run_pipeline.py scenarios/sample_scenario.json --format longform
# 롱폼

python scripts/run_pipeline.py scenarios/sample_scenario.json --skip-render
# 씬은 세팅하되 렌더는 스킵 (UE 에디터에서 수동 확인용)
```

실행 중 UE 에디터는 **켜진 상태여야 하고**, 파이프라인이 끝날 때까지
에디터 창을 포커스하거나 씬을 건드리면 안 된다 (MRQ 가 PIE 로 돌아감).

## 시나리오 JSON 스펙

`pipeline/scenario.py` 에 Pydantic 모델이 정의되어 있다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `title` | str | 출력 파일명 베이스 |
| `level` | str | 레벨 에셋 경로, e.g. `/Game/Maps/Battlefield_Desert` |
| `format` | `shorts` \| `longform` | 기본 출력 포맷 |
| `characters[]` | list | id / role / blueprint / transform / idle_anim |
| `cameras[]` | list | 시간축 카메라 키프레임 (location/rotation/fov) |
| `character_cues[]` | list | 특정 시간에 애니메이션 재생 |
| `effects[]` | list | Niagara 시스템 트리거 (폭발, 연기, 머즐플래시) |
| `lines[]` | list | TTS 대사 (speaker/text) — 타임스탬프는 자동 계산 |
| `line_gap` | float | 대사 사이 간격(초) |
| `tail_padding` | float | 엔딩 여백(초) |

좌표계는 Unreal 기본: `location = (x, y, z) cm`, `rotation = (pitch, yaw, roll) deg`.

## 출력

```
output/
├── audio/<title>/
│   ├── line_000.mp3 ... line_NNN.mp3
│   ├── mix.m4a
│   └── subs.srt
├── renders/<title>/
│   └── frame.0000.png ... frame.NNNN.png
└── final/
    └── <title>.mp4
```

최종 MP4 는 `mov_text` 소프트섭 자막이 **embedded** 되어 있다.
유튜브 업로드 시 자막이 자동 인식된다.

## 트러블슈팅

### "Remote Control 서버 연결 실패"

1. UE 에디터 Output Log 에서 `HTTP Server Listening on port 30010` 메시지 확인
2. 포트 충돌: 30010 을 다른 프로세스가 점유하고 있는지 `netstat -ano | findstr 30010`
3. 에디터 cmd: `WebControl.StartServer`

### "MRQ 렌더가 안 끝난다"

- MRQ Preset 에 `Movie Pipeline PNG Sequence Output` 이 추가되어 있는지 확인
- `output/renders/<title>/.render_done` sentinel 파일이 생성되는지 확인
- 에디터가 Focus 상태인지 (PIE 렌더는 에디터 활성 필요)

### "ElevenLabs 토큰 초과"

- 시나리오 `lines[].text` 길이 체크
- 무료 티어는 월 10k 자 제한

### "캐릭터가 안 보인다"

- Blueprint 경로가 실제 UE 프로젝트 경로와 일치하는지
  - 대소문자 포함 완전히 일치해야 함
- 스폰 좌표가 레벨 지형 밖에 있지 않은지

## 확장 아이디어

- `scenarios/` 에 템플릿 여러 개 넣고 GitHub Actions 로 매일 한 편씩 자동 렌더
- `pipeline/composer.py` 에 BGM 트랙 합성 (라이선스 프리 음악 + ducking)
- ElevenLabs Sound Effect API 로 효과음(총성/폭발) 자동 합성
- Shotgrid/Perforce 연동 시 `pipeline/config.py` 의 경로를 P4 워크스페이스로 교체

## 라이선스

이 파이프라인 코드: MIT.
Unreal/Mixamo/Fab/ElevenLabs 에셋은 각각의 EULA 를 따른다.
