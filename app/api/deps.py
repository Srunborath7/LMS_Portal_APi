from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import current_user_id
from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import SecurityService
from app.core.database import get_db
from app.domain.auths.model import Auth, AuthRole
from app.repositories.auth_repositories import AuthRepository


DbSession = Annotated[AsyncSession, Depends(get_db)]
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> AsyncIterator[Auth]:
    if credentials is None:
        raise Unauthorized("Bearer token required")
    try:
        auth_id = SecurityService().decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise Unauthorized("Invalid or expired access token") from exc

    auth = await AuthRepository(db).get_by_id(auth_id)
    if auth is None or not auth.is_active:
        raise Unauthorized("Account unavailable")

    context_token = current_user_id.set(auth.id)
    try:
        yield auth
    finally:
        current_user_id.reset(context_token)


CurrentAuth = Annotated[Auth, Depends(get_current_auth)]


async def get_current_user_id(auth: CurrentAuth) -> UUID:
    return auth.id


async def require_staff(
    auth: CurrentAuth,
) -> UUID:
    if auth.role not in {AuthRole.teacher, AuthRole.admin}:
        raise Forbidden("A teacher or administrator role is required")
    return auth.id


async def require_admin(auth: CurrentAuth) -> UUID:
    if auth.role != AuthRole.admin:
        raise Forbidden("An administrator role is required")
    return auth.id
