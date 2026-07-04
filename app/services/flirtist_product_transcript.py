from __future__ import annotations

import re
from typing import Final

from app.schemas.flirtist import FlirtistLanguage
from app.schemas.flirtist_product import FlirtistPreviewMessage


_PUNCTUATION_ONLY: Final[re.Pattern[str]] = re.compile(r"^[\W_]+$")
_TIME_ONLY: Final[re.Pattern[str]] = re.compile(r"^\d{1,2}:\d{2}$")
_STATUS_CHROME: Final[re.Pattern[str]] = re.compile(
    r"^(?:lte|5g|4g|3g|wifi|wi-fi|vpn|no service|carrier|battery|skt|kt|lgu|u\+|\d{1,3}%|\d{1,4}\+?)$",
    re.IGNORECASE,
)
_DATE_CHROME: Final[re.Pattern[str]] = re.compile(
    r"^(?:mon|tue|wed|thu|fri|sat|sun)(?:day)?[,.\s-]+\w+|\d{4}[./-]\d{1,2}[./-]\d{1,2}$",
    re.IGNORECASE,
)
_MESSAGE_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(
    r"^(?:message|messages|enter a message|메시지|메세지|입력|채팅|write a message|type a message|send a message|reply)\s*[.….\-_:]*$",
    re.IGNORECASE,
)
_UI_PHRASES: Final[tuple[str, ...]] = (
    "ai 추천 답장",
    "ai coach is extracting",
    "hidden chemistry",
    "interest signal",
    "analyzing their true feelings",
    "reading the screenshot",
    "reading the chat",
    "finding the next best reply",
    "finding the next reply",
    "finding real signals",
    "get nsfw reply",
    "generated rizz",
    "unlock infinite rizz",
    "집중할 키워드",
    "스크린샷 스캔 중",
    "대화 읽는 중",
    "상대방의 속마음",
    "숨겨진 호감",
    "진짜 신호",
    "답장 흐름",
    "flirtcue",
    "flirtist",
    "app store",
)


def preview_messages(language: FlirtistLanguage, text: str | None) -> list[FlirtistPreviewMessage]:
    cleaned_text = sanitized_transcript_text(text)
    if not cleaned_text:
        return [
            FlirtistPreviewMessage(role="system", text="Screenshot uploaded" if language == "en" else "스크린샷 업로드됨")
        ]

    messages: list[FlirtistPreviewMessage] = []
    for raw_line in cleaned_text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith(("me:", "나:", "저:")):
            messages.append(FlirtistPreviewMessage(role="me", text=line.split(":", 1)[1].strip()))
        elif lowered.startswith(("them:", "상대:", "그쪽:")):
            messages.append(FlirtistPreviewMessage(role="them", text=line.split(":", 1)[1].strip()))
        else:
            messages.append(FlirtistPreviewMessage(role="them", text=line))
    return messages or [FlirtistPreviewMessage(role="system", text=cleaned_text[:500])]


def clean_preview_messages(
    language: FlirtistLanguage,
    messages: list[FlirtistPreviewMessage],
) -> list[FlirtistPreviewMessage]:
    cleaned = [message for message in messages if not is_ui_noise_text(message.text)]
    if cleaned:
        return cleaned
    return [
        FlirtistPreviewMessage(role="system", text="Screenshot uploaded" if language == "en" else "스크린샷 업로드됨")
    ]


def sanitized_transcript_text(text: str | None) -> str | None:
    if text is None:
        return None
    lines = [_clean_line(line) for line in text.splitlines()]
    kept = [line for line in lines if line and not is_ui_noise_text(line)]
    if not kept:
        return None
    return "\n".join(kept)


def is_ui_noise_text(text: str) -> bool:
    compact = " ".join(text.split()).strip()
    if not compact:
        return True
    lowered = compact.lower()
    role_text = _without_role_prefix(lowered)
    if _MESSAGE_PLACEHOLDER.fullmatch(role_text):
        return True
    if _TIME_ONLY.fullmatch(role_text):
        return True
    if _STATUS_CHROME.fullmatch(role_text):
        return True
    if _DATE_CHROME.match(role_text):
        return True
    if len(role_text) <= 8 and _PUNCTUATION_ONLY.fullmatch(role_text):
        return True
    return any(phrase in lowered for phrase in _UI_PHRASES)


def _clean_line(line: str) -> str:
    return " ".join(line.replace("\n", " ").split()).strip()


def _without_role_prefix(text: str) -> str:
    for prefix in ("me:", "them:", "나:", "저:", "상대:", "그쪽:"):
        if text.startswith(prefix):
            return text.split(":", 1)[1].strip()
    return text
