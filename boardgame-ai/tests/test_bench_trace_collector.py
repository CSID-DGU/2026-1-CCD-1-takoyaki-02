"""benchmarks.trace_collector 회귀 방지 테스트.

로그 포맷이 미세하게 바뀌면 모든 분석 모듈이 깨지므로 정상/비정상 입력 케이스를 고정한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.trace_collector import collect, collect_to_list, parse_line


class TestParseLine:
    def test_event_with_positional_args(self) -> None:
        line = "2026-05-17T20:27:31.117 event_emit ROLL_CONFIRMED p1 100 1779017251.117711"
        result = parse_line(line)
        assert result is not None
        assert result["log_ts"] == "2026-05-17T20:27:31.117"
        assert result["event"] == "event_emit"
        assert result["args"] == ["ROLL_CONFIRMED", "p1", "100", "1779017251.117711"]
        assert result["kv"] == {}

    def test_event_with_kv_pairs(self) -> None:
        line = "2026-05-17T20:27:31.117 tts_synth_done abc123 hit=1 layer=static elapsed_ms=0.0"
        result = parse_line(line)
        assert result is not None
        assert result["event"] == "tts_synth_done"
        assert result["args"] == ["abc123"]
        assert result["kv"] == {"hit": "1", "layer": "static", "elapsed_ms": "0.0"}

    def test_event_with_mixed_args_and_kv(self) -> None:
        line = "2026-05-17T20:27:31.117 audio_enqueue tts_play pb_xyz hit=0 1779017251.5"
        result = parse_line(line)
        assert result is not None
        assert result["args"] == ["tts_play", "pb_xyz", "1779017251.5"]
        assert result["kv"] == {"hit": "0"}

    def test_event_without_args(self) -> None:
        line = "2026-05-17T20:27:31.117 game_end"
        result = parse_line(line)
        assert result is not None
        assert result["event"] == "game_end"
        assert result["args"] == []
        assert result["kv"] == {}

    def test_trailing_whitespace_tolerated(self) -> None:
        line = "2026-05-17T20:27:31.117 sfx_play dice_roll   \n"
        result = parse_line(line)
        assert result is not None
        assert result["args"] == ["dice_roll"]

    @pytest.mark.parametrize(
        "invalid",
        [
            "",
            "not a log line",
            "INFO some random text",
            "2026/05/17 not iso format event_name",
            "20-05-17T20:27:31.117 event arg",  # year too short
        ],
    )
    def test_invalid_lines_return_none(self, invalid: str) -> None:
        assert parse_line(invalid) is None


class TestCollect:
    def test_collect_to_list_skips_invalid(self, tmp_path: Path) -> None:
        log = tmp_path / "app.log"
        log.write_text(
            "2026-05-17T20:27:31.117 event_a foo\n"
            "garbage line should be skipped\n"
            "2026-05-17T20:27:31.118 event_b hit=1\n",
            encoding="utf-8",
        )
        events = collect_to_list(log)
        assert len(events) == 2
        assert events[0]["event"] == "event_a"
        assert events[1]["kv"] == {"hit": "1"}

    def test_collect_writes_jsonl(self, tmp_path: Path) -> None:
        log = tmp_path / "app.log"
        log.write_text(
            "2026-05-17T20:27:31.117 event_a foo\n" "2026-05-17T20:27:31.118 event_b bar\n",
            encoding="utf-8",
        )
        out = tmp_path / "traces.jsonl"
        count = collect(log, out)
        assert count == 2
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert '"event": "event_a"' in lines[0]
