from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import UserRegisterRequest


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Retrieve user by normalized email."""
    return db.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Retrieve user by primary key ID."""
    return db.query(User).filter(User.id == user_id).first()


def register_user(db: Session, user_in: UserRegisterRequest) -> User:
    """Validate uniqueness, hash password with Argon2, and create new User."""
    normalized_email = user_in.email.strip().lower()

    existing_user = get_user_by_email(db, normalized_email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    hashed_pw = hash_password(user_in.password)

    new_user = User(
        name=user_in.name.strip(),
        email=normalized_email,
        password_hash=hashed_pw
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password."""
    normalized_email = email.strip().lower()
    user = get_user_by_email(db, normalized_email)
    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user
