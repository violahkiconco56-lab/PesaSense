from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    PasswordChange,
    UserCreate,
    UserCreateResponse,
    UserResponse,
    UserUpdate,
)
from app.services.email import check_smtp_connection, send_verification_email
from app.services.security import hash_password, verify_password, create_access_token
from app.services.auth import get_current_user
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.post(
    "/",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED
)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    # Check if email already exists
    existing_user = (
        db.query(User)
        .filter(User.email == user.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered."
        )

    # Check if username already exists (the column is unique, so a duplicate
    # would otherwise surface as an unhandled 500 IntegrityError on commit).
    existing_username = (
        db.query(User)
        .filter(User.username == user.username)
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken. Please choose another name."
        )

    verification_token = secrets.token_urlsafe(32)
    new_user = User(
        username=user.username,
        email=user.email,
        password=hash_password(user.password),
        profile_picture_url=user.profile_picture_url,
        email_verification_token=verification_token,
        email_verification_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    verification_url = (
        f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    )

    # send_verification_email handles its own errors and returns False on
    # failure, so a mail problem never breaks account creation.
    email_sent = send_verification_email(
        new_user.email,
        new_user.username,
        verification_url,
    )

    return {
        **UserResponse.model_validate(new_user).model_dump(),
        "email_verification_sent": email_sent,
        "email_verification_message": (
            "Confirmation email sent. Please check your inbox."
            if email_sent
            else "Account created. Email confirmation is pending until SMTP is configured."
        ),
    }


@router.get("/verify-email")
def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email_verification_token == token)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification link."
        )

    expires_at = user.email_verification_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification link has expired."
            )

    user.is_verified = True
    user.email_verification_token = None
    user.email_verification_expires_at = None
    db.commit()

    return {"message": "Email confirmed successfully."}


@router.get("/email-status")
def email_status():
    """Report whether the SMTP verification email is ready to send.

    Exposes only non-sensitive diagnostics (no username/password values) so the
    Brevo/SMTP configuration can be checked without creating test accounts.
    """
    return check_smtp_connection()


@router.get("/", response_model=UserResponse)
def get_current_user_profile_from_root(
    current_user: User = Depends(get_current_user)
):
    return current_user


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    return current_user


@router.put("/me", response_model=UserResponse)
def update_current_user_profile(
    updated_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    update_fields = updated_data.model_dump(exclude_unset=True)

    if "username" in update_fields:
        existing_username = (
            db.query(User)
            .filter(
                User.username == update_fields["username"],
                User.id != current_user.id
            )
            .first()
        )
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken."
            )

    if "email" in update_fields:
        existing_email = (
            db.query(User)
            .filter(
                User.email == update_fields["email"],
                User.id != current_user.id
            )
            .first()
        )
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered."
            )

    for field, value in update_fields.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return current_user


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_current_user_password(
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not verify_password(password_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )

    current_user.password = hash_password(password_data.new_password)
    db.commit()


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    db_user = (
        db.query(User)
        .filter(User.email == form_data.username)
        .first()
    )

    if not db_user or not verify_password(
        form_data.password,
        db_user.password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_access_token(
        {"user_id": db_user.id}
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }
