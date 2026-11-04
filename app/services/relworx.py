import httpx

from app.config import settings


BASE_URL = "https://payments.relworx.com/api/mobile-money"


class RelworxError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        may_have_succeeded: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.may_have_succeeded = may_have_succeeded


def ensure_relworx_configured() -> None:
    if not settings.RELWORX_API_KEY or not settings.RELWORX_ACCOUNT_NO:
        raise RelworxError(
            "Mobile Money payments are temporarily unavailable.",
            status_code=503,
        )
    if settings.PREMIUM_PRICE_UGX < 500:
        raise RelworxError(
            "The Premium price is below Relworx's minimum payment amount.",
            status_code=503,
        )


def _headers() -> dict[str, str]:
    ensure_relworx_configured()
    return {
        "Content-Type": "application/json",
        "Accept": "application/vnd.relworx.v2",
        "Authorization": f"Bearer {settings.RELWORX_API_KEY}",
    }


def request_payment(
    *,
    reference: str,
    msisdn: str,
    amount: int,
    description: str,
) -> dict:
    try:
        response = httpx.post(
            f"{BASE_URL}/request-payment",
            headers=_headers(),
            json={
                "account_no": settings.RELWORX_ACCOUNT_NO,
                "reference": reference,
                "msisdn": msisdn,
                "currency": "UGX",
                "amount": amount,
                "description": description,
            },
            timeout=settings.RELWORX_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        raise RelworxError(
            "Relworx did not respond before the request timed out.",
            may_have_succeeded=True,
        ) from exc
    except httpx.RequestError as exc:
        raise RelworxError(
            "Relworx could not be reached.",
            may_have_succeeded=True,
        ) from exc

    if response.status_code == 429:
        raise RelworxError(
            "Relworx rate limit reached.",
            status_code=429,
        )
    if response.is_error:
        raise RelworxError(
            "Relworx rejected the payment request.",
            status_code=response.status_code,
            may_have_succeeded=response.status_code >= 500,
        )

    try:
        result = response.json()
    except ValueError as exc:
        raise RelworxError(
            "Relworx returned an unreadable payment response.",
            may_have_succeeded=True,
        ) from exc

    if not isinstance(result, dict):
        raise RelworxError(
            "Relworx returned an unreadable payment response.",
            may_have_succeeded=True,
        )
    if result.get("success") is not True:
        raise RelworxError("Relworx did not accept the payment request.")
    if not isinstance(result.get("internal_reference"), str):
        raise RelworxError(
            "Relworx did not return a payment reference.",
            may_have_succeeded=True,
        )
    return result


def check_request_status(internal_reference: str) -> dict:
    try:
        response = httpx.get(
            f"{BASE_URL}/check-request-status",
            headers=_headers(),
            params={
                "internal_reference": internal_reference,
                "account_no": settings.RELWORX_ACCOUNT_NO,
            },
            timeout=settings.RELWORX_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        raise RelworxError("Relworx status check timed out.") from exc
    except httpx.RequestError as exc:
        raise RelworxError("Relworx could not be reached for a status check.") from exc

    if response.is_error:
        raise RelworxError(
            "Relworx could not confirm the payment status.",
            status_code=response.status_code,
        )
    try:
        result = response.json()
    except ValueError as exc:
        raise RelworxError("Relworx returned an unreadable status response.") from exc
    if not isinstance(result, dict) or result.get("success") is not True:
        raise RelworxError("Relworx could not confirm the payment status.")
    return result
