from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import PasswordChange, UserCreate, UserResponse, UserUpdate
from app.services.security import hash_password, verify_password, create_access_token
from app.services.auth import get_current_user
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.post(
    "/",
    response_model=UserResponse,
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

    new_user = User(
        username=user.username,
        email=user.email,
        password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


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
