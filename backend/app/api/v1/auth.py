"""Authentication API endpoints.

Security:
- Rate limiting on login and register endpoints to prevent brute force attacks
- Login: 5 attempts per minute per IP
- Register: 3 attempts per minute per IP
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.rate_limiter import limiter
from app.db.postgres import get_db
from app.models.user import User, UserCreate, UserResponse
from app.api.deps import get_current_active_user

router = APIRouter()


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Login response with token and user info."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """Authenticate user and return JWT token.

    Rate limited to 5 attempts per minute per IP to prevent brute force attacks.
    """
    # Trim username to handle accidental whitespace
    username = form_data.username.strip()
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Register a new user. Creates a new organization for each user unless org_id is specified.

    Rate limited to 3 attempts per minute per IP to prevent abuse.
    """
    from app.models.organization import Organization
    from uuid import uuid4

    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # If no org_id provided, create a new organization for this user
    org_id = user_data.org_id
    if org_id is None:
        # Create a unique organization for this user
        org_code = f"ORG_{user_data.username.upper()}_{uuid4().hex[:8]}"
        new_org = Organization(
            name=f"{user_data.full_name or user_data.username}的组织",
            code=org_code,
            address="",
            contact_name=user_data.full_name or user_data.username,
            contact_phone="",
        )
        db.add(new_org)
        await db.flush()
        await db.refresh(new_org)
        org_id = new_org.id

    # Create user with admin role for their own organization
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role.value if user_data.org_id else 'admin',  # Auto admin for new org
        org_id=org_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Get current user information."""
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Logout current user (client should discard token)."""
    return {"message": "Successfully logged out"}
