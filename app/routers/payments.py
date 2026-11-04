import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import (
    PaymentResponse,
    PremiumPriceResponse,
    PremiumPaymentRequest,
    RelworxWebhook,
)
from app.services.auth import get_current_user
from app.services.payment_status import (
    PaymentStatusMismatch,
    reconcile_payment_status,
)
from app.services.relworx import (
    RelworxError,
    check_request_status,
    ensure_relworx_configured,
    request_payment,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["Payments"])
PENDING_MESSAGE = "Check your phone and approve the payment."


def _to_response(
    payment: Payment,
    user: User | None,
    message: str,
) -> PaymentResponse:
    return PaymentResponse(
        reference=payment.reference,
        plan="premium",
        amount=float(payment.amount),
        currency=payment.currency,
        status=payment.status,
        message=message,
        current_period_end=user.current_period_end if user else None,
    )


def _refresh_payment(
    db: Session,
    payment: Payment,
    *,
    fallback_internal_reference: str | None = None,
) -> Payment:
    if payment.status != "pending":
        return payment
    internal_reference = payment.internal_reference or fallback_internal_reference
    if not internal_reference:
        return payment
    result = check_request_status(internal_reference)
    return reconcile_payment_status(db, payment, internal_reference, result)


@router.get("/premium/price", response_model=PremiumPriceResponse)
def get_premium_price(
    current_user: User = Depends(get_current_user),
):
    return PremiumPriceResponse(amount=settings.PREMIUM_PRICE_UGX, currency="UGX")


@router.post(
    "/webhook",
    include_in_schema=True,
)
def relworx_webhook(
    payload: RelworxWebhook,
    db: Session = Depends(get_db),
):
    # Relworx cannot send the app's user JWT; its payload is only a signal.
    payment = None
    if payload.customer_reference:
        payment = (
            db.query(Payment)
            .filter(Payment.reference == payload.customer_reference)
            .first()
        )
    if payment is None and payload.internal_reference:
        payment = (
            db.query(Payment)
            .filter(Payment.internal_reference == payload.internal_reference)
            .first()
        )
    if payment is None or payment.status != "pending":
        return {"received": True}
    if (
        payment.internal_reference
        and payload.internal_reference
        and payment.internal_reference != payload.internal_reference
    ):
        logger.warning(
            "Ignored Relworx webhook with mismatched references",
            extra={"payment_id": payment.id},
        )
        return {"received": True}

    try:
        _refresh_payment(
            db,
            payment,
            fallback_internal_reference=payload.internal_reference,
        )
    except RelworxError as exc:
        logger.warning(
            "Relworx webhook status confirmation failed",
            extra={"payment_id": payment.id, "provider_status": exc.status_code},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment status could not be confirmed yet.",
        ) from exc
    except PaymentStatusMismatch as exc:
        logger.error(
            "Relworx webhook status did not match the payment",
            extra={"payment_id": payment.id},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment status could not be confirmed.",
        ) from exc
    return {"received": True}


@router.post(
    "/premium",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_premium_payment(
    request: PremiumPaymentRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ensure_relworx_configured()
    except RelworxError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    payment = Payment(
        user_id=current_user.id,
        plan="premium",
        amount=settings.PREMIUM_PRICE_UGX,
        currency="UGX",
        msisdn=request.msisdn,
        reference=secrets.token_hex(16),
        status="pending",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    logger.info(
        "Premium payment request created",
        extra={"payment_id": payment.id, "user_id": current_user.id},
    )

    try:
        result = request_payment(
            reference=payment.reference,
            msisdn=payment.msisdn,
            amount=settings.PREMIUM_PRICE_UGX,
            description="PesaSense-AI Premium subscription",
        )
    except RelworxError as exc:
        if not exc.may_have_succeeded:
            payment.status = "failed"
            db.commit()
            logger.warning(
                "Relworx rejected a premium payment request",
                extra={
                    "payment_id": payment.id,
                    "user_id": current_user.id,
                    "provider_status": exc.status_code,
                },
            )
            if exc.status_code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many payment requests for this number. Wait 10 minutes before trying again.",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="We could not start the payment. Check the number and try again.",
            ) from exc
        response.status_code = status.HTTP_202_ACCEPTED
        logger.warning(
            "Relworx payment request outcome is uncertain",
            extra={"payment_id": payment.id, "user_id": current_user.id},
        )
        return _to_response(
            payment,
            current_user,
            "We could not confirm whether the request reached Relworx. Check your phone; do not retry immediately.",
        )

    payment.internal_reference = result["internal_reference"]
    db.commit()
    db.refresh(payment)
    return _to_response(payment, current_user, PENDING_MESSAGE)


@router.get("/{reference}", response_model=PaymentResponse)
def get_payment_status(
    reference: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .filter(
            Payment.reference == reference,
            Payment.user_id == current_user.id,
        )
        .first()
    )
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )
    if payment.status == "pending":
        try:
            payment = _refresh_payment(db, payment)
        except RelworxError as exc:
            logger.warning(
                "Relworx payment status check failed",
                extra={
                    "payment_id": payment.id,
                    "user_id": current_user.id,
                    "provider_status": exc.status_code,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="We could not check the payment status yet. Please try again shortly.",
            ) from exc
        except PaymentStatusMismatch as exc:
            logger.error(
                "Relworx status did not match the payment",
                extra={"payment_id": payment.id, "user_id": current_user.id},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Payment status could not be confirmed.",
            ) from exc

    message = {
        "pending": PENDING_MESSAGE,
        "success": "Payment approved. Premium is active for 30 days.",
        "failed": "Payment failed. You can try again.",
    }[payment.status]
    return _to_response(payment, current_user, message)
