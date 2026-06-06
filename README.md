<div align="center">

# 🎲 BoardMaster AI

### 오버헤드 카메라 기반 실시간 객체인식과 멀티에이전트를 활용한 보드게임 진행 시스템

플레이어는 실물 보드게임을 그대로 즐기고, AI가 진행자(딜러)를 대신해 **인식 · 심판 · 진행 · 해설**을 수행한다.

<!-- 동국대학교 · 2026-1 융합캡스톤디자인 · Team Takoyaki -->

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-5.4-646CFF?logo=vite&logoColor=white)
![YOLO](https://img.shields.io/badge/YOLO26s-Ultralytics-00FFFF)
![MediaPipe](https://img.shields.io/badge/MediaPipe-HandLandmarker-FF6F00?logo=google&logoColor=white)
![Google TTS](https://img.shields.io/badge/Google_Cloud-TTS-4285F4?logo=googlecloud&logoColor=white)

</div>

---

## 📌 프로젝트 개요

테이블 위에 설치된 **카메라 한 대**가 주사위 · 카드 · 손동작을 실시간으로 인식하고,
게임 규칙 엔진(FSM)과 네 개의 AI 에이전트가 협력하여 **사람 진행자 없이** 보드게임을 처음부터 끝까지 진행한다.
플레이어는 태블릿 화면과 음성 안내만 따라가면 되며, 현재 **요트다이스**와 **한밤의 늑대인간**을 지원한다.

보드게임은 규칙 설명 · 차례 관리 · 점수 계산 · 판정에 진행자를 필요로 하고, 규칙을 모르면 시작 자체가 어렵다.
본 시스템은 테이블을 **관찰하고, 규칙을 적용하고, 음성으로 안내하는** AI 진행자를 구현하여 이 진입 장벽을 해소하며,
플레이어 경험은 실물 그대로 유지하는 **Analog-first** 설계를 따른다.

| 항목 | 내용 |
|---|---|
| 🎯 **지원 게임** | 요트다이스(Yacht Dice) · 한밤의 늑대인간(One Night Werewolf) |
| 👁 **인식** | YOLO(주사위 · 카드) + MediaPipe(손) + OpenCV(주사위 눈 판독) |
| 🧠 **진행** | 심판 · 템포 · 진행 · 전략 네 에이전트의 우선순위 협력 + LLM 전략 코칭 |
| 🔊 **음성** | Google Cloud TTS · 3-계층 캐시 · 우선순위 큐(끼어들기 · 페이드) |
| 📱 **화면** | React 기반 태블릿 UI · WebSocket 실시간 동기화 |

---

## 🖼 시연 및 화면

<!--
  이미지 삽입: 캡처를 docs/images/ 에 저장하고 커밋한 뒤 아래 주석을 해제한다.
  (GitHub 웹 편집 화면에 드래그&드롭해도 자동 업로드된다. 폭은 <img ... width="600"> 으로 조절.)
-->
<div align="center">
[시스템 구성 — 오버헤드 카메라 + 테이블 + 태블릿](docs/images/setup.jpeg)
[로비 · 좌석 등록 화면](docs/images/lobby.png)
[요트다이스 진행 화면](docs/images/yacht.png)
[한밤의 늑대인간 진행 화면](docs/images/werewolf.png)
</div>

---

## ✨ 핵심 특징

### 1. 인식과 규칙을 분리한 양방향 통신 구조
비전(카메라)과 게임 규칙은 서로의 코드를 직접 호출하지 않고 **두 종류의 메시지로만** 통신한다.
- `GameEvent` (비전 → 규칙): *"특정 사건이 발생했다"* — 예: 주사위를 굴렸다, 카드를 확인했다.
- `FusionContext` (규칙 → 비전): *"현재 단계에서 기대하는 입력"* — 예: 현재 차례 · 허용 행동 · 기대 이벤트.

규칙 엔진이 단계마다 기대 이벤트를 한정해 전달하면 비전은 그 외의 사건을 발화하지 않는다.
이 **상태 기반 게이팅**은 오인식을 줄이는 동시에 새 게임을 추가하기 쉬운 확장성을 제공한다.

### 2. 오버헤드 환경에 특화된 인식 기법
- **팔 방향 기반 좌석 매칭** — 위에서 내려다보는 시점에서는 얼굴이 보이지 않으므로, 팔이 뻗어 들어오는 각도와
  추정한 몸 위치로 손의 주인을 식별한다. 이를 통해 **차례가 아닌 사람의 행동을 자동으로 감지**한다.
- **굴림 귀속(RollAttributor)** — 요트 주사위는 굴림통을 엎어 거의 구르지 않으므로, 움직임 대신
  **손의 트레이 점유 · 굴림통 사용 · 주사위 눈 분포 변화**를 종합해 실제 굴림을 판정한다.
- **영상처리 기반 주사위 눈 판독** — OpenCV로 밝기를 보정(CLAHE)한 뒤 원형 검출(HoughCircles)로 주사위 눈 1~6을 읽는다.

### 3. 멀티에이전트 진행자
하나의 거대한 모델 대신 **역할이 구분된 네 개의 경량 에이전트**가 우선순위에 따라 협력한다.
심판은 즉시 개입하고, 진행과 전략 안내는 게임 흐름을 방해하지 않는다.

| 우선순위 | 에이전트 | 역할 | 음성 우선순위 |
|:---:|---|---|:---:|
| 1 | **Rules** (심판) | 차례 위반 · 금지 행동 즉시 개입, 하위 억제 | CRITICAL |
| 2 | **Tempo** (템포) | 턴 타이머 경과 · 종료 임박 경고 | HIGH |
| 3 | **Progress** (진행) | 단계 전환 안내 및 해설 | NORMAL |
| 4 | **Strategy** (전략) | (선택) LLM 기반 전략 추천, 규칙 폴백 | LOW |

### 4. 자연스러운 음성 진행
Google Cloud TTS와 **3-계층 디스크 캐시**로 합성 비용을 최소화하고, **우선순위 큐**로 안내가 겹치지 않도록 직렬화한다.
긴급 안내(CRITICAL)는 진행 중인 멘트를 페이드아웃하며 즉시 끼어든다.

---

## 📊 성능

**플레이어 등록 → 요트다이스 → 한밤의 늑대인간**을 하나의 세션으로 연속 진행하며 측정하였다.
응답시간은 *End-to-End*(플레이어의 물리적 행동부터 화면 · 음성 반영까지)를 기준으로 한다.

#### 정확도
| 지표 | 값 |
|---|---:|
| 통합 세션 전체 인식 정확도 | **93.5%** |
| 게임 동일 가중 기하평균 | 86.6% |

> 표본: 4인 플레이 10판. 요트 총 **800회 주사위 굴림**, 한밤 총 **40회 역할 등록 인식**으로 산출.

#### 응답 속도 (End-to-End)
| 항목 | 평균 | 표준편차 | 표본 |
|---|---:|---:|:---:|
| 주사위 굴림 인식 | **약 1.14초** | 121 ms | n = 30 |
| 좌석/역할 등록 인식 | **208.5 ms** | 21 ms | n = 30 |
| 한밤 역할 카드 인식 | **430.7 ms** | 63.6 ms | n = 30 |
| 시스템 전체 | **0.47초** (기하평균) | — | — |

#### 지속성 (약 26분 연속 구동)
| 지표 | 값 |
|---|---|
| 비전 처리 속도 | 평균 **25.1 fps** (목표 30), 프레임 드랍률 **16.4%** |
| RAM 사용량 | 평균 **1,061 MB** · 최대 1,066 MB (표준편차 ±21 MB, 누수 없음) |
| 게임 완주율 | **100%** (운영자 개입 없이 완주) |
| TTS 캐시 적중률 | 64.6% (고정 멘트 100% · 동적 멘트 54.5%) |

<!--
  RAM 그래프: benchmarks/results/<세션>/_persistence_ram_panel.png 를 docs/images/persistence_ram.png 로 복사 후 주석 해제.
  (benchmarks/results/ 는 .gitignore 대상이므로 커밋되는 docs/images/ 로 옮겨야 표시된다.)
-->
<!-- <div align="center"><img src="docs/images/persistence_ram.png" width="700" alt="RAM 사용량 추이"></div> -->

> **측정 환경** — Apple M4 Pro (12-core) · RAM 48 GB · macOS · Python 3.13. RAM은 26분 내내 평탄하게 유지되어 장시간 구동에도 누수가 없음을 확인하였다.

---

## 🏗 시스템 아키텍처

```
        [오버헤드 카메라]
               │  단일 카메라 → 여러 인식기로 프레임 분배 (drop-oldest)
   ┌───────────┼────────────────┬─────────────────┐
   ▼           ▼                ▼                  (각각 별도 스레드, 활성 1개만 연산)
 로비        요트              늑대인간       ← 비전 파이프라인
 (손/제스처) (주사위/트레이)   (카드/손/투표)
   └───────────┴───── GameEvent ┴───────────┐
                                            ▼
                              Bridge (비전 ↔ 규칙 통신 계층)
                              ▲ FusionContext        │ GameEvent
              ┌───────────────┘                      ▼
        로비 오케스트레이터            게임별 Runner → Session → FSM (규칙 엔진)
        (플레이어 · 좌석 등록)                          │
                                            멀티에이전트 (심판 · 템포 · 진행 · 전략)
                                                       │
                                            오디오 매니저 (TTS · 효과음 · BGM 큐)
                                                       │
              WebSocket: /ws/tablet · /ws/yacht · /ws/werewolf
                                                       ▼
                                        [태블릿 — React UI]
```

- 단일 프로세스에서 FastAPI 서버와 비전 파이프라인이 함께 동작하며 인프로세스로 직접 통신한다.
- 통신은 **내부**(Bridge: `GameEvent`/`FusionContext`)와 **외부**(WebSocket: 화면 · 음성 · 입력) 두 평면으로 나뉜다.
- 모든 상태 변화에 버전 번호(`state_version`)를 부여해 화면 일관성과 성능 측정의 기준점으로 활용한다.

---

## 🧩 기술 스택

| 영역 | 스택 |
|---|---|
| **언어 / 런타임** | Python 3.11+ · asyncio |
| **물체 인식** | YOLO26s (Ultralytics) 커스텀 학습 · 추론 해상도 640 |
| **손 인식** | MediaPipe HandLandmarker (Tasks API, mediapipe 0.10+) · 최대 8손 |
| **영상처리** | OpenCV (HoughCircles · CLAHE · SimpleBlobDetector) · NumPy |
| **추적** | ByteTrack(자체 경량 구현) + Hungarian 매칭(lap/lapjv) |
| **백엔드** | FastAPI · uvicorn · websockets |
| **게임 로직** | 순수 Python FSM (외부 의존성 없음, StrEnum 상태머신) |
| **에이전트** | 우선순위 중재 + OpenAI `gpt-5.4-mini`(전략) · 규칙 기반 폴백 |
| **오디오** | Google Cloud TTS (ko-KR Neural2) · 3-계층 디스크 캐시 · 우선순위 큐 |
| **프론트엔드** | React 18.3 · Vite 5.4 · zustand 4.5 · WebSocket |
| **품질 관리** | pytest · ruff · black · mypy(strict) · GitHub Actions CI |

<!-- 기반 YOLO 모델 변형(YOLO26s/n 등)은 학습에 사용한 값으로 확인 후 정정. 커스텀 가중치는 weights/ 에 위치하며 git 제외. -->

**인식 모델** — 요트 YOLO 4종(`tray`·`tray_inner`·`roll_tray`·`dice`, `yacht_v4.pt`) ·
늑대 YOLO 13종(역할 카드 12종 + `Card_Back`, `werewolf_v8.pt`) · 손 랜드마크 21 keypoints(`hand_landmarker.task`).

---

## 🚀 시작하기

```bash
# 1) 설치
cd boardgame-ai
pip install -e ".[dev]"
pytest tests/test_contracts.py -v          # 동작 확인

# 2) 백엔드 (비전 파이프라인은 시작 시 자동 실행)
uvicorn backend.server:app --host 127.0.0.1 --port 8000

# 3) 프론트엔드 (Vite 개발 서버)
cd frontend && npm install && npm run dev
```

- YOLO 가중치(`weights/*.pt`)는 저장소에 포함되지 않으므로 Google Drive에서 받아 `weights/`에 둔다(없으면 해당 인식만 비활성).
- 음성을 사용하려면 `.env`에 `GOOGLE_APPLICATION_CREDENTIALS`(Google Cloud TTS 서비스 계정 키 경로)를 설정한다.
- 카메라 인식 과정을 단독 시각화하는 시연 스크립트는 [`boardgame-ai/demos/`](boardgame-ai/demos/README.md) 참고.

---

## 📂 저장소 구조

```
boardgame-ai/
├── core/        공유 타입 · 상수 (순수 Python — 외부 라이브러리 · 게임 종속 금지)
├── bridge/      비전 ↔ 규칙 통신 (LocalBridge / WebSocketBridge)
├── vision/      비전 파이프라인 (detectors · tracking · attribution · fusion · 게임별 pipeline)
├── games/       게임 규칙 FSM (yacht · werewolf)
├── agents/      멀티에이전트 (rules · tempo · progress · strategy)
├── audio/       Google TTS · 3-계층 캐시 · 우선순위 큐
├── backend/     FastAPI 서버 · 게임별 runner/session · WebSocket
├── frontend/    React 태블릿 UI (Vite)
├── benchmarks/  성능 측정 (정확도 · 응답시간 · FPS · 자원)
├── demos/       비전 시각화 시연 스크립트
├── weights/     YOLO 가중치 (git 제외, Drive 공유)
├── tests/       계약 · FSM · 융합 · 추적 테스트
└── docs/        설계 문서
```

---

## 👥 팀 — Takoyaki

| 이름 | 담당 |
|---|---|
| **양승경** (팀장) | 한밤의 늑대인간 비전 · 멀티에이전트 · 프로젝트 총괄 |
| 김성민 | 요트다이스 비전 · 플레이어 등록 및 매칭 · 로비 UI · 오디오/TTS · 성능 측정 |
| 강병진 | 요트다이스 FSM · 요트다이스 UI · 공통 타입(core) |
| 유형승 | 한밤의 늑대인간 FSM · 한밤의 늑대인간 UI · 비전↔FSM 브릿지/백엔드 |

---

## 📚 문서

- [시스템 상세 정리](docs/최종발표_시스템정리.md) — 아키텍처 · 통신 · 세부 로직 종합
- [새 게임 추가 가이드](boardgame-ai/docs/게임_추가_가이드.md) — 개념부터 단계별 안내
- [인터페이스 계약](boardgame-ai/docs/phase1_spec.md) · [오디오 명세](boardgame-ai/docs/phase2_audio_spec.md) · [팀 워크플로우](boardgame-ai/docs/team_workflow.md)
