# Phase 2 오디오·TTS 시스템 사용 가이드

담당: 김성민. 이 문서는 다른 팀원이 오디오 시스템을 **어떻게 호출하는지**만 다룹니다. 내부 구현은 [audio/](../audio/) 디렉토리 코드와 주석 참고.

---

## TL;DR

| 누구 | 어디서 | 어떻게 |
|---|---|---|
| 게임 FSM 담당 | `games/<game>/fsm.py` | `self._make_tts("문장")` 한 줄. 또는 catalog에 멘트 등록. |
| LLM 멀티에이전트 | 어디서든 | `audio_manager.enqueue_llm_line(agent, text, priority)` |
| 효과음 트리거 | FSM 메시지 리스트 | `WSMessage.make_sfx_play(SFXRequest(name="..."))` |

---

## 1. 시스템 개요

```
[FSM tts_play] ─┐
                ├─► [AudioManager 우선순위 큐] ─► [합성/캐시] ─► [WebSocket → 태블릿]
[LLM enqueue]  ─┤
                │
[SFX/BGM]      ─┘
                                    ▲
                                    │ audio_ack
                                    └──── [태블릿 재생]
```

- **합성 백엔드**: Google Cloud TTS (Neural2). API 키는 `.env`의 `GOOGLE_APPLICATION_CREDENTIALS`.
- **캐시**: sha1(text + voice + rate + pitch). static / session / dynamic 세 계층 자동 분류.
- **재생 위치**: 태블릿 브라우저 (HTML5 Audio).
- **재생 채널 (동시성 정리)**:
  - **TTS와 SFX는 같은 채널** — 한 큐에 들어가 직렬 재생. 효과음 "띠링" 후 TTS "성민님 차례입니다." 처럼 자연스러운 순서.
  - **BGM은 별도 채널** — TTS·SFX와 항상 동시 재생 가능.
  - **BGM 자동 더킹** — TTS 시작 시 BGM 볼륨 -12dB 자동 감쇠, TTS 끝나면 원복.
- **큐 정책 (TTS/SFX 채널)**: priority 오름차순(CRITICAL=1 우선), 동순위 도착순. ack-driven (한 번에 하나).
- **인터럽트**: CRITICAL 도착 시 현재 재생 fade-out(150ms) + interruptible 큐 항목 제거.

---

## 2. 게임 FSM 담당자용

### 2.1 FSM에서 멘트 emit

요트 FSM이 쓰는 헬퍼([games/yacht/fsm.py:333-344](../games/yacht/fsm.py#L333-L344))를 그대로 복사해 자기 FSM에 넣으면 끝.

```python
def _make_tts(
    self,
    text: str,
    priority: AudioPriority = AudioPriority.NORMAL,
) -> WSMessage:
    request = TTSRequest(
        text=text,
        priority=priority,
        agent=AgentRole.NARRATOR.value,
        state_version=self.state.state_version,
    )
    return WSMessage.make_tts_play(request, self.state.state_version)
```

상태 전이 시:
```python
return [
    self._make_state_update(),
    self._emit_fusion_context(),
    self._make_tts("플레이어님 차례입니다."),  # ← 이 한 줄
]
```

**우선순위 가이드**:
- `AudioPriority.NORMAL` (기본): 일반 진행 멘트
- `AudioPriority.HIGH`: 빠른 진행/템포 멘트
- `AudioPriority.CRITICAL`: **규칙 위반·즉시 알려야 할 것**. 현재 재생 중인 진행 멘트를 끊고 끼어든다.
- `AudioPriority.LOW`: 거의 안 씀

### 2.2 자주 쓰는 멘트는 사전 등록 (선택)

[audio/catalog.py](../audio/catalog.py)에 추가하면 **서버 부팅 시 사전 합성** → 런타임 합성 지연 0.

```python
# 플레이어 이름 없는 완전 고정 멘트
STATIC_LINES: list[str] = [
    "게임이 종료되었습니다.",
    "잠시만 기다려주세요.",
]

# 플레이어 이름 슬롯 멘트 (좌석 등록 직후 미리 합성됨)
SESSION_TEMPLATES: list[str] = [
    "{player}님 차례입니다.",
    "{player}님, 다시 굴려주세요.",
]

# 흥분된 톤으로 외칠 멘트
EXCITED_LINES: list[str] = [
    "야추!",
    "포 카드!",
]
```

**카탈로그에 없어도 동작은 함** — `dynamic` 캐시로 떨어져 첫 호출 시 ~600ms 합성, 같은 문장 두 번째부터 캐시 hit.

### 2.3 효과음(SFX) 트리거

자산 파일을 `audio/assets/sfx/`에 두면 자동으로 `/sfx/<filename>`로 서빙됨.
이미 등록된 SFX 키 (catalog.SFX_REGISTRY):

| 키 | 파일 | 용도 |
|---|---|---|
| `hand_register` | hand_register.mp3 | 좌석 등록 완료 |
| `dice_roll` | dice_roll.mp3 | 주사위 굴림 |
| `score_select` | score_select.mp3 | 점수판 카테고리 선택 |
| `game_start` | game_start.mp3 | 게임 시작 알림 |
| `game_end` | game_end.mp3 | 결과 발표 징글 |

새 SFX는 [audio/catalog.py](../audio/catalog.py)의 `SFX_REGISTRY`에 키 추가하고 파일을 그 디렉토리에 넣으면 끝.

FSM에서 호출:

```python
from core.audio import SFXRequest, AudioPriority
from core.envelope import WSMessage

sfx = SFXRequest(name="dice_roll", priority=AudioPriority.HIGH)
return [
    WSMessage.make_sfx_play(sfx),  # ← AudioManager가 자동 라우팅
    # ...
]
```

**효과음 → TTS 자연스럽게 잇기 (sequence_id)**:

```python
# 점수 선택 → "딸깍" → "성민님 50점입니다." 순으로 자연스럽게
sid = f"score_announce_{state_version}"
sfx = SFXRequest(name="score_select", priority=AudioPriority.HIGH,
                 sequence_id=sid, seq_index=0)
tts_req = TTSRequest(text=f"{name}님 {score}점입니다.",
                     sequence_id=sid, seq_index=1)
return [
    WSMessage.make_sfx_play(sfx),
    WSMessage.make_tts_play(tts_req),
    # ...
]
```

같은 `sequence_id` 묶음은 `seq_index` 순서로 직렬 재생됨.

---

## 3. LLM 멀티에이전트 담당자용

### 3.1 진입점

```python
# 어디서든 audio_manager를 받으면:
await audio_manager.enqueue_llm_line(
    agent="referee",                   # "narrator" | "referee" | "tempo"
    text="플레이어님, 규칙을 다시 한 번 안내드릴게요.",
    priority=AudioPriority.HIGH,       # 보통 HIGH, 위반 알림이면 CRITICAL
)
```

`audio_manager`는 `app.state.audio_manager`로 접근하거나 (FastAPI 컨텍스트), 외부 모듈이면 backend에서 명시적으로 주입.

### 3.2 시퀀스: 여러 문장을 직렬로 출력

LLM이 긴 응답을 문장 단위로 끊어 여러 번 호출할 때, **같은 `sequence_id`**로 묶으면 frontend에서 자연스럽게 직렬 재생됨.

```python
sid = "llm_response_42"
for i, sentence in enumerate(llm_sentences):
    await audio_manager.enqueue_llm_line(
        agent="narrator",
        text=sentence,
        sequence_id=sid,
        seq_index=i,
    )
```

같은 sequence 내 항목은 `seq_index` 순서로 ack를 기다리며 직렬 재생.

### 3.3 인터럽트 정책

- 기본 `interruptible=True` — CRITICAL 멘트가 오면 끊김.
- LLM 멘트는 **interruptible 유지 권장**. 사용자가 다음 행동을 하려는데 LLM이 길게 말하고 있으면 끊겨야 함.
- 만약 절대 끊기지 말아야 할 메시지면 (현재는 그런 경우 없음) `enqueue_tts(..., interruptible=False)`.

### 3.4 가이드라인

- **문장 길이**: 1-2 문장, 한국어 60자 이하 권장. 길면 합성 시간↑·끊기 어려움.
- **agent 선택**: `narrator` (진행 멘트 톤), `referee` (규칙 알림 톤, 진중한 남성). 보이스 차별화는 [audio/catalog.py](../audio/catalog.py)의 `VOICE_BY_AGENT`에서 관리.

---

### 2.4 BGM 시작·정지

자산 파일을 `audio/assets/bgm/`에 두고 catalog 등록. 이미 등록된 BGM:

| 키 | 파일 | 용도 |
|---|---|---|
| `lobby_loop` | lobby_loop.mp3 | 로비/게임 진행 중 (loop) |
| `game_outro` | game_outro.mp3 | 우승자 발표 후 배경음 |

호출 (backend에서 `audio_manager` 받아 사용):

```python
# 게임 시작 시
await audio_manager.play_bgm("lobby_loop", loop=True, gain_db=-6.0)

# 우승자 발표 직전 교체
await audio_manager.play_bgm("game_outro", loop=True, fade_ms=800)

# 정지
await audio_manager.stop_bgm()
```

TTS가 재생되는 동안 BGM은 자동으로 -12dB 감쇠(ducking)됨. 별도 호출 필요 없음.

---

## 4. backend 통합 (참고)

이미 다 연결돼 있어요. 새로 세션을 만들 일이 있다면:

```python
from audio.manager import AudioManager

session = SomeGameSession(
    websocket=ws,
    audio_manager=app.state.audio_manager,  # ← 주입
)
# 세션 send() 안에서 audio 메시지 자동 라우팅됨 (yacht_session 참고)
# audio_ack input 처리도 자동 (handle_client_message)
```

---

## 5. 메시지 스키마

backend → 태블릿:

```jsonc
// tts_play (audio_url은 AudioManager가 채워서 보냄)
{ "msg_type": "tts_play", "payload": {
    "text": "...", "audio_url": "/cache/tts/session/.../...wav",
    "priority": 3, "playback_id": "pb_xxx",
    "sequence_id": null, "seq_index": 0, "interruptible": true,
    "agent": "narrator", "state_version": 17
}}

// tts_interrupt (AudioManager가 CRITICAL 도착 시 자동 발행)
{ "msg_type": "tts_interrupt", "payload": { "playback_id": "pb_xxx" }}

// sfx_play
{ "msg_type": "sfx_play", "payload": {
    "name": "dice_roll", "audio_url": "/sfx/dice_roll.wav",
    "priority": 2, "playback_id": "pb_xxx"
}}

// bgm_play (TTS 시작 시 frontend에서 자동 더킹됨)
{ "msg_type": "bgm_play", "payload": {
    "name": "lobby_loop", "audio_url": "/bgm/lobby_loop.mp3",
    "loop": true, "gain_db": -6.0, "fade_ms": 500
}}
// audio_url 빈 문자열이면 정지 신호.
```

태블릿 → backend (input 봉투 안):

```jsonc
{ "msg_type": "input", "input_type": "audio_ack", "data": {
    "playback_id": "pb_xxx",
    "status": "played" | "interrupted" | "error",
    "started_at": 1715683200.123, "ended_at": 1715683202.456
}}
```

---

## 6. 환경 변수 (`.env`)

```bash
GOOGLE_APPLICATION_CREDENTIALS=./.secrets/google-tts.json  # 절대경로 권장
TTS_VOICE_NARRATOR=ko-KR-Neural2-C
TTS_SPEAKING_RATE=1.10
TTS_PITCH=2.0
TTS_VOICE_REFEREE=ko-KR-Neural2-B
TTS_REFEREE_RATE=0.95
TTS_REFEREE_PITCH=-1.0
```

값 변경하면 캐시 키가 바뀌므로 기존 wav는 자동으로 사용 안 됨. 다음 호출 시 새 보이스로 재합성.

---

## 7. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| 멘트가 재생 안 됨 | autoplay 차단 | 사용자가 화면을 한 번 클릭/터치해서 unlock. App.jsx에서 자동 unlock 처리됨. |
| 첫 호출이 1-2초 지연 | dynamic 합성 | catalog에 등록하면 사전 합성됨 |
| `TTSEngine not available` 로그 | API 키 미설정 | `.env`의 `GOOGLE_APPLICATION_CREDENTIALS` 확인 |
| `tts_play` 메시지에 `audio_url=null` | 합성 실패 (network/quota) | text-only로 frontend에 보내짐 (재생 안 됨). backend 로그 확인 |
| 같은 멘트 매번 합성됨 | 보이스 설정이 환경마다 다름 | `.env`가 모든 머신에서 같은지 확인 |
| 인터럽트가 너무 갑작스러움 | fade-out 시간 조정 | `frontend/src/hooks/useAudioPlayer.js`의 `FADE_OUT_MS` 상수 변경 |
