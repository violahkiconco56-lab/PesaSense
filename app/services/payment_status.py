from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import logging

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.user import User


logger = logging.getLogger(__name__)
PREMIUM_PERIOD = timedelta(days=30)


class PaymentStatusMismatch(Exception):
    pass


def _check_response_matches(payment: Payment, result: dict, queried_reference: str):
    if result.get("internal_reference") != queried_reference:
        raise PaymentStatusMismatch("Relworx returned a different payment reference.")
    if result.get("customer_reference") != payment.reference:
        raise PaymentStatusMismatch("Relworx returned a different customer reference.")
    if result.get("msisdn") != payment.msisdn:
        raise PaymentStatusMismatch("Relworx returned a different phone number.")
    if result.get("currency") != payment.currency:
        raise PaymentStatusMismatch("Relworx returned a different currency.")
    try:
        if Decimal(str(result.get("amount"))) != Decimal(str(payment.amount)):
            raise PaymentStatusMismatch("Relworx returned a different payment amount.")
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PaymentStatusMismatch("Relworx returned an invalid payment amount.") from exc


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def reconcile_payment_status(
    db: Session,
    payment: Payment,
    internal_reference: str,
    result: dict,
) -> Payment:
    _check_response_matches(payment, result, internal_reference)
    response_status = result.get("request_status", result.get("status"))
    if result.get("status") and result.get("request_status"):
        if result["status"] != result["request_status"]:
            raise PaymentStatusMismatch("Relworx returned conflicting payment statuses.")
    if response_status not in {"pending", "success", "failed"}:
        response_status = "pending"

    locked_payment = (
        db.query(Payment)
        .filter(Payment.id == payment.id)
        .with_for_update()
        .one()
    )
    if locked_payment.status != "pending":
        return locked_payment

    locked_payment.internal_reference = internal_reference
    if response_status == "failed":
        locked_payment.status = "failed"
    elif response_status == "success":
        user = (
            db.query(User)
            .filter(User.id == locked_payment.user_id)
            .with_for_update()
            .one()
        )
        now = datetime.now(timezone.utc)
        period_end = user.current_period_end
        if period_end is not None:
            period_end = _aware_datetime(period_end)
        starts_at = period_end if period_end and period_end > now else now
        user.subscription_plan = "premium"
        user.subscription_status = "active"
        user.current_period_end = starts_at + PREMIUM_PERIOD
        locked_payment.status = "success"

    db.commit()
    db.refresh(locked_payment)
    logger.info(
        "Relworx payment status reconciled",
        extra={
            "payment_id": locked_payment.id,
            "user_id": locked_payment.user_id,
            "status": locked_payment.status,
        },
    )
    return locked_payment
