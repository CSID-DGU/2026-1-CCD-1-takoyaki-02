# BoardGame AI

오버헤드 카메라 + YOLO/MediaPipe/ByteTrack으로 물리 보드게임을 자동 진행하는 시스템. **요트다이스**와 **한밤의 늑대인간** 지원. 사람은 실제 보드게임을 하고, AI가 뒤에서 조용히 진행·판정·해설 (Analog-first). 확장성 있는 구조로 설계(게임별 내용과 공용 내용 구분)

## 빠른 시작

```bash
cd boardgame-ai
pip install -e ".[dev]"
python -c "from core import GameEvent, FusionContext, PlayerManager; print('OK')"
pytest tests/test_contracts.py -v
```

## 팀 구성

| 이름   | 담당             |
|--------|----------------|
| 김성민 | 요트 비전          |
| 강병진 | 요트 FSM          |
| 양승경 | 늑대 비전          |
| 유형승 | 늑대 FSM          |

## 앱 흐름

`PLAYER_SETUP` → (좌석 등록) → `GAME_SELECT` → `게임 FSM` → `게임 종료`  
종료 후 3선택지: 플레이어 변경 / 게임 변경 / 재시작

## 데이터 흐름

- 비전: raw 프레임 → Fusion 3조건(FSM 기대 + 물리 변화 + N프레임 안정) 통과한 이벤트만 FSM에
- FSM: 상태 전이 + TTS 트리거, 전이한 상태 정보 비전으로 전달
- 통신: 개발 중 `LocalBridge` (인프로세스), 배포 시 `WebSocketBridge`

## 레포 구조

```
boardgame-ai/
├── core/        공유 타입 & 상수 (순수 Python, 외부 라이브러리 금지)
├── bridge/      비전↔FSM 통신 인터페이스
├── vision/      비전 파이프라인 (YOLO, MediaPipe, ByteTrack)
├── games/       게임별 FSM
├── audio/       TTS/오디오 모듈
├── backend/     FastAPI 백엔드
├── frontend/    태블릿 UI (React)
├── tests/       계약 테스트
├── docs/        설계 문서
├── weights/     모델 가중치 (Git 제외, Drive 공유)
└── training/    학습 스크립트
```

## 핵심 원칙

1. `core/`는 순수 Python만 — numpy, cv2, torch 등 외부 라이브러리 import 금지
2. `core/`는 게임을 몰라야 함 — 요트·늑대 전용 로직을 core에 넣지 않음
3. 좌표는 정규화 float64 (0.0 ~ 1.0)
4. ID는 전부 문자열
5. `state_version`: FSM 전이마다 +1, 불일치 메시지 drop
6. FSM은 Fusion 통과한 `GameEvent`만 수신 — raw 프레임 수신 금지

## Phase

- **Phase 1**: 요트 + 늑대 병렬 구현. LocalBridge. 고정 TTS.
- **Phase 2**: 멀티에이전트 LLM 진행자, 태블릿 UI, WebSocketBridge.

## 작업 규칙

- 브랜치: `feat/<영역>-<기능>`, `fix/...`, `chore/...`
- PR 제목: `[영역] 설명` (영역: 요트-비전, 요트-FSM, 늑대-비전, 늑대-FSM, 코어, 브릿지)
- CI: ruff + black + mypy(core/bridge) + pytest 계약 테스트 자동
- `core/` 수정 시 계약 테스트도 같은 PR에서 업데이트
- Weights는 Git 커밋 금지. Google Drive 공유 (`yacht_v{N}_{YYYYMMDD}.pt`)
- 커뮤니케이션: GitHub(공식 기록), Discord(실시간), 카톡(긴급)

## 주요 문서

- [Phase 1 인터페이스 계약서](docs/phase1_spec.md)
- [팀 워크플로우](docs/team_workflow.md)
