"""정량 성능 측정 시스템.

BENCH_TRACE=1 환경변수가 켜진 상태에서 uvicorn을 부팅하면 server.py가
BenchmarkSession을 자동 시작한다. 게임 종료 시 finalize가 자동 호출되어
results/<timestamp>/ 디렉토리에 모든 측정 결과가 저장된다.

사용자는 평소처럼 게임만 진행하면 됨. 추가 명령 불필요.

자세한 설계: /Users/kimsungmin/.claude/plans/phase1-tts-woolly-hamming.md
"""
