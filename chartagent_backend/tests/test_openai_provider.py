from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict

from app.config import Settings
from app.errors import AnalysisUnavailableError
from app.providers.openai_api import OpenAIAPIProvider
from app.schemas import AnalysisPayload, TradePlan


class TradePlanEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)
    trade_plan: TradePlan


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

    assert captured["max_output_tokens"] >= 6_500
    assert captured["reasoning"] == {"effort": "minimal"}


@pytest.mark.anyio
async def test_fallback_retries_once_when_trade_plan_entry_geometry_fails_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []
    invalid_plan = {
        "direction_code": "bearish",
        "reference_price": "63,000",
        "entry": "62,000",
        "stop": "63,000",
        "target": "60,000",
        "risk_reward": "1:2",
        "trigger": "Reject the retest before entering short.",
        "rationale": "Wait for confirmation instead of chasing the current price.",
    }
    valid_plan = invalid_plan | {"entry": "64,000", "stop": "65,000", "target": "62,000"}
    outputs = [
        json.dumps({"trade_plan": invalid_plan}),
        TradePlanEnvelope(trade_plan=TradePlan(**valid_plan)).model_dump_json(),
    ]

    class FakeOpenAIError(Exception):
        pass

    class FakeResponses:
        async def create(self, **kwargs: object) -> SimpleNamespace:
            request_input = kwargs["input"]
            prompts.append(request_input[0]["content"][0]["text"])
            return SimpleNamespace(status="completed", output_text=outputs.pop(0))

    class FakeClient:
        def __init__(self, **_: object) -> None:
            self.responses = FakeResponses()

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(AsyncOpenAI=FakeClient, OpenAIError=FakeOpenAIError),
    )

    result = await OpenAIAPIProvider(Settings(openai_api_key="test-key")).complete(
        prompt="Return a bearish trade plan.",
        image_path=None,
        response_model=TradePlanEnvelope,
    )

    assert result.trade_plan.entry == "64,000"
    assert len(prompts) == 2
    assert "bearish entry must be at or above the displayed current price" in prompts[1]
