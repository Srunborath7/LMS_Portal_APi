from typing import Annotated

import jwt
from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import Unauthorized
from app.core.security import SecurityService
from app.domain.auths.model import Auth
from app.domain.auths.schema import AuthCreate, AuthLogin, AuthRead, AuthToken
from app.repositories.auth_repositories import AuthRepository
from app.services.auth_services import AuthService


router = APIRouter(prefix="/auths", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(AuthRepository(db), SecurityService())


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=AuthRead, status_code=status.HTTP_201_CREATED)
async def register(data: AuthCreate, service: AuthServiceDep) -> Auth:
    return await service.register(data)


@router.post("/login", response_model=AuthToken)
async def login(data: AuthLogin, response: Response, service: AuthServiceDep) -> AuthToken:
    auth, access_token, refresh_token, max_age = await service.login(data)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=max_age,
        **SecurityService.refresh_cookie_options(),
    )
    return AuthToken(access_token=access_token, user=AuthRead.model_validate(auth))


@router.post("/refresh", response_model=AuthToken)
async def refresh(
    response: Response,
    service: AuthServiceDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> AuthToken:
    if not refresh_token:
        raise Unauthorized("Refresh token required")
    auth, access_token, new_refresh_token, max_age = await service.refresh(refresh_token)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        max_age=max_age,
        **SecurityService.refresh_cookie_options(),
    )
    return AuthToken(access_token=access_token, user=AuthRead.model_validate(auth))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    service: AuthServiceDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    await service.logout(refresh_token)
    response.delete_cookie(
        key="refresh_token",
        **SecurityService.refresh_cookie_options(),
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


async def get_current_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    service: AuthServiceDep,
) -> Auth:
    if credentials is None:
        raise Unauthorized("Bearer token required")
    try:
        auth_id = service.decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise Unauthorized("Invalid or expired access token") from exc
    auth = await service.get_auth(auth_id)
    if auth is None or not auth.is_active:
        raise Unauthorized("Account unavailable")
    return auth


@router.get("/me", response_model=AuthRead)
async def get_me(auth: Annotated[Auth, Depends(get_current_auth)]) -> Auth:
    return auth
