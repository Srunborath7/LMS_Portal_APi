from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auths.model import Auth, RefreshToken


class AuthRepository:
    """Persists and queries authentication records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> Auth | None:
        result = await self.session.execute(
            select(Auth).where(func.lower(Auth.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Auth | None:
        result = await self.session.execute(
            select(Auth).where(func.lower(Auth.username) == username.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, auth_id: UUID) -> Auth | None:
        result = await self.session.execute(select(Auth).where(Auth.id == auth_id))
        return result.scalar_one_or_none()

    async def create(self, *, username: str, email: str, password_hash: str) -> Auth:
        auth = Auth(username=username, email=email, password_hash=password_hash)
        self.session.add(auth)
        await self.session.flush()
        await self.session.refresh(auth)
        return auth

    async def update_last_login(self, auth: Auth) -> Auth:
        auth.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(auth)
        return auth

    async def create_refresh_token(
        self, *, auth_id: UUID, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            auth_id=auth_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(refresh_token)
        await self.session.flush()
        return refresh_token

    async def get_refresh_token(self, token_hash: str, *, lock: bool = False) -> RefreshToken | None:
        statement = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        if lock:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token: RefreshToken) -> None:
        if token.revoked_at is None:
            token.revoked_at = datetime.now(timezone.utc)
            await self.session.flush()
