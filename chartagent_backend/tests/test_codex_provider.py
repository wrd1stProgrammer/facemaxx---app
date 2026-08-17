from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel, ConfigDict

from app.config import Settings
from app.providers.codex_cli import CodexCLIProvider
from app.schemas import AnalysisPayload


class TinyResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    ok: bool


class FakeProcess:
    pid = 4242
    returncode = 0

    def __init__(self, output: str) -> None:
        self.output = output
        self.input = ""
        self.timeout: float | None = None

    def communicate(self, input: str | None = None, timeout: float | None = None) -> tuple[str, str]:
        self.input = input or ""
        self.timeout = timeout
        return self.output, ""


@pytest.mark.anyio
async def test_codex_is_pinned_to_luna_low_and_does_not_receive_api_keys(tmp_path: Path) -> None:
    output_path = tmp_path / "response.json"
    payload = TinyResponse(ok=True)
    fake = FakeProcess("{}")

    def fake_popen(command: list[str], **kwargs: str) -> FakeProcess:
        destination = Path(command[command.index("-o") + 1])
        destination.write_text(payload.model_dump_json(), encoding="utf-8")
        return fake

    settings = Settings(codex_binary="codex", codex_timeout_seconds=5)
    with patch.dict(os.environ, {"OPENAI_API_KEY": "never-forward", "INSIGHTSENTRY_API_KEY": "never-forward"}), patch(
        "app.providers.codex_cli.subprocess.Popen",
        side_effect=fake_popen,
    ) as popen:
        await CodexCLIProvider(settings).complete(
            prompt="Analyze this chart.",
            image_path=tmp_path / "chart.png",
            response_model=TinyResponse,
        )

    command = popen.call_args.args[0]
    environment = popen.call_args.kwargs["env"]
    assert command[command.index("--model") + 1] == "gpt-5.6-luna"
    assert 'model_reasoning_effort="low"' in command
    assert "--ephemeral" in command
    assert "read-only" in command
    assert "OPENAI_API_KEY" not in environment
    assert "INSIGHTSENTRY_API_KEY" not in environment
    assert "untrusted image" in fake.input
    assert not output_path.exists()


@pytest.mark.anyio
async def test_nonzero_process_exit_is_typed_failure(tmp_path: Path) -> None:
    fake = FakeProcess("")
    fake.returncode = 1
    with patch("app.providers.codex_cli.subprocess.Popen", return_value=fake):
        provider = CodexCLIProvider(Settings(codex_binary="codex", codex_timeout_seconds=5))
        try:
            await provider.complete(
                prompt="Analyze.",
                image_path=tmp_path / "chart.png",
                response_model=TinyResponse,
            )
        except provider.error_type as error:
            assert error.reason == "process_exit"
        else:
            raise AssertionError("Codex process failure was not surfaced")


@pytest.mark.anyio
async def test_full_analysis_uses_a_fifty_second_codex_budget(tmp_path: Path) -> None:
    fake = FakeProcess("{}")
    provider = CodexCLIProvider(Settings(codex_binary="codex", codex_timeout_seconds=55))
    with patch("app.providers.codex_cli.subprocess.Popen", return_value=fake):
        with pytest.raises(provider.error_type):
            await provider.complete(
                prompt="Analyze.",
                image_path=tmp_path / "chart.png",
                response_model=AnalysisPayload,
            )

    assert fake.timeout is not None
    assert fake.timeout == 50
