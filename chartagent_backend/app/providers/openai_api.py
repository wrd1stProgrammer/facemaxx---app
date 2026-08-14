from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.errors import AnalysisUnavailableError
from app.providers.codex_cli import _strict_schema


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class OpenAIAPIProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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
        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        try:
            response = await client.responses.create(
                model=self.settings.openai_model,
                reasoning={"effort": "low"},
                max_output_tokens=2800,
                input=[
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": response_model.__name__,
                        "schema": _strict_schema(response_model),
                        "strict": True,
                    }
                },
            )
            return response_model.model_validate_json(response.output_text or "{}")
        except (OpenAIError, ValidationError, ValueError, json.JSONDecodeError) as error:
            raise AnalysisUnavailableError() from error
