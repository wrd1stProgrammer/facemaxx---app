from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch

import anyio
import pytest
from pydantic import BaseModel

from app.codex_alerts import CodexFailureAlerts, send_email
from app.config import Settings
from app.providers.codex_cli import CodexCLIError, CodexCLIProvider, _classify_error


def configured():
    return Settings(_env_file=None, alert_smtp_user="sender@gmail.com",
                    alert_smtp_password="test password", alert_email_to="kicoa24@gmail.com")


def test_concurrent_errors_send_once_without_waiting_for_smtp():
    alerts = CodexFailureAlerts()
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def deliver(settings, reason):
        entered.set()
        release.wait(5)
        finished.set()

    with patch("app.codex_alerts.send_email", side_effect=deliver) as send:
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda _: alerts.notify(configured(), CodexCLIError("timeout")), range(20)))
            assert entered.wait(2)
            assert not finished.is_set()
            assert send.call_count == 1
        finally:
            release.set()
            assert finished.wait(2)


def test_missing_password_disables_delivery():
    with patch("app.codex_alerts.send_email") as send:
        CodexFailureAlerts().notify(Settings(_env_file=None), CodexCLIError("timeout"))
        send.assert_not_called()


def test_gmail_transport_and_message():
    with patch("app.codex_alerts.smtplib.SMTP_SSL") as transport:
        send_email(configured(), "not_authenticated")
        smtp = transport.return_value.__enter__.return_value
        smtp.login.assert_called_once_with("sender@gmail.com", "testpassword")
        message = smtp.send_message.call_args.args[0]
        assert message["To"] == "kicoa24@gmail.com"
        assert "not_authenticated" in message.get_content()
        assert "testpassword" not in message.as_string()
        assert transport.call_args.args == ("smtp.gmail.com", 465)


def test_smtp_failure_does_not_escape_or_log_secret(caplog):
    with patch("app.codex_alerts.send_email", side_effect=RuntimeError("secret-password")):
        CodexFailureAlerts._deliver(configured(), "timeout")
    assert "RuntimeError" in caplog.text
    assert "secret-password" not in caplog.text


def test_provider_preserves_error_for_fallback_and_sends_alert():
    class Result(BaseModel):
        ok: bool

    async def run():
        provider = CodexCLIProvider(configured())
        failure = CodexCLIError("not_authenticated")
        with patch.object(provider, "_complete_sync", side_effect=failure), \
             patch("app.providers.codex_cli.codex_failure_alerts.notify") as notify:
            with pytest.raises(CodexCLIError) as caught:
                await provider.complete(prompt="private prompt", image_path=None, response_model=Result)
            assert caught.value is failure
            notify.assert_called_once_with(provider.settings, failure)

    anyio.run(run)


@pytest.mark.parametrize("message", ["refresh_token_reused", "refresh_token_expired", "invalid_grant", "HTTP 401"])
def test_expired_auth_classification(message):
    assert _classify_error(message) == "not_authenticated"
