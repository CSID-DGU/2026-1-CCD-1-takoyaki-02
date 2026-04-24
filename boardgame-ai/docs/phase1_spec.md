# Phase 1 인터페이스 계약서

비전 파이프라인 ↔ FSM 간 통신 명세. `core/` 타입을 기준으로 한다.

---

## 1. 전체 데이터 흐름

```
카메라 프레임
    │
    ▼
[비전 파이프라인]  (YOLO + MediaPipe + ByteTrack)
    │  raw 감지 결과
    ▼
[Fusion Engine]   ← FusionContext (FSM이 역방향으로 전송)
    │  3조건 통과한 GameEvent만
    │    ① FSM이 기대하는 이벤트 (expected_events)
    │    ② 물리적 변화 감지
    │    ③ N프레임 안정화
    ▼
[GameEvent]  ─────────────────────────────────────────►  [FSM]
                                                              │
                                                         상태 전이
                                                              │
                                                         [TTS 트리거]
                                                              │
                                                         TTSRequest
                                                              ▼
                                                         [오디오 모듈]
```

---

## 2. 앱 흐름

```
[PLAYER_SETUP]  ← 플레이어 추가/수정/삭제
      │              추가 시 좌석 등록 sub-flow 진입
      │                ↓
      │         [SEAT_REGISTER_RIGHT]  오른손 V-sign 대기
      │                ↓
      │         [SEAT_REGISTER_LEFT]   왼손 OK-sign 대기
      │                ↓
      │         PLAYER_SETUP로 복귀
      ▼
[GAME_SELECT]   ← 게임 선택 (yacht / werewolf)
      ▼
[게임 FSM]      ← 각 게임 팀원 영역
      ▼
[게임 종료]     ← 3선택지
      ├── CHANGE_PLAYERS  → PLAYER_SETUP  (players 유지)
      ├── CHANGE_GAME     → GAME_SELECT   (players 유지)
      └── RESTART         → 같은 게임 재시작 (players + game_type 유지)
```

---

## 3. 공통 메시지 봉투 (WSMessage)

모든 메시지는 `WSMessage`로 감싸서 전송한다.

```python
@dataclass
class WSMessage:
    msg_type: str        # MsgType enum value
    payload: dict        # 실제 데이터
    state_version: int   # FSM 전이마다 +1. 불일치 메시지는 drop
    msg_id: str          # 고유 ID (prefix로 출처 구분)
    timestamp: float     # time.time()
```

**msg_id prefix 규칙**

| prefix  | 용도                  |
|---------|-----------------------|
| `evt_`  | GameEvent             |
| `ctx_`  | FusionContext         |
| `tts_`  | TTSRequest 재생       |
| `int_`  | TTS 인터럽트          |
| `hello_`| 연결 확인             |
| `err_`  | 에러                  |

**MsgType 값**

`game_event`, `fusion_context`, `state_update`, `input`, `agent_message`,
`tts_play`, `tts_interrupt`, `game_result`, `hello`, `error`

---

## 4. 공통 이벤트 카탈로그 (CommonEventType)

게임별 전용 이벤트는 각 팀이 자기 모듈에서 추가 정의한다.

| event_type               | data 필드                                              | 발생 조건              |
|--------------------------|--------------------------------------------------------|------------------------|
| `seat_hand_registered`   | `hand`: "Right"\|"Left"<br>`wrist`: [x, y]<br>`gesture`: "v_sign"\|"ok_sign" | 손 제스처 안정화 완료 |
| `seat_registered`        | `seat_zone`: SeatZone dict                             | 양손 등록 완료        |
| `gesture_confirmed`      | `gesture`: str                                         | 제스처 N프레임 유지   |
| `rule_violation`         | `violation_type`: str<br>`detail`: str                 | 규칙 위반 감지        |
| `vision_error`           | `error_code`: str<br>`message`: str                    | 비전 처리 오류        |

> 요트 전용 이벤트(dice_stable 등)는 `vision/yacht/` 또는 팀 내 문서에서 정의.  
> 늑대 전용 이벤트는 `vision/werewolf/` 또는 팀 내 문서에서 정의.

---

## 5. FusionContext 구조

FSM이 매 상태 전이마다 비전으로 역방향 전송하는 컨텍스트.
Fusion Engine은 이 컨텍스트를 바탕으로 이벤트 필터링을 수행한다.

```python
@dataclass
class FusionContext:
    fsm_state: str               # 현재 Phase value 문자열
    game_type: str | None        # "yacht" | "werewolf" | None
    active_player: str | None    # 현재 행동 주체 player_id
    allowed_actors: list[str]    # 이벤트를 발생시킬 수 있는 player_id 목록
    expected_events: list[str]   # 수신 가능한 event_type 목록
    reject_events: list[str]     # 명시적 거부 목록 (expected보다 우선)
    valid_targets: dict | None   # 유효한 타겟 정보 (게임별 자유 형식)
    zones: dict                  # 관심 영역 좌표 (정규화)
    anchors: dict                # 기준점 좌표 (정규화)
    params: dict                 # Fusion 파라미터 오버라이드
```

**Fusion 3조건 (모두 통과해야 FSM에 전달)**

1. `event_type in expected_events` AND `event_type not in reject_events`
2. 물리적 변화 감지 (이전 프레임 대비 motion_threshold_norm 초과)
3. N프레임 안정화 (stabilization_frames 동안 동일 판정 유지)

---

## 6. 공통 Phase별 FusionContext 매핑

### PLAYER_SETUP

```python
FusionContext(
    fsm_state="player_setup",
    game_type=None,
    active_player=None,
    allowed_actors=[],          # 비전 이벤트 없음 (UI 입력만)
    expected_events=[],
)
```

### SEAT_REGISTER_RIGHT

```python
FusionContext(
    fsm_state="seat_register_right",
    game_type=None,
    active_player=registering_player_id,
    allowed_actors=[registering_player_id],
    expected_events=["seat_hand_registered"],
    params={"gesture_stabilization_frames": 10},
)
```

비전은 오른손 V-sign을 감지해 `seat_hand_registered` 이벤트를 발생시킨다.
`data.hand == "Right"`, `data.gesture == "v_sign"` 확인 필수.

### SEAT_REGISTER_LEFT

```python
FusionContext(
    fsm_state="seat_register_left",
    game_type=None,
    active_player=registering_player_id,
    allowed_actors=[registering_player_id],
    expected_events=["seat_hand_registered"],
    params={"gesture_stabilization_frames": 10},
)
```

비전은 왼손 OK-sign을 감지. `data.hand == "Left"`, `data.gesture == "ok_sign"` 확인 필수.

### GAME_SELECT

```python
FusionContext(
    fsm_state="game_select",
    game_type=None,
    active_player=None,
    allowed_actors=[],          # UI 입력만
    expected_events=[],
)
```

---

## 7. SeatZone 양손 등록 & handedness 매칭

### 등록 절차

1. FSM이 `SEAT_REGISTER_RIGHT` 진입 → FusionContext 전송
2. 비전이 오른손 V-sign 감지 → `seat_hand_registered` 이벤트 전송 (`hand="Right"`, `wrist=[x,y]`)
3. FSM이 `PlayerManager.record_hand("Right", wrist)` 호출
4. FSM이 `SEAT_REGISTER_LEFT` 진입 → FusionContext 전송
5. 비전이 왼손 OK-sign 감지 → `seat_hand_registered` 이벤트 전송 (`hand="Left"`, `wrist=[x,y]`)
6. FSM이 `PlayerManager.record_hand("Left", wrist)` 호출 → `True` 반환
7. FSM이 `PlayerManager.finalize_seat()` 호출 → `SeatZone` 조립 완료

```
SeatZone
  ├── right_hand_wrist: (P_R_x, P_R_y)   # 오른손 V-sign 위치
  └── left_hand_wrist:  (P_L_x, P_L_y)   # 왼손 OK-sign 위치
```

모든 좌표는 **정규화 float64 (0.0 ~ 1.0)**. 프레임 해상도 무관.

### 런타임 handedness 매칭

게임 중 비전이 손을 감지하면, 아래 규칙으로 플레이어를 특정한다.

```
detected_hand.handedness == "Right"
    → 각 Player의 seat_zone.right_hand_wrist와 Euclidean distance 계산
    → 최소 distance 플레이어가 주인

detected_hand.handedness == "Left"
    → 각 Player의 seat_zone.left_hand_wrist와 Euclidean distance 계산
    → 최소 distance 플레이어가 주인
```

distance 계산식:
```
d = sqrt((x1-x2)^2 + (y1-y2)^2)   # 정규화 좌표 기준
```

신뢰 임계값(`wrist_distance_min_norm` ~ `wrist_distance_max_norm`) 범위 밖이면
매칭 실패로 처리한다.

---

## 8. TTSRequest 사용법

FSM이 TTS 재생을 요청할 때 `WSMessage.make_tts_play(request)`로 봉투에 담아 전송.

```python
from core.audio import TTSRequest, AudioPriority
from core.envelope import WSMessage

request = TTSRequest(
    text="주사위를 굴려주세요",
    audio_url="/cache/roll_dice.wav",   # 캐시 없으면 None → TTS 엔진이 합성
    priority=AudioPriority.NORMAL,
    agent="narrator",
    interruptible=True,
    state_version=current_version,
)
msg = WSMessage.make_tts_play(request, state_version=current_version)
```

우선순위: `CRITICAL(1) > HIGH(2) > NORMAL(3) > LOW(4)`  
낮은 숫자가 높은 우선순위. CRITICAL은 현재 재생 중인 TTS를 즉시 인터럽트.

인터럽트 요청:
```python
msg = WSMessage.make_tts_interrupt(playback_id="pb_001", state_version=current_version)
```

---

## 9. Fusion 파라미터 테이블

`DEFAULT_PARAMS`에 정의된 기본값. `FusionContext.params`로 Phase별 오버라이드 가능.

| 파라미터                        | 기본값 | 설명                                       |
|---------------------------------|--------|--------------------------------------------|
| `motion_threshold_norm`         | 0.002  | 물리 변화 감지 최소 이동량 (정규화)        |
| `motion_start_frames`           | 3      | 움직임 시작 판정 최소 프레임 수            |
| `stabilization_frames`          | 30     | 이벤트 안정화 필요 프레임 수               |
| `gesture_stabilization_frames`  | 10     | 제스처 안정화 필요 프레임 수               |
| `handedness_confirm_frames`     | 5      | handedness 확정 프레임 수                  |
| `wrist_distance_min_norm`       | 0.05   | 손 매칭 최소 허용 거리 (정규화)            |
| `wrist_distance_max_norm`       | 0.30   | 손 매칭 최대 허용 거리 (정규화)            |
| `pointing_stabilization_frames` | 10     | 포인팅 안정화 필요 프레임 수               |
| `confidence_threshold`          | 0.6    | 이벤트 신뢰도 최소값                       |

실측 후 `FusionContext.params`에 오버라이드해 조정한다.

---

## 10. 메시지 플로우 예시 (좌석 등록)

```
FSM                             Fusion / 비전
 │                                   │
 │── FusionContext(SEAT_REGISTER_RIGHT) ──►│
 │                                   │  오른손 V-sign 감지
 │◄── GameEvent(seat_hand_registered, hand="Right") ──│
 │  record_hand("Right", wrist)      │
 │── FusionContext(SEAT_REGISTER_LEFT) ──►│
 │                                   │  왼손 OK-sign 감지
 │◄── GameEvent(seat_hand_registered, hand="Left") ──│
 │  record_hand("Left", wrist)       │
 │  finalize_seat() → SeatZone       │
 │── FusionContext(PLAYER_SETUP) ────►│
```

---

## 11. 게임별 명세 작성 가이드

core의 공통 타입 외에 게임별 이벤트·Phase는 각 팀이 직접 작성한다.

| 역할            | 파일 위치                              |
|-----------------|----------------------------------------|
| 요트 FSM        | `games/yacht/phases.py` (강병진)       |
| 요트 비전 이벤트 데이터 | `vision/yacht/` 또는 팀 내 문서 (김성민) |
| 늑대 FSM        | `games/werewolf/phases.py` (유형승)    |
| 늑대 비전 이벤트 데이터 | `vision/werewolf/` 또는 팀 내 문서 (양승경) |
