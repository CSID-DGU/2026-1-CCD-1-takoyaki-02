# core/

공유 타입 & 상수 정의. **외부 라이브러리 import 금지. 게임 종속 금지.**

## 파일별 역할

| 파일                | 역할                                              |
|---------------------|---------------------------------------------------|
| `constants.py`      | `MsgType`, `CommonPhase`, `CommonEventType`, `AgentRole`, `InputType`, `DEFAULT_PARAMS` |
| `models.py`         | `Player`, `SeatZone` 데이터 모델                  |
| `events.py`         | `GameEvent`, `FusionContext`                      |
| `envelope.py`       | `WSMessage` (공통 메시지 봉투 + 팩토리 메서드)    |
| `audio.py`          | `TTSRequest`, `AudioType`, `AudioPriority`        |
| `player_manager.py` | `PlayerManager` — 플레이어 CRUD + 좌석 등록 로직  |

## 게임별 확장

게임별 Phase와 EventType은 core가 아닌 각 게임 팀 영역에서 정의한다.

| 게임   | Phase / FSM              | 비전 이벤트 스키마        |
|--------|--------------------------|---------------------------|
| 요트   | `games/yacht/phases.py`  | `vision/yacht/`           |
| 늑대   | `games/werewolf/phases.py` | `vision/werewolf/`      |

`FusionContext.fsm_state`와 `expected_events`는 문자열로 처리하므로 core가 특정 게임을 import하지 않는다.
