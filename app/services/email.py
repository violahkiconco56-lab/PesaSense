from email.message import EmailMessage
import logging
import smtplib

from app.config import settings


logger = logging.getLogger(__name__)


def is_email_configured() -> bool:
    return all([
        settings.SMTP_HOST,
        settings.SMTP_USERNAME,
        settings.SMTP_PASSWORD,
        settings.EMAIL_FROM,
    ])


def check_smtp_connection() -> dict:
    """Diagnose SMTP readiness without sending any mail.

    Returns only non-sensitive information (host, port, boolean flags and an
    error label) so it is safe to expose through a diagnostic endpoint. The
    username/password values themselves are never included.
    """
    result = {
        "configured": is_email_configured(),
        "host": settings.SMTP_HOST or None,
        "port": settings.SMTP_PORT,
        "username_set": bool(settings.SMTP_USERNAME),
        "password_set": bool(settings.SMTP_PASSWORD),
        "password_length": len(settings.SMTP_PASSWORD or ""),
        "email_from": settings.EMAIL_FROM or None,
        "login_ok": False,
        "error": None,
        "hint": None,
    }

    if not result["configured"]:
        result["error"] = "SMTP settings are incomplete in .env."
        result["hint"] = (
            "Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD and EMAIL_FROM."
        )
        return result

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
    except smtplib.SMTPAuthenticationError:
        result["error"] = "SMTP authentication failed."
        result["hint"] = (
            "SMTP_USERNAME must be your provider account login (Brevo: your Brevo "
            "account email, not the sender name), and SMTP_PASSWORD must be the "
            "provider's SMTP key (Brevo: SMTP & API -> SMTP tab), not an API key."
        )
    except Exception as error:
        result["error"] = f"SMTP connection failed: {type(error).__name__}."
        result["hint"] = (
            "Check the host, port and your network/firewall. Brevo uses "
            "smtp-relay.brevo.com on port 587."
        )
    else:
        result["login_ok"] = True

    return result


def send_verification_email(email: str, username: str, verification_url: str) -> bool:
    if not is_email_configured():
        logger.warning(
            "Verification email not sent: SMTP settings are incomplete in .env."
        )
        return False

    message = EmailMessage()
    message["Subject"] = "Confirm your PesaSense-AI account"
    message["From"] = settings.EMAIL_FROM
    message["To"] = email
    message.set_content(
        f"Hi {username},\n\n"
        "Confirm your PesaSense-AI account by opening this link:\n"
        f"{verification_url}\n\n"
        "If you did not create this account, you can ignore this email.\n"
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError as error:
        # e.g. Brevo: "535 Authentication failed" means SMTP_PASSWORD is not the
        # SMTP key (an API key or account password will be rejected here).
        logger.error(
            "Verification email not sent for %s: SMTP authentication failed (%s). "
            "Check SMTP_USERNAME and SMTP_PASSWORD (use the provider's SMTP key).",
            email,
            error.smtp_code,
        )
        return False
    except Exception as error:
        logger.error(
            "Verification email not sent for %s: %s",
            email,
            type(error).__name__,
        )
        return False

    logger.info("Verification email sent to %s", email)
    return True
