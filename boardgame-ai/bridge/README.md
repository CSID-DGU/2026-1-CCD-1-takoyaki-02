# bridge/

비전 파이프라인 ↔ FSM 통신 인터페이스.

- **`LocalBridge`** (현재 사용): 인프로세스 직접 연결. 개발·테스트용.
- **`WebSocketBridge`** (Phase 1 후반): 태블릿 UI 연동용 WebSocket 브릿지. 미구현.

## 사용 예시

```python
from bridge import LocalBridge

bridge = LocalBridge()
bridge.on_game_event(lambda event, ver: print(event, ver))
bridge.start()

# 비전 파이프라인에서
bridge.send_game_event(event, state_version=1)

bridge.stop()
```

`LocalBridge`와 `WebSocketBridge`는 동일한 `Bridge` 인터페이스를 구현하므로
FSM/비전 코드 변경 없이 교체 가능하다.
