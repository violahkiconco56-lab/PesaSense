import logging
import os

import httpx

from app.config import settings


logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
BREVO_ACCOUNT_URL = "https://api.brevo.com/v3/account"


def get_api_key() -> str | None:
    return os.getenv("BREVO_API_KEY")


def is_email_configured() -> bool:
    return bool(get_api_key() and settings.EMAIL_FROM)


def check_smtp_connection() -> dict:
    """Check that the Brevo API key works, without sending any mail.

    Returns only non-sensitive information, so it is safe to expose.
    """
    result = {
        "configured": is_email_configured(),
        "api_key_set": bool(get_api_key()),
        "email_from": settings.EMAIL_FROM or None,
        "login_ok": False,
        "error": None,
        "hint": None,
    }

    if not result["configured"]:
        result["error"] = "Email settings are incomplete."
        result["hint"] = "Set BREVO_API_KEY and EMAIL_FROM in the environment."
        return result

    try:
        response = httpx.get(
            BREVO_ACCOUNT_URL,
            headers={"api-key": get_api_key(), "accept": "application/json"},
            timeout=15,
        )
    except Exception as error:
        result["error"] = f"Could not reach Brevo: {type(error).__name__}."
        return result

    if response.status_code == 200:
        result["login_ok"] = True
    else:
        result["error"] = f"Brevo rejected the API key (status {response.status_code})."
        result["hint"] = "Create a new API key in Brevo: SMTP & API -> API Keys."

    return result


def send_verification_email(email: str, username: str, verification_url: str) -> bool:
    if not is_email_configured():
        logger.warning(
            "Verification email not sent: BREVO_API_KEY or EMAIL_FROM is missing."
        )
        return False

    payload = {
        "sender": {"name": "PesaSense-AI", "email": settings.EMAIL_FROM},
        "to": [{"email": email, "name": username}],
        "subject": "Confirm your PesaSense-AI account",
        "textContent": (
            f"Hi {username},\n\n"
            "Confirm your PesaSense-AI account by opening this link:\n"
            f"{verification_url}\n\n"
            "If you did not create this account, you can ignore this email.\n"
        ),
    }

    try:
        response = httpx.post(
            BREVO_SEND_URL,
            json=payload,
            headers={
                "api-key": get_api_key(),
                "accept": "application/json",
                "content-type": "application/json",
            },
            timeout=20,
        )
    except Exception as error:
        logger.error(
            "Verification email not sent for %s: %s", email, type(error).__name__
        )
        return False

    if response.status_code not in (200, 201):
        logger.error(
            "Verification email not sent for %s: Brevo returned %s: %s",
            email,
            response.status_code,
            response.text,
        )
        return False

    logger.info("Verification email sent to %s", email)
    return True