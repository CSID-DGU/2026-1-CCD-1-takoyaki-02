# 2026-1-CCD-1-takoyaki-02

## 📁 디렉토리 구조

```text
boardmaster-ai/
├── app.py                  # 전체 모듈을 조립하고 실행하는 진입점
├── requirements.txt        # Python 의존성 목록
├── .gitignore              # Git 추적 제외 파일 목록
│
├── 📁 core/                # 게임 공통 모델과 이벤트, 식별 로직
│   ├── models.py           # Player, Session 등 공통 데이터 모델
│   ├── events.py           # GameEvent, FusionContext 등 공통 이벤트 스키마
│   ├── player_identifier.py# zone + handedness 기반 플레이어 식별
│   ├── seat_registration.py# 좌석 등록 및 제스처 확인 로직
│   └── pointing_resolver.py# 검지 방향과 앵커를 매칭하는 로직
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
├── 📁 bridge/              # 비전과 게임 로직을 연결하는 인터페이스 계층
│   ├── interface.py        # 공통 브리지 인터페이스 정의
│   ├── local_bridge.py     # 로컬 실행용 직접 호출 브리지
│   └── websocket_bridge.py # 분리 배포용 WebSocket 브리지
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
├── 📁 weights/             # 학습된 모델 가중치 파일 저장
│   ├── yacht_best.pt       # 요트다이스 객체 인식 가중치
│   └── werewolf_best.pt    # 늑대인간 객체 인식 가중치
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
│   ├── test_yacht_fsm.py   # 요트다이스 FSM 테스트
│   ├── test_werewolf_fsm.py# 늑대인간 FSM 테스트
│   ├── test_scoring.py     # 점수 계산 테스트
│   └── test_fusion_rules.py# 퓨전 규칙 테스트
│
└── 📁 docs/                # 설계 문서와 통신/데이터 흐름 명세
    ├── FSM_설계.md         # FSM 설계 문서
    ├── WebSocket_명세.md   # WebSocket 메시지 명세
    ├── 데이터흐름_명세.md   # 시스템 데이터 흐름 문서
    └── diagrams/           # 아키텍처 및 설계 다이어그램
