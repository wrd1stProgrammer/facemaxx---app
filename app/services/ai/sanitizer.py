from __future__ import annotations

import re

from app.schemas.analysis import AnalysisResultPayload


PHOTO_RANKING_CHIP_LIMIT = 3

_INTERNAL_TERM_PATTERN = re.compile(
    r"\b(?:face\s*mesh|mesh(?:\s*data)?|wireframe|landmark(?:s| overlay)?|overlay|"
    r"ARKit|Apple\s+Vision|Vision\s+framework|geometry\s+(?:metadata|data)|"
    r"scan\s+payload|scan\s+data|backend\s+data|model\s+fallback|local\s+cache)\b"
    r"|메시|메쉬|오버레이|랜드마크|와이어프레임|기하(?:학)?\s*데이터|"
    r"스캔\s*데이터|백엔드\s*데이터",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?。！？])\s+|\n+")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_KOREAN_PATTERN = re.compile(r"[가-힣]")


def sanitize_analysis_result(result: AnalysisResultPayload) -> AnalysisResultPayload:
    """Clean provider output before it is returned to the app or persisted."""

    result.summary_text = sanitize_user_text(result.summary_text)

    for ring in result.rings:
        ring.display_value = sanitize_user_text(ring.display_value, fallback=ring.display_value) or ring.display_value

    for metric in result.metrics:
        metric.value_text = sanitize_user_text(metric.value_text)
        metric.status_text = sanitize_user_text(metric.status_text)
        metric.detail_text = sanitize_user_text(metric.detail_text)

    for item in result.growth_opportunities:
        item.body_text = sanitize_user_text(item.body_text)

    for ranking in result.photo_rankings:
        ranking.verdict = sanitize_user_text(ranking.verdict)
        ranking.reason_text = sanitize_user_text(ranking.reason_text)
        ranking.description_text = sanitize_user_text(ranking.description_text)
        ranking.best_use_text = sanitize_user_text(ranking.best_use_text)
        ranking.fun_label_text = sanitize_user_text(ranking.fun_label_text)
        ranking.weakness_text = sanitize_user_text(ranking.weakness_text)
        ranking.fix_text = sanitize_user_text(ranking.fix_text)
        ranking.caption_idea_text = sanitize_user_text(ranking.caption_idea_text)
        ranking.strengths, ranking.vibe_tags = _sanitize_photo_chips(
            ranking.strengths,
            ranking.vibe_tags,
        )

    for item in result.coach_items:
        item.assessment_text = sanitize_user_text(item.assessment_text)
        item.action_text = sanitize_user_text(item.action_text)

    if result.look_archetype is not None:
        archetype = result.look_archetype
        archetype.type_name = sanitize_user_text(archetype.type_name, fallback=archetype.type_name) or archetype.type_name
        archetype.secondary_type_name = sanitize_user_text(archetype.secondary_type_name)
        archetype.subtitle_text = sanitize_user_text(archetype.subtitle_text)
        archetype.body_text = sanitize_user_text(archetype.body_text)
        for trait in archetype.traits:
            trait.title_text = sanitize_user_text(trait.title_text)
        for section in archetype.sections:
            section.title_text = sanitize_user_text(section.title_text)
            for bullet in section.bullets:
                bullet.title_text = sanitize_user_text(bullet.title_text)

    return result


def sanitize_user_text(value: str | None, fallback: str | None = None) -> str | None:
    if value is None:
        return None
    text = _WHITESPACE_PATTERN.sub(" ", value).strip()
    if not text:
        return None
    if not _INTERNAL_TERM_PATTERN.search(text):
        return text

    parts = [part.strip() for part in _SENTENCE_SPLIT_PATTERN.split(text) if part.strip()]
    kept = [part for part in parts if not _INTERNAL_TERM_PATTERN.search(part)]
    if kept:
        return " ".join(kept)
    if fallback is not None:
        return fallback
    return _default_photo_fallback(text)


def _sanitize_photo_chips(strengths: list[str], vibe_tags: list[str]) -> tuple[list[str], list[str]]:
    selected_strengths: list[str] = []
    selected_vibes: list[str] = []

    for item in strengths:
        cleaned = _sanitize_chip(item)
        if cleaned is None:
            continue
        selected_strengths.append(cleaned)
        if len(selected_strengths) == PHOTO_RANKING_CHIP_LIMIT:
            break

    remaining = PHOTO_RANKING_CHIP_LIMIT - len(selected_strengths)
    if remaining > 0:
        for item in vibe_tags:
            cleaned = _sanitize_chip(item)
            if cleaned is None:
                continue
            selected_vibes.append(cleaned)
            if len(selected_vibes) == remaining:
                break

    return selected_strengths, selected_vibes


def _sanitize_chip(value: str | None) -> str | None:
    if value is None:
        return None
    text = _WHITESPACE_PATTERN.sub(" ", value).strip()
    if not text or _INTERNAL_TERM_PATTERN.search(text):
        return None
    return text


def _default_photo_fallback(original: str) -> str:
    if _KOREAN_PATTERN.search(original):
        return "원본 사진 기준으로 조명, 각도, 표정, 얼굴 가독성을 다시 확인하는 것이 좋습니다."
    return "Review the original photo for lighting, angle, expression, and face visibility."
