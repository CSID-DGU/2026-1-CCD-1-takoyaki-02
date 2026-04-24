## 제목 형식
`[영역] 설명`
> 영역 예: 요트-비전, 요트-FSM, 늑대-비전, 늑대-FSM, 코어, 브릿지, 문서

---

## 작업 요약
<!-- 3~5줄로 무엇을 왜 했는지 설명 -->

---

## 변경 영역
- [ ] core/
- [ ] bridge/
- [ ] vision/
- [ ] games/
- [ ] audio/
- [ ] backend/
- [ ] frontend/
- [ ] tests/
- [ ] docs/
- [ ] CI / 설정

---

## 테스트
- [ ] 로컬에서 직접 실행해 동작 확인
- [ ] 관련 단위 테스트 추가 또는 업데이트

---

## 체크리스트
- [ ] `ruff check` 통과
- [ ] `black --check` 통과
- [ ] 기존 계약 테스트(`pytest tests/test_contracts.py`) 통과
- [ ] `core/` 수정 시 계약 테스트도 함께 업데이트
