"""오디오 카탈로그: 멘트 템플릿, SFX 레지스트리, 보이스 설정.

세 계층의 캐시 구분:
- STATIC_LINES: 플레이어 이름 없는 완전 고정 멘트. 부팅 시 prewarm.
- SESSION_TEMPLATES: 플레이어 이름 슬롯이 있는 반고정 멘트. 좌석 등록 직후 prewarm.
- 그 외(dynamic): on-demand 합성. 예: 주사위 값/점수 포함 멘트.

resolve_static(text)으로 백엔드 텍스트가 어느 캐시 계층에 있는지 판단한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.constants import AgentRole


# 프로젝트 루트(boardgame-ai/) 기준 경로
_BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = _BASE_DIR / "assets"
TTS_CACHE_DIR = ASSETS_DIR / "tts_cache"
SFX_DIR = ASSETS_DIR / "sfx"
BGM_DIR = ASSETS_DIR / "bgm"

# 캐시 계층별 디렉토리
STATIC_CACHE_DIR = TTS_CACHE_DIR / "static"
SESSION_CACHE_DIR = TTS_CACHE_DIR / "session"
DYNAMIC_CACHE_DIR = TTS_CACHE_DIR / "dynamic"


@dataclass(frozen=True)
class VoiceConfig:
    """Google Cloud TTS 보이스 설정."""

    name: str  # ex: "ko-KR-Neural2-A"
    language_code: str = "ko-KR"
    speaking_rate: float = 1.0
    pitch: float = 0.0


# agent별 음성 매핑. 새 agent 추가 시 여기에만 등록.
# .env의 TTS_* 변수로 오버라이드 가능 (server.py 부팅 시점에 주입).
VOICE_BY_AGENT: dict[str, VoiceConfig] = {
    # 메인 진행자: 활기찬 남성 게임 호스트 톤
    AgentRole.NARRATOR.value: VoiceConfig(
        name="ko-KR-Neural2-C", speaking_rate=1.10, pitch=2.0
    ),
    # 규칙 위반 알림: 진중한 남성 톤 (narrator와 음색 차별화)
    AgentRole.REFEREE.value: VoiceConfig(
        name="ko-KR-Neural2-B", speaking_rate=0.95, pitch=-1.0
    ),
    # 템포 (현재 미사용)
    AgentRole.TEMPO.value: VoiceConfig(name="ko-KR-Neural2-B"),
}

DEFAULT_VOICE = VOICE_BY_AGENT[AgentRole.NARRATOR.value]

# 족보/하이라이트 외침 전용. narrator와 같은 보이스+속도, pitch만 +4 올려 텐션 표현.
EXCITED_VOICE = VoiceConfig(name="ko-KR-Neural2-C", speaking_rate=1.10, pitch=6.0)


# ── STATIC: 플레이어 이름 없는 완전 고정 멘트 ──────────────────────────────────
# 부팅 시 1회 prewarm. tts_cache/static/에 저장.
# 각 게임 담당자가 자기 게임 멘트를 여기 추가하면 자동으로 prewarm된다.
# 예: STATIC_LINES = ["게임이 종료되었습니다.", "잠시만 기다려주세요."]

STATIC_LINES: list[str] = [
    # ── 웨어울프 ──────────────────────────────────────────────────────────────────
    "밤이 되었습니다. 모두 눈을 감아주세요.",
    "도플갱어는 깨어나세요. 다른 플레이어 1명의 카드를 확인하세요. 그 역할이 됩니다.",
    "늑대인간은 깨어나세요. 서로를 확인하고 다시 눈을 감으세요.",
    "하수인은 깨어나세요. 늑대인간들은 엄지를 들어올려 자신을 알려주세요.",
    "프리메이슨은 깨어나세요. 서로를 확인하고 다시 눈을 감으세요.",
    "예언자는 깨어나세요. 다른 플레이어 1명 또는 중앙 카드 2장을 확인할 수 있습니다.",
    "강도는 깨어나세요. 다른 플레이어 1명의 카드와 자신의 카드를 교환할 수 있습니다.",
    "말썽쟁이는 깨어나세요. 자신을 제외한 두 플레이어의 카드를 서로 교환하세요.",
    "주정뱅이는 깨어나세요. 중앙 카드 1장을 가져와 자신의 카드와 교환하세요. 새 카드는 볼 수 없습니다.",
    "불면증환자는 깨어나세요. 자신의 카드를 확인하세요.",
    "모두 눈을 뜨세요! 토론을 시작합니다.",
    "아침이 밝았습니다. 모두 눈을 뜨세요.",
    "자, 지금부터 토론을 시작합니다.",
    "투표를 시작합니다. 제거할 플레이어를 손으로 가리키세요.",
    "마을 팀이 승리했습니다!",
    "늑대인간 팀이 승리했습니다!",
    "무두장이가 승리했습니다!",
]

# 족보/하이라이트 외침. EXCITED_VOICE로 별도 prewarm.
# 캐치프레이즈, 점수 발표 시 강조 외침 등.
# 예: EXCITED_LINES = ["야추!", "포 카드!"]

EXCITED_LINES: list[str] = []


# ── SESSION: 플레이어 이름 슬롯 멘트 템플릿 ────────────────────────────────────
# 좌석 등록 완료 후 prewarm. 각 플레이어 이름으로 변형해 tts_cache/session/<session_id>/에 저장.
# {player} 슬롯만 지원 (단일 슬롯). 다중 플레이어가 등장하는 멘트(점수 발표 등)는 dynamic으로.
# 예: SESSION_TEMPLATES = ["{player}님 차례입니다.", "{player}님, 다시 굴려주세요."]

SESSION_TEMPLATES: list[str] = []


def format_session_line(template: str, player_name: str) -> str:
    """SESSION_TEMPLATES의 {player} 슬롯에 이름을 채워 실제 멘트로 변환."""
    return template.format(player=player_name)


def expand_session_lines(player_names: list[str]) -> list[tuple[str, str]]:
    """각 플레이어 × 각 템플릿 조합으로 (template, formatted_text) 리스트 반환.

    AudioManager가 prewarm 시 호출. template은 캐시 키 일관성 위해 보관.
    """
    return [
        (template, format_session_line(template, name))
        for name in player_names
        for template in SESSION_TEMPLATES
    ]


# ── SFX 레지스트리 ─────────────────────────────────────────────────────────────
# 키 → 정적 파일 경로. frontend는 audio_url로 접근.

SFX_REGISTRY: dict[str, str] = {
    # 자산 파일 위치: audio/assets/sfx/<filename>. 서버가 /sfx/<filename>로 서빙.
    "hand_register": "/sfx/hand_register.mp3",  # 좌석 등록 완료
    "dice_roll": "/sfx/dice_roll.mp3",          # 주사위 굴림
    "score_select": "/sfx/score_select.mp3",    # 점수판 카테고리 선택
    "game_start": "/sfx/game_start.mp3",        # 게임 시작 알림
    "game_end": "/sfx/game_end.mp3",            # 결과 발표 징글
}

# BGM 레지스트리. 자산 파일: audio/assets/bgm/<filename>. 서버 /bgm/<filename>.
BGM_REGISTRY: dict[str, str] = {
    "lobby_loop": "/bgm/lobby_loop.mp3",  # 로비/게임 진행 중 배경음 (loop)
    "game_outro": "/bgm/game_outro.mp3",  # 우승자 발표 후 배경음
}


# ── 텍스트 → 캐시 계층 분류 ────────────────────────────────────────────────────


def classify_text(text: str) -> str:
    """text가 어느 캐시 계층에 속하는지 판단.

    Returns: "static" | "session" | "dynamic"
    """
    if text in STATIC_LINES:
        return "static"

    # SESSION_TEMPLATES와 정확히 매칭되는 패턴 탐색
    for template in SESSION_TEMPLATES:
        pattern = re.escape(template).replace(r"\{player\}", r"[가-힣A-Za-z0-9]{1,10}")
        if re.fullmatch(pattern, text):
            return "session"

    return "dynamic"


def session_template_for(text: str) -> str | None:
    """주어진 text가 어떤 SESSION_TEMPLATE을 instantiate한 것인지 역추적.

    캐시 키 안정화를 위해 사용. 매칭 실패 시 None.
    """
    for template in SESSION_TEMPLATES:
        pattern = re.escape(template).replace(r"\{player\}", r"([가-힣A-Za-z0-9]{1,10})")
        if re.fullmatch(pattern, text):
            return template
    return None
