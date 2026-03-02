"""Auth API router"""

from fastapi import APIRouter, HTTPException, status, Depends
from pymongo.errors import DuplicateKeyError

from app.auth.models import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    RefreshRequest,
    AccessTokenResponse,
    UserInfo,
)
from app.auth.service import get_auth_service
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: UserRegisterRequest):
    auth = get_auth_service()

    try:
        auth.create_user(req.username, req.email, req.password)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    return TokenResponse(
        access_token=auth.create_access_token(req.username),
        refresh_token=auth.create_refresh_token(req.username),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLoginRequest):
    auth = get_auth_service()
    user = auth.authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    return TokenResponse(
        access_token=auth.create_access_token(req.username),
        refresh_token=auth.create_refresh_token(req.username),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(req: RefreshRequest):
    auth = get_auth_service()
    username = auth.verify_token(req.refresh_token, expected_type="refresh")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return AccessTokenResponse(
        access_token=auth.create_access_token(username),
    )


@router.get("/me", response_model=UserInfo)
async def me(current_user: str = Depends(get_current_user)):
    auth = get_auth_service()
    user = auth.get_user_by_username(current_user)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserInfo(
        username=user["username"],
        email=user["email"],
        created_at=user.get("created_at"),
    )
