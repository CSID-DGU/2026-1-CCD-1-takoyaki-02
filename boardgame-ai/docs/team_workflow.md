# 팀 워크플로우

## 브랜치 규칙

```
feat/<영역>-<기능>   예) feat/yacht-vision-dice-detect
fix/<영역>-<설명>    예) fix/core-seat-zone-distance
chore/<설명>         예) chore/ci-add-mypy
```

## PR 규칙

- 제목: `[영역] 설명`  
  영역 예: `요트-비전`, `요트-FSM`, `늑대-비전`, `늑대-FSM`, `코어`, `브릿지`, `문서`
- CI 통과 + 팀원 리뷰 1명 이상 후 머지

## CI 자동 검증 항목

| 단계           | 대상                       |
|----------------|----------------------------|
| `ruff check`   | `core/`, `bridge/`, `tests/` |
| `black --check`| `core/`, `bridge/`, `tests/` |
| `mypy`         | `core/`, `bridge/`           |
| `pytest`       | `tests/test_contracts.py`    |

## 새 이벤트 추가 시

- **공통 이벤트** (게임 불문): `core/constants.py`의 `CommonEventType`에 추가 + `tests/test_contracts.py` 업데이트
- **게임별 이벤트**: 해당 게임 모듈(`games/yacht/`, `vision/yacht/` 등)에만 추가. core/ 수정 불필요

## 모델 가중치 관리

- Git 커밋 **금지** (`.gitignore`에 등록됨)
- Google Drive 공유
- 명명 규칙: `yacht_v{N}_{YYYYMMDD}.pt`, `werewolf_v{N}_{YYYYMMDD}.pt`
- 자세한 내용: [`weights/README.md`](../weights/README.md)

## 커뮤니케이션 채널

| 채널      | 용도                        |
|-----------|-----------------------------|
| GitHub    | 공식 기록 (PR, Issue, 리뷰) |
| Discord   | 실시간 소통                 |
| 카카오톡  | 긴급 연락                   |
