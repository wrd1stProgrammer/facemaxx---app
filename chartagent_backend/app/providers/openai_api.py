from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.errors import AnalysisUnavailableError
from app.providers.codex_cli import _strict_schema


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
LOGGER = logging.getLogger(__name__)


class OpenAIAPIProvider:
    def __init__(self, settings: Settings, *, model: str | None = None,
                 reasoning_effort: Literal["minimal", "low", "medium"] = "minimal",
                 timeout_seconds: float = 55.0, max_attempts: int = 2) -> None:
        self.settings = settings
        self.model = model or settings.openai_model
        self.reasoning_effort = reasoning_effort
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts

    async def complete(
        self,
        *,
        prompt: str,
        image_path: Path | None,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        if not self.settings.openai_api_key:
            raise AnalysisUnavailableError()
        from openai import AsyncOpenAI, OpenAIError

        content: list[dict[str, str]] = [{"type": "input_text", "text": prompt}]
        if image_path is not None:
            image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
            suffix = image_path.suffix.lower()
            media_type = {".png": "image/png", ".webp": "image/webp"}.get(suffix, "image/jpeg")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{media_type};base64,{image_data}",
                    "detail": "high",
                }
            )
        # Codex is attempted first. Keep the fallback inside a bounded wall-clock
        # window so the reverse proxy can always return a structured API error
        # instead of closing the request with an HTML gateway response.
        client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.timeout_seconds,
            max_retries=0,
        )
        try:
            for attempt in range(self.max_attempts):
                response = await client.responses.create(
                    model=self.model,
                    # Preserve the token budget for the schema-constrained report;
                    # the five specialist perspectives already provide deliberation.
                    reasoning={"effort": self.reasoning_effort},
                    # Five opinions, council dialogue, scenarios, structure, and a
                    # trade plan no longer fit reliably inside the original 2,800
                    # token cap. This is an output ceiling, not reserved usage.
                    max_output_tokens=7000,
                    input=[{"role": "user", "content": content}],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": response_model.__name__,
                            "schema": _strict_schema(response_model),
                            "strict": True,
                        }
                    },
                )
                output_text = response.output_text or ""
                if getattr(response, "status", None) == "incomplete" or not output_text:
                    incomplete = getattr(response, "incomplete_details", None)
                    LOGGER.warning(
                        "OpenAI fallback incomplete response_model=%s status=%s reason=%s output_chars=%s",
                        response_model.__name__,
                        getattr(response, "status", "unknown"),
                        getattr(incomplete, "reason", "unknown"),
                        len(output_text),
                    )
                    raise AnalysisUnavailableError()
                try:
                    return response_model.model_validate_json(output_text)
                except ValidationError as error:
                    if attempt + 1 >= self.max_attempts:
                        raise
                    feedback = _validation_feedback(error)
                    LOGGER.warning(
                        "OpenAI fallback validation failed; retrying response_model=%s errors=%s",
                        response_model.__name__,
                        feedback,
                    )
                    content[0] = {
                        "type": "input_text",
                        "text": f"{prompt}\n\nThe previous response failed validation. Recalculate the full response and correct these issues: {feedback}",
                    }
            raise AnalysisUnavailableError()
        except AnalysisUnavailableError:
            raise
        except (OpenAIError, ValidationError, ValueError, json.JSONDecodeError) as error:
            LOGGER.warning(
                "OpenAI fallback failed response_model=%s reason=%s",
                response_model.__name__,
                type(error).__name__,
            )
            raise AnalysisUnavailableError() from error


def _validation_feedback(error: ValidationError) -> str:
    issues: list[str] = []
    for issue in error.errors(include_url=False, include_input=False)[:6]:
        location = ".".join(str(part) for part in issue["loc"]) or "response"
        issues.append(f"{location}: {issue['msg']}")
    return "; ".join(issues)
