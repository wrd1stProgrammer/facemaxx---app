from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, assert_never

from app.schemas.flirtist import FlirtistLanguage, FlirtistPickupLinesRequest, FlirtistPickupLinesResponse
from app.services.flirtist_language_profile import culture_guidance, language_name
from app.services.flirtist_provider_payloads import request_json_for_prompt


@dataclass(frozen=True, slots=True)
class PickupLineContext:
    language: FlirtistLanguage
    situation: str
    hooks: tuple[str, ...]

    @property
    def primary(self) -> str:
        return self.hooks[0]

    @property
    def secondary(self) -> str:
        return self.hooks[1] if len(self.hooks) > 1 else self.hooks[0]

    @property
    def tertiary(self) -> str:
        return self.hooks[2] if len(self.hooks) > 2 else self.secondary


EN_HOOKS: Final[tuple[tuple[str, str], ...]] = (
    ("murakami", "Murakami novel"),
    ("bookstore", "bookstore"), ("book store", "bookstore"),
    ("book", "book"), ("novel", "novel"), ("reading", "reading break"),
    ("cafe", "cafe"), ("coffee", "coffee"),
    ("rain", "rainy afternoon"), ("quiet", "quiet mood"),
    ("museum", "museum"), ("gallery", "gallery"), ("exhibition", "exhibition"),
    ("concert", "concert"), ("bar", "bar"), ("gym", "gym"), ("park", "park"), ("dog", "dog"),
)
KO_HOOKS: Final[tuple[tuple[str, str], ...]] = (
    ("무라카미", "무라카미 소설"),
    ("북카페", "북카페"), ("카페", "카페"),
    ("소설", "소설"), ("책", "책"), ("읽", "읽고 있는 책"),
    ("비", "비 오는 날"), ("조용", "조용한 분위기"),
    ("전시", "전시"), ("공연", "공연"), ("콘서트", "콘서트"),
    ("바", "바"), ("헬스", "헬스장"), ("운동", "운동"), ("공원", "공원"), ("강아지", "강아지"),
)
CLICHE_FRAGMENTS: Final[tuple[str, ...]] = (
    "smooth opener",
    "perfect line",
    "least rehearsed",
    "wanted to meet you",
    "risk a slightly awkward hello",
    "pick a lucky day",
    "phone less interesting",
    "good story",
    "말 걸까 말까",
    "핑계를 찾다가",
    "점수 후하게",
    "연습 중",
    "그냥 지나가기 아쉬",
)


def pickup_lines(language: FlirtistLanguage, situation: str) -> list[str]:
    context = _context(language, situation)
    return _fallback_lines(context)


def curate_pickup_lines(
    lines: list[str],
    language: FlirtistLanguage,
    situation: str,
) -> list[str]:
    context = _context(language, situation)
    curated: list[str] = []
    seen: set[str] = set()
    for line in lines:
        normalized = _clean_line(line)
        key = normalized.casefold()
        if not normalized or key in seen or _is_cliche(normalized):
            continue
        curated.append(normalized)
        seen.add(key)
        if len(curated) == 20:
            return curated
    for line in _fallback_lines(context):
        key = line.casefold()
        if key not in seen:
            curated.append(line)
            seen.add(key)
        if len(curated) == 20:
            return curated
    return curated[:20]


def pickup_lines_prompt(*, request: FlirtistPickupLinesRequest, fallback: FlirtistPickupLinesResponse) -> str:
    language = request.language or _language_from_locale(request.locale)
    return "\n".join(
        [
            "You are Flirtist, a dating-app pickup line writer for consenting adult dating contexts.",
            "Return one JSON object only. No markdown. The JSON must include a lines array with exactly 20 strings.",
            f"Write in {language_name(language)}. {culture_guidance(language)}",
            "Every line must be copy-ready: something the user can send or say directly, not advice.",
            "Use micro-observations from the situation: a place, object, activity, timing, mood, or shared constraint.",
            "At least 12 lines must include a concrete noun or action from the user's situation.",
            "Mix intents: noticing, tiny opinion, recommendation ask, shared-context joke, and low-pressure exit-safe invite.",
            "Avoid generic appearance compliments unless the situation explicitly asks for them.",
            "Banned frames: talking about having a pickup line, being brave, rehearsing, scoring the attempt, fate, destiny, or needing an excuse to talk.",
            "Banned phrases include: smooth opener, perfect line, wanted to meet you, least rehearsed, 말 걸까 말까, 연습 중, 점수 후하게, 핑계.",
            "If language is ko, do not use 당신, do not translate English pickup-line clichés, and do not overuse 혹시.",
            "Each string must be 1-2 short sentences with no numbering, labels, bullets, or meta commentary.",
            "Avoid coercion, harassment, minors, stalking, or sexually explicit pressure.",
            f"Request JSON: {request_json_for_prompt(request)}",
            f"Fallback contract JSON: {fallback.model_dump_json()}",
        ]
    )


def _context(language: FlirtistLanguage, situation: str) -> PickupLineContext:
    cleaned = re.sub(r"\s+", " ", situation.strip()).strip(" .!?")
    match language:
        case "ko":
            hooks = _matched_hooks(cleaned, KO_HOOKS) or (_short_hint(cleaned, "상황"),)
        case "en" | "ja" | "zh-Hant" | "es-MX" | "pt-BR" | "fr" | "de" | "th" | "id":
            hooks = _matched_hooks(cleaned, EN_HOOKS) or (_short_hint(cleaned, "this moment"),)
        case unreachable:
            assert_never(unreachable)
    return PickupLineContext(language=language, situation=cleaned, hooks=hooks[:4])


def _matched_hooks(situation: str, hook_map: tuple[tuple[str, str], ...]) -> tuple[str, ...]:
    lowered = situation.casefold()
    hooks: list[str] = []
    for needle, hook in hook_map:
        if needle.casefold() in lowered and hook not in hooks and not _is_redundant_hook(hook, hooks):
            hooks.append(hook)
    return tuple(hooks)


def _is_redundant_hook(candidate: str, hooks: list[str]) -> bool:
    return any(candidate in hook or hook in candidate for hook in hooks)


def _short_hint(situation: str, fallback: str) -> str:
    if not situation:
        return fallback
    return situation[:42].rstrip()


def _fallback_lines(context: PickupLineContext) -> list[str]:
    match context.language:
        case "ko":
            return _ko_lines(context)
        case "en" | "ja" | "zh-Hant" | "es-MX" | "pt-BR" | "fr" | "de" | "th" | "id":
            return _en_lines(context)
        case unreachable:
            assert_never(unreachable)


def _en_lines(context: PickupLineContext) -> list[str]:
    primary = context.primary
    secondary = context.secondary
    tertiary = context.tertiary
    return [
        f"That {primary} choice made me curious. What pulled you toward it?",
        f"I like the {secondary} energy here. Is this your usual kind of place or a lucky find?",
        f"You picked a very specific {tertiary} moment, so I have to ask what the story is.",
        f"I was trying to respect the {primary} silence, but your taste looked worth one small question.",
        f"If I needed one recommendation from this {secondary}, what would you tell me not to miss?",
        f"This {tertiary} has a calm kind of charm. Do you usually go for places like this?",
        f"I am debating whether the {primary} or your focus is more interesting right now.",
        f"Small question before I disappear back into the room: is the {secondary} as good as it looks?",
        f"The {tertiary} made this feel like a good time for a tiny opinion. Worth it so far?",
        f"You look like you chose the {primary} deliberately, and I respect a deliberate choice.",
        f"I need a second opinion from someone with {secondary} taste: what should I pay attention to here?",
        f"That {tertiary} detail is doing a lot of work. Was that the plan or just good timing?",
        f"I will keep this low-pressure: the {primary} caught my eye, then your reaction did.",
        f"Is this a favorite {secondary}, or did I walk into your first impression too?",
        f"I like when someone makes a {tertiary} look intentional. What are you liking about it?",
        f"If this {primary} had a tiny review, I feel like yours would be better than mine.",
        f"I was about to guess your take on the {secondary}, but asking seems less annoying.",
        f"This may be too specific, but the {tertiary} made me want to say hi properly.",
        f"Before I overthink it, what is the best thing about this {primary} so far?",
        f"If the conversation is not welcome, I can vanish gracefully. The {secondary} just made me curious.",
    ]


def _ko_lines(context: PickupLineContext) -> list[str]:
    primary = context.primary
    secondary = context.secondary
    detail = context.tertiary
    scene = context.hooks[3] if len(context.hooks) > 3 else context.tertiary
    primary_topic = f"{primary}{_topic_particle(primary)}"
    detail_subject = f"{detail}{_subject_particle(detail)}"
    detail_choice = _choice_phrase(detail)
    scene_reason = _scene_reason(scene)
    return [
        f"{primary} 고른 이유가 궁금해졌어요. 이런 취향이면 첫 질문을 조심히 해야 할 것 같아서요.",
        f"{secondary} 분위기랑 너무 잘 맞아서요. 여기 자주 오시는 편이에요?",
        f"지금 {detail_subject} 눈에 들어왔어요. 그거 지금까지 괜찮아요?",
        f"조용히 지나가려다 {primary} 때문에 한 번만 물어보고 싶어졌어요.",
        f"여기서 하나만 추천받는다면 {secondary} 기준으로 뭐가 제일 괜찮아요?",
        f"{scene}에는 말도 좀 천천히 걸어야 할 것 같네요. 잠깐 괜찮으세요?",
        f"{primary} 취향이면 다른 것도 잘 고르실 것 같아서요. 메뉴 하나만 추천해주실래요?",
        f"저도 {secondary} 좋아하는데, 오늘은 그쪽 선택이 더 좋아 보여요.",
        f"{scene_reason} 분위기가 좋아서요. 방해 아니면 한마디만 해도 될까요?",
        f"그 {primary} 선택이 너무 구체적이라 그냥 지나치기 어렵네요.",
        f"혹시 {secondary} 처음 오신 거예요, 아니면 이미 잘 아는 곳이에요?",
        f"{detail_choice}이면 어떤 대답을 할지 궁금해졌어요.",
        f"부담 없이 하나만 물어볼게요. {primary_topic} 원래 좋아하시는 편이에요?",
        f"이 {secondary}에서 제일 괜찮은 포인트를 고르면 뭐예요?",
        f"지금 {scene_reason} 말 걸 타이밍을 오래 고르진 않았어요.",
        f"혹시 추천 하나만 받을 수 있을까요? {primary} 고른 사람 추천이면 믿어도 될 것 같아서요.",
        f"저는 아직 이 {secondary} 분위기 파악 중인데, 이미 잘 즐기고 계신 것 같아요.",
        f"{detail} 얘기로 시작하면 덜 어색할 것 같아서요. 지금 장면 어디쯤이에요?",
        f"딱 짧게만요. {primary} 보고 계신 표정이 좋아 보여서 궁금했습니다.",
        f"대화가 불편하면 바로 물러날게요. {secondary} 취향이 좋아 보여서 인사하고 싶었어요.",
    ]


def _choice_phrase(text: str) -> str:
    if text == "읽고 있는 책":
        return "책 고르는 취향"
    return f"{text} 취향"


def _scene_reason(text: str) -> str:
    if text.endswith("날"):
        return f"{text}이라"
    return f"{text} 덕분에"


def _subject_particle(text: str) -> str:
    last = text[-1]
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 > 0:
        return "이"
    return "가"


def _topic_particle(text: str) -> str:
    last = text[-1]
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 > 0:
        return "은"
    return "는"


def _clean_line(line: str) -> str:
    trimmed = re.sub(r"\s+", " ", line).strip()
    return re.sub(r"^\s*(?:\d+[\).\s-]+|[-*]\s+)", "", trimmed)


def _is_cliche(line: str) -> bool:
    lowered = line.casefold()
    return any(fragment.casefold() in lowered for fragment in CLICHE_FRAGMENTS)


def _language_from_locale(locale: str) -> FlirtistLanguage:
    lowered = locale.strip().lower()
    if lowered.startswith("ko"):
        return "ko"
    if lowered.startswith("ja"):
        return "ja"
    if lowered.startswith("zh"):
        return "zh-Hant"
    if lowered.startswith("es"):
        return "es-MX"
    if lowered.startswith("pt-br") or lowered.startswith("pt_br"):
        return "pt-BR"
    if lowered.startswith("fr"):
        return "fr"
    if lowered.startswith("de"):
        return "de"
    if lowered.startswith("th"):
        return "th"
    if lowered.startswith("id") or lowered.startswith("in"):
        return "id"
    return "en"
