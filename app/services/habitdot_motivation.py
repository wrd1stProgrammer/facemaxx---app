from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from openai import AsyncOpenAI, OpenAIError

from app.core.config import Settings, get_settings
from app.schemas.habitdot import HabitdotMotivationRequest, HabitdotMotivationResponse


class HabitdotMotivationService:
    provider_name = "openai"

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def generate(self, request: HabitdotMotivationRequest) -> HabitdotMotivationResponse:
        generated_at = datetime.now(UTC)
        fallback_text = self._clean_text(self._fallback_text(request), request.locale)

        if not self.settings.openai_api_key:
            return self._response(fallback_text, generated_at)

        try:
            text, model_name = await self._generate_with_openai(request)
        except OpenAIError as exc:
            print("Habitdot OpenAI motivation failed; using fallback:", repr(exc))
            return self._response(fallback_text, generated_at)

        text = self._clean_text(text, request.locale)
        if not text:
            text = fallback_text
            return self._response(text, generated_at)

        return HabitdotMotivationResponse(
            text=text,
            provider=self.provider_name,
            model_name=model_name,
            generated_at=generated_at,
        )

    async def _generate_with_openai(self, request: HabitdotMotivationRequest) -> tuple[str, str]:
        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        model_name = self.settings.openai_model
        prompt = self._prompt(request)
        normalized_model = model_name.lower()
        if normalized_model.startswith("gpt-5") or normalized_model.startswith(("o3", "o4")):
            response = await client.responses.create(
                model=model_name,
                input=prompt,
                max_output_tokens=120,
                reasoning={"effort": "minimal"},
            )
        else:
            response = await client.responses.create(
                model=model_name,
                input=prompt,
                max_output_tokens=120,
            )
        return response.output_text or "", model_name

    def _prompt(self, request: HabitdotMotivationRequest) -> str:
        habits = [
            {
                "title": habit.title,
                "purpose": habit.purpose,
                "completed_today": habit.completed_today,
                "completed_yesterday": habit.completed_yesterday,
                "current_streak": habit.current_streak,
                "weekly_completion_count": habit.weekly_completion_count,
                "recent_7_completed_count": self._recent_completed_count(habit),
                "recent_7_days": [
                    {
                        "date": day.date,
                        "completed": day.completed,
                        "count": day.count,
                    }
                    for day in habit.recent_7_days[-7:]
                ],
            }
            for habit in request.habits
        ]
        context = json.dumps(
            {
                "locale": request.locale,
                "date": request.date,
                "habits": habits,
            },
            ensure_ascii=False,
        )

        if request.locale == "ko":
            return (
                "너는 습관 앱 Habitdot의 짧은 동기부여 문구를 쓰는 코치다.\n"
                "최근 7일 패턴, 어제 완료 여부, 오늘 완료 여부를 우선 보고 한국어 문구 하나만 작성해라.\n"
                "오늘 미완료 습관이 있으면 완료된 습관 축하보다 미완료 습관을 우선하라.\n"
                "어제도 미완료였거나 최근 잘 하다가 오늘 남아있는 습관 1~2개를 고르고, 오늘 할 행동으로 끝내라. 내일 얘기는 하지 마라.\n"
                "'놓쳤다', '못했다', '실패' 같은 부정 표현은 쓰지 말고 '아직 남아있는', '오늘 할 수 있는' 톤으로 말해라.\n"
                "조건: 습관명 1~2개만 자연스럽게 언급, 다음 행동이 분명해야 함, 1줄 우선, 최대 2줄, 마크다운 금지, "
                "따옴표 금지, JSON 금지, 중괄호 금지, text: 같은 키 이름 금지, 32자 이하, 과장 금지, 죄책감 유발 금지.\n"
                f"JSON: {context}"
            )

        return (
            "You write brief motivational copy for the habit app Habitdot.\n"
            "Prioritize recent 7-day patterns, yesterday completion, and today's completion.\n"
            "If any habits are incomplete today, prioritize those over celebrating completed habits.\n"
            "Choose 1-2 habits that are still open today, especially if they were also incomplete yesterday or recently consistent; end with today's next action. Do not talk about tomorrow.\n"
            "Avoid negative wording like missed, failed, or didn't; use a calm still open / can do today tone.\n"
            "Rules: naturally mention only 1-2 habit names, make the next action clear, one or two lines, "
            "no markdown, no quotes, no JSON, no braces, no text: key, under 70 characters, no hype, no guilt.\n"
            f"JSON: {context}"
        )

    def _fallback_text(self, request: HabitdotMotivationRequest) -> str:
        habits = request.habits
        incomplete = [habit for habit in habits if habit.completed_today is not True]
        yesterday_missed = [habit for habit in incomplete if habit.completed_yesterday is False]
        recent_sorted = sorted(habits, key=self._recent_completed_count, reverse=True)

        if request.locale == "en":
            if not habits:
                return "Start tiny today. One clear step is enough."
            if not incomplete:
                title = self._short_title(recent_sorted[0].title, 38)
                return f"{title} is carrying the week. Keep it light today."
            primary = yesterday_missed[0] if yesterday_missed else incomplete[0]
            title = self._short_title(primary.title, 34)
            secondary = next((habit for habit in incomplete if habit.title != primary.title), None)
            if secondary is not None:
                second = self._short_title(secondary.title, 28)
                return f"{title} first, then {second}. Keep it small today."
            return f"{title} is still open today. One small start is enough."

        if not habits:
            return "오늘도 한 걸음이면 충분해요."
        if not incomplete:
            title = self._short_title(recent_sorted[0].title, 12)
            return f"{title} 흐름이 좋아요. 오늘도 가볍게 이어가요."
        primary = yesterday_missed[0] if yesterday_missed else incomplete[0]
        title = self._short_title(primary.title, 12)
        secondary = next((habit for habit in incomplete if habit.title != primary.title), None)
        if secondary is not None:
            second = self._short_title(secondary.title, 10)
            return f"{title}부터, 여유가 있으면 {second}까지."
        return f"{title}, 오늘 한 번만 이어가요."

    @staticmethod
    def _recent_completed_count(habit) -> int:
        return sum(1 for day in habit.recent_7_days if day.completed)

    @staticmethod
    def _short_title(title: str, max_length: int) -> str:
        title = re.sub(r"\s+", " ", title).strip()
        return title[:max_length].rstrip()

    def _response(
        self,
        text: str,
        generated_at: datetime,
    ) -> HabitdotMotivationResponse:
        return HabitdotMotivationResponse(
            text=text,
            provider="fallback",
            model_name=None,
            generated_at=generated_at,
        )

    def _clean_text(self, text: str, locale: str) -> str:
        text = self._extract_plain_text(text)
        lines = [self._clean_line(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        text = "\n".join(lines[:2])
        text = self._strip_wrapping_quotes(text)
        text = self._strip_text_key(text)
        text = re.sub(r"\s+", " ", text).strip()
        limit = 70 if locale == "en" else 32
        return text[:limit].rstrip()

    @staticmethod
    def _extract_plain_text(text: str) -> str:
        candidate = text.strip()
        try:
            parsed = json.loads(candidate)
        except Exception:
            parsed = None

        if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
            return parsed["text"]

        return HabitdotMotivationService._strip_text_key(candidate)

    @staticmethod
    def _strip_text_key(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^\{\s*[\"']?text[\"']?\s*:\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^[\"']?text[\"']?\s*:\s*", "", text, flags=re.IGNORECASE)
        text = text.rstrip("}").strip()
        return text

    @staticmethod
    def _clean_line(line: str) -> str:
        line = line.strip()
        line = re.sub(r"^[\-\*\d\.\)\s]+", "", line)
        line = line.replace("`", "").replace("*", "").replace("#", "")
        line = re.sub(r"[\"'“”‘’「」『』{}]", "", line)
        line = HabitdotMotivationService._strip_text_key(line)
        return HabitdotMotivationService._strip_wrapping_quotes(line)

    @staticmethod
    def _strip_wrapping_quotes(text: str) -> str:
        return text.strip().strip("\"'“”‘’「」『』").strip()
