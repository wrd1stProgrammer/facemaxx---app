from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app import main as main_module
from app.schemas import AnalysisPayload, AnalysisResponse, SymbolInfo


def _chart_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (640, 480), color=(4, 18, 26)).save(output, format="PNG")
    return output.getvalue()


def test_analysis_accepts_one_image_without_user_market_fields(
    monkeypatch,
    valid_payload: AnalysisPayload,
) -> None:
    captured: dict[str, object] = {}

    class StubService:
        async def analyze(self, *, context, image_path):
            captured["context"] = context
            captured["image_exists"] = image_path.exists()
            return AnalysisResponse.create(
                provider="codex_cli",
                symbol=SymbolInfo(code="BINANCE:BTCUSDT", name="Bitcoin / Tether", instrument_type="crypto"),
                timeframe="4H",
                included_news=context.include_news,
                result=valid_payload,
                news=[],
            )

    monkeypatch.setattr(main_module, "service", StubService())
    response = TestClient(main_module.app).post(
        "/v1/analyses",
        data={"include_news": "false", "active_agent_ids": "trend,pattern,risk"},
        files={"image": ("chart.png", _chart_png(), "image/png")},
    )

    assert response.status_code == 200, response.text
    assert captured["image_exists"] is True
    assert not hasattr(captured["context"], "symbol_code")
    assert not hasattr(captured["context"], "timeframe")
