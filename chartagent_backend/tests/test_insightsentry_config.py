from __future__ import annotations

import pytest

from app.config import Settings


def test_rapidapi_environment_builds_rapidapi_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setenv("INSIGHTSENTRY_RAPIDAPI_KEY", "private-test-key")
    monkeypatch.setenv("INSIGHTSENTRY_RAPIDAPI_HOST", "insightsentry.p.rapidapi.com")

    # When
    settings = Settings(_env_file=None)
    connection = settings.insightsentry_connection

    # Then
    assert connection is not None
    assert connection.base_url == "https://insightsentry.p.rapidapi.com"
    assert dict(connection.headers) == {
        "Accept": "application/json",
        "x-rapidapi-host": "insightsentry.p.rapidapi.com",
        "x-rapidapi-key": "private-test-key",
    }
