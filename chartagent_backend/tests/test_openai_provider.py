from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.errors import AnalysisUnavailableError
from app.providers.openai_api import OpenAIAPIProvider
from app.schemas import AnalysisPayload


@pytest.mark.anyio
async def test_fallback_reserves_enough_output_for_a_full_five_agent_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    class FakeOpenAIError(Exception):
        pass

    class FakeResponses:
        async def create(self, **kwargs: object) -> None:
            captured.update(kwargs)
            raise FakeOpenAIError("stop after request capture")

    class FakeClient:
        def __init__(self, **_: object) -> None:
            self.responses = FakeResponses()

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(AsyncOpenAI=FakeClient, OpenAIError=FakeOpenAIError),
    )
    provider = OpenAIAPIProvider(Settings(openai_api_key="test-key"))
    image = tmp_path / "chart.jpg"
    image.write_bytes(b"image")

    with pytest.raises(AnalysisUnavailableError):
        await provider.complete(prompt="analyze", image_path=image, response_model=AnalysisPayload)

    assert captured["max_output_tokens"] >= 5_000
