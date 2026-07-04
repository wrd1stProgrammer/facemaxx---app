from __future__ import annotations

from typing import Final, assert_never

from app.schemas.flirtist_product import FlirtistProductSessionRequest, FlirtistReplyCoaching
from app.services.flirtist_product_ai import FlirtistProductAIError

_REQUIRED_REPLY_PACK_STYLES: Final[frozenset[str]] = frozenset(
    {"genuine", "witty", "flirty", "romantic", "nsfw"}
)
_MIN_REPLIES_PER_PACK: Final = 4


def ensure_complete_screenshot_reply_packs(
    request: FlirtistProductSessionRequest,
    coaching: FlirtistReplyCoaching,
) -> None:
    match (request.mode, request.source):
        case ("reply_coach", "screenshot"):
            if not request.imageBase64:
                return
            if _has_complete_reply_packs(coaching):
                return
            raise FlirtistProductAIError(reason=_analysis_failure_message(request.locale))
        case ("reply_coach", "manual") | ("score_analysis", "manual") | ("score_analysis", "screenshot"):
            return
        case unreachable:
            assert_never(unreachable)


def _has_complete_reply_packs(coaching: FlirtistReplyCoaching) -> bool:
    complete_styles = {
        pack.style.strip().lower()
        for pack in coaching.replyPacks
        if len(pack.replies) >= _MIN_REPLIES_PER_PACK
    }
    return _REQUIRED_REPLY_PACK_STYLES.issubset(complete_styles)


def _analysis_failure_message(locale: str) -> str:
    if locale.lower().startswith("ko"):
        return "분석에 실패했습니다. 잠시 후 다시 시도해 주세요."
    return "Analysis failed. Please try again in a moment."
