from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime

from app.core.config import Settings, get_settings
from app.schemas.habitdot import HabitdotMotivationRequest, HabitdotMotivationResponse


class HabitdotMotivationService:
    provider_name = "gemini"
    transient_status_codes = {429, 500, 502, 503, 504}

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def generate(self, request: HabitdotMotivationRequest) -> HabitdotMotivationResponse:
        generated_at = datetime.now(UTC)
        fallback_text = self._fallback_text(request)

        if not self.settings.gemini_api_key:
            return self._response(fallback_text, generated_at)

        try:
            text, model_name = await self._generate_with_gemini(request)
        except Exception as exc:
            print("Habitdot Gemini motivation failed; using fallback:", repr(exc))
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

    async def _generate_with_gemini(self, request: HabitdotMotivationRequest) -> tuple[str, str]:
        from google import genai
        from google.genai import types

        previous_google_api_key = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            client = genai.Client(api_key=self.settings.gemini_api_key)
        finally:
            if previous_google_api_key is not None:
                os.environ["GOOGLE_API_KEY"] = previous_google_api_key

        config = types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=80,
        )
        response, model_name = await self._generate_content_with_fallback(
            client=client,
            contents=[self._prompt(request)],
            config=config,
        )
        return response.text or "", model_name

    async def _generate_content_with_fallback(self, client, contents: list[str], config):
        attempts_per_model = max(1, self.settings.gemini_retry_attempts)
        model_candidates = self.settings.gemini_model_candidates or [self.settings.gemini_model]
        last_exc: Exception | None = None

        for model_index, model_name in enumerate(model_candidates):
            for attempt_index in range(attempts_per_model):
                try:
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    return response, model_name
                except Exception as exc:
                    last_exc = exc
                    is_transient = self._is_transient_model_error(exc)
                    has_more_attempts = attempt_index < attempts_per_model - 1
                    has_fallback_model = model_index < len(model_candidates) - 1
                    if not is_transient or (not has_more_attempts and not has_fallback_model):
                        raise

                    delay = self._retry_delay_seconds(attempt_index, model_index)
                    await asyncio.sleep(delay)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No Gemini model candidates configured")

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
                "조건: 습관명 1~2개만 자연스럽게 언급, 다음 행동이 분명해야 함, 1~2줄, 마크다운 금지, "
                "따옴표 금지, 100자 이하, 과장 금지, 죄책감 유발 금지.\n"
                f"JSON: {context}"
            )

        return (
            "You write brief motivational copy for the habit app Habitdot.\n"
            "Prioritize recent 7-day patterns, yesterday completion, and today's completion.\n"
            "If any habits are incomplete today, prioritize those over celebrating completed habits.\n"
            "Choose 1-2 habits that are still open today, especially if they were also incomplete yesterday or recently consistent; end with today's next action. Do not talk about tomorrow.\n"
            "Avoid negative wording like missed, failed, or didn't; use a calm still open / can do today tone.\n"
            "Rules: naturally mention only 1-2 habit names, make the next action clear, one or two lines, "
            "no markdown, no quotes, under 140 characters, no hype, no guilt.\n"
            f"JSON: {context}"
        )

    def _fallback_text(self, request: HabitdotMotivationRequest) -> str:
        habits = request.habits
        incomplete = [habit for habit in habits if habit.completed_today is not True]
        yesterday_missed = [habit for habit in incomplete if habit.completed_yesterday is False]
        recent_sorted = sorted(habits, key=self._recent_completed_count, reverse=True)

        if request.locale == "en":
            if not habits:
                return "No habit needs to be huge today.\nStart small and keep the promise."
            if not incomplete:
                title = self._short_title(recent_sorted[0].title, 38)
                return f"{title} is already carrying the week.\nLet today's finish count."
            primary = yesterday_missed[0] if yesterday_missed else incomplete[0]
            title = self._short_title(primary.title, 34)
            secondary = next((habit for habit in incomplete if habit.title != primary.title), None)
            if secondary is not None:
                second = self._short_title(secondary.title, 28)
                return f"{title} first, then {second} if there is room.\nKeep today's step small."
            return f"{title} is still open today.\nOne small start is enough."

        if not habits:
            return "오늘도 한 걸음이면 충분해요.\n작게 시작하고 끝까지 가봐요."
        if not incomplete:
            title = self._short_title(recent_sorted[0].title, 16)
            return f"{title} 흐름이 이번 주를 잘 받쳐주고 있어요.\n오늘도 충분히 쌓았습니다."
        primary = yesterday_missed[0] if yesterday_missed else incomplete[0]
        title = self._short_title(primary.title, 16)
        secondary = next((habit for habit in incomplete if habit.title != primary.title), None)
        if secondary is not None:
            second = self._short_title(secondary.title, 14)
            return f"{title}부터 작게 시작하고, 여유가 있으면 {second}까지.\n오늘은 한 번이면 충분해요."
        return f"어제도 남아있던 {title}, 오늘은 한 번만 이어가요.\n작게 해도 흐름은 돌아옵니다."

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
        lines = [self._clean_line(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        text = "\n".join(lines[:2])
        text = self._strip_wrapping_quotes(text)
        limit = 140 if locale == "en" else 100
        return text[:limit].rstrip()

    @staticmethod
    def _clean_line(line: str) -> str:
        line = line.strip()
        line = re.sub(r"^[\-\*\d\.\)\s]+", "", line)
        line = line.replace("`", "").replace("*", "").replace("#", "")
        line = re.sub(r"[\"'“”‘’「」『』]", "", line)
        return HabitdotMotivationService._strip_wrapping_quotes(line)

    @staticmethod
    def _strip_wrapping_quotes(text: str) -> str:
        return text.strip().strip("\"'“”‘’「」『』").strip()

    @classmethod
    def _is_transient_model_error(cls, exc: Exception) -> bool:
        status_code = cls._exception_status_code(exc)
        if status_code in cls.transient_status_codes:
            return True

        text = str(exc).lower()
        transient_markers = (
            "unavailable",
            "high demand",
            "temporarily",
            "resource_exhausted",
            "deadline",
            "timeout",
            "rate limit",
        )
        return any(marker in text for marker in transient_markers)

    @staticmethod
    def _exception_status_code(exc: Exception) -> int | None:
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        try:
            return int(status_code) if status_code is not None else None
        except (TypeError, ValueError):
            return None

    def _retry_delay_seconds(self, attempt_index: int, model_index: int) -> float:
        base_delay = max(0.1, self.settings.gemini_retry_base_delay_seconds)
        return round(base_delay * (2 ** attempt_index) + (0.25 * model_index), 2)
