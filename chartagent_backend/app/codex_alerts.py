from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
import logging
import smtplib
import ssl
import threading
import time

from app.config import Settings, get_settings


LOGGER = logging.getLogger(__name__)


def send_email(settings: Settings, reason: str, *, test: bool = False) -> None:
    if not settings.alert_smtp_user or not settings.alert_smtp_password:
        raise ValueError("Set CHARTAGENT_ALERT_SMTP_USER and CHARTAGENT_ALERT_SMTP_PASSWORD")
    message = EmailMessage()
    message["From"] = settings.alert_smtp_user
    message["To"] = settings.alert_email_to
    message["Subject"] = "[ChartAgent] " + ("Email alert test" if test else "Codex provider failure")
    message.set_content(
        f"Environment: {settings.app_env}\n"
        f"Time (UTC): {datetime.now(timezone.utc).isoformat()}\n"
        f"Reason: {reason}\n\n"
        "A Codex failure triggers the existing OpenAI API fallback. "
        "This notification does not confirm that the fallback succeeded.\n"
        "For authentication errors, check the server's Codex login.\n"
        "No prompts, chart images, tokens, or raw error output are included.\n"
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10, context=ssl.create_default_context()) as smtp:
        smtp.login(settings.alert_smtp_user, settings.alert_smtp_password.get_secret_value().replace(" ", ""))
        smtp.send_message(message)


class CodexFailureAlerts:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def notify(self, settings: Settings, error: Exception) -> None:
        if not settings.alert_smtp_user or not settings.alert_smtp_password:
            return
        # One shared gate bounds threads and mail across all Codex provider instances.
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed:
                return
            self._next_allowed = now + settings.alert_cooldown_seconds
        reason = getattr(error, "reason", "unexpected_error")
        if reason not in {"not_authenticated", "timeout", "rate_limited", "model_unavailable",
                          "process_exit", "invalid_response", "not_started", "capacity_exhausted"}:
            reason = "unexpected_error"
        try:
            threading.Thread(target=self._deliver, args=(settings, reason), daemon=True,
                             name="codex-email-alert").start()
        except Exception as delivery_error:
            LOGGER.warning("Codex email could not start: %s", type(delivery_error).__name__)

    @staticmethod
    def _deliver(settings: Settings, reason: str) -> None:
        try:
            send_email(settings, reason)
            LOGGER.info("Codex failure email sent")
        except Exception as error:
            # Keep the cooldown even on SMTP failure; never log credentials or SMTP replies.
            LOGGER.warning("Codex email delivery failed: %s", type(error).__name__)


codex_failure_alerts = CodexFailureAlerts()


if __name__ == "__main__":
    try:
        send_email(get_settings(), "manual_test", test=True)
    except Exception as error:
        print(f"Email test failed ({type(error).__name__}); check SMTP settings and server logs.")
        raise SystemExit(1)
    print("Test email accepted by Gmail SMTP. Check the recipient inbox/spam folder.")
