from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ReplyScenario = Literal["celebration", "fatigue", "plans", "affection", "reaction", "generic"]


@dataclass(frozen=True, slots=True)
class ReplyContext:
    scenario: ReplyScenario
    topic: str
    last_them: str


def focus_or_topic(topic: str, focus: str | None) -> str:
    clipped = " ".join((focus or "").split())[:28]
    return clipped or topic
