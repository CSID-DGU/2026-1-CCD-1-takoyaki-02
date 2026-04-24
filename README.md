# 2026-1-CCD-1-takoyaki-02

## 📁 디렉토리 구조

```text
boardgame-ai/
├── app.py                  # 전체 모듈을 조립하고 실행하는 진입점
├── requirements.txt        # Python 의존성 목록
├── pyproject.toml          # 패키지 설정 및 개발 도구 설정
├── .gitignore              # Git 추적 제외 파일 목록
│
├── 📁 core/                # 공유 타입·상수 (순수 Python, 외부 라이브러리 금지)
│   ├── constants.py        # MsgType, CommonPhase, CommonEventType, DEFAULT_PARAMS 등
│   ├── models.py           # Player, SeatZone 공통 데이터 모델
│   ├── events.py           # GameEvent, FusionContext 이벤트 스키마
│   ├── envelope.py         # WSMessage 공통 메시지 봉투
│   ├── audio.py            # TTSRequest, AudioType, AudioPriority
│   └── player_manager.py   # 플레이어 CRUD + 좌석 등록 공통 로직
│
├── 📁 vision/              # 객체·제스처 인식을 수행하는 비전 파이프라인
│   ├── pipeline.py         # 전체 비전 파이프라인 조립
│   ├── detectors/          # 객체/손/주사위 눈 검출 모듈
│   ├── tracking/           # 객체 추적 및 주사위 ID 관리 모듈
│   └── fusion/             # 비전 결과를 게임 이벤트로 변환하는 모듈
│
├── 📁 games/               # 게임별 FSM, 상태, 규칙, 점수 계산 로직
│   ├── base_fsm.py         # FSM 공통 인터페이스
│   ├── registry.py         # 게임 등록 및 전환 관리
│   ├── yacht/              # 요트다이스 전용 FSM/상태/점수 로직
│   └── werewolf/           # 늑대인간 전용 FSM/상태/판정 로직
│
├── 📁 bridge/              # 비전 ↔ FSM 통신 인터페이스 계층
│   ├── interface.py        # 추상 Bridge 인터페이스 정의
│   ├── local_bridge.py     # 인프로세스 직접 연결 (개발/테스트용)
│   └── websocket_bridge.py # WebSocket 브리지 (Phase 1 후반 구현 예정)
│
├── 📁 audio/               # TTS, 효과음, BGM 등 오디오 관리
│   ├── manager.py          # 오디오 재생 큐와 인터럽트 관리
│   ├── tts_engine.py       # TTS 엔진 연동 모듈
│   └── assets/             # 효과음, 배경음악, TTS 캐시 파일
│
├── 📁 backend/             # FastAPI 서버와 WebSocket 통신 처리
│   ├── server.py           # FastAPI 앱 생성 및 서버 설정
│   └── ws/                 # 태블릿과의 WebSocket 통신 처리 모듈
│
├── 📁 frontend/            # React 기반 태블릿 UI 및 게임 화면
│   ├── src/
│   │   ├── hooks/          # WebSocket 등 공통 프론트 훅
│   │   ├── pages/          # 로비 및 게임별 메인 페이지
│   │   └── components/     # 공통/게임별 UI 컴포넌트
│   ├── package.json        # 프론트엔드 의존성 및 스크립트 설정
│   └── vite.config.js      # Vite 빌드 설정
│
├── 📁 weights/             # 학습된 모델 가중치 (Git 제외, Google Drive 공유)
│   └── README.md           # 명명 규칙 및 관리 방법
│
├── 📁 training/            # 객체 인식 모델 학습 코드와 설정 파일
│   ├── yacht/              # 요트다이스 학습 데이터 설정
│   ├── werewolf/           # 늑대인간 학습 데이터 설정
│   └── train_colab.ipynb   # 모델 학습 실험 노트북
│
├── 📁 tools/               # 수집·추출·테스트용 보조 스크립트
│   ├── recorder.py         # 데이터 수집용 녹화 스크립트
│   ├── frame_extractor.py  # 영상 프레임 추출 스크립트
│   └── dice_prototype_v2.py# 주사위 인식 프로토타입 코드
│
├── 📁 tests/               # 게임 로직과 규칙 검증용 테스트 코드
│   ├── test_contracts.py   # core/ 타입 직렬화·구조 계약 테스트 (CI 필수)
│   ├── test_yacht_fsm.py   # 요트다이스 FSM 테스트
│   ├── test_werewolf_fsm.py# 늑대인간 FSM 테스트
│   ├── test_scoring.py     # 점수 계산 테스트
│   └── test_fusion_rules.py# 퓨전 규칙 테스트
│
└── 📁 docs/                # 설계 문서와 통신/데이터 흐름 명세
    ├── phase1_spec.md      # 비전↔FSM 인터페이스 계약서 (Phase 1)
    ├── team_workflow.md    # 브랜치·PR·CI·가중치 관리 규칙
    ├── FSM_설계.md         # FSM 설계 문서
    ├── WebSocket_명세.md   # WebSocket 메시지 명세
    ├── 데이터흐름_명세.md   # 시스템 데이터 흐름 문서
    └── diagrams/           # 아키텍처 및 설계 다이어그램
```
