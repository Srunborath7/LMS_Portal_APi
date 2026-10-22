from datetime import datetime, timezone
from uuid import UUID
from app.domain.auths.model import AuthRole
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update as sa_update
from app.domain.auths.model import Auth, RefreshToken, PasswordResetToken


class AuthRepository:
    """Persists and queries authentication records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str, *, lock: bool = False) -> Auth | None:
        statement = select(Auth).where(func.lower(Auth.email) == email.lower())
        if lock:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
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

    async def list(
        self,
        *,
        q: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Auth], int]:
        stmt = select(Auth)

        if is_active is not None:
            stmt = stmt.where(Auth.is_active == is_active)
        if q:
            escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            stmt = stmt.where(
                or_(
                    Auth.username.ilike(pattern, escape="\\"),
                    Auth.email.ilike(pattern, escape="\\"),
                )
            )

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )

        stmt = (
            stmt.order_by(Auth.created_at.desc(), Auth.id)  # id = stable paging
            .offset((page - 1) * size)
            .limit(size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total or 0

    async def update(self, auth: Auth, changes: dict) -> Auth:

        for key, value in changes.items():
            setattr(auth, key, value)
        await self.session.flush()
        await self.session.refresh(auth)

        return auth

    async def delete(self, auth: Auth) -> None:
        await self.session.delete(auth)
        await self.session.flush()

    async def revoke_all_refresh_tokens(self, auth_id: UUID) -> None:
        await self.session.execute(
            sa_update(RefreshToken)
            .where(RefreshToken.auth_id == auth_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def create_password_reset_token(self, auth_id: UUID, token_hash: str, expires_at: datetime) -> None:
        await self.session.execute(
            sa_update(PasswordResetToken)
            .where(PasswordResetToken.auth_id == auth_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=datetime.now(timezone.utc))
        )
        self.session.add(PasswordResetToken(auth_id=auth_id, token_hash=token_hash, expires_at=expires_at))
        await self.session.flush()

    async def get_password_reset_token(self, token_hash: str, *, lock: bool = False) -> PasswordResetToken | None:
        statement = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        if lock:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def count_active_admins(self) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(Auth).where(
                Auth.role == AuthRole.admin, Auth.is_active.is_(True)
            )
        ) or 0
