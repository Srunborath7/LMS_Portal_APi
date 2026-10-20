from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import Conflict, Unauthorized
from app.core.security import SecurityService
from app.domain.auths import model
from app.domain.auths.schema import AuthCreate, AuthLogin
from app.repositories.auth_repositories import AuthRepository


class AuthService:
    """Applies authentication rules and coordinates repository transactions."""

    def __init__(self, repository: AuthRepository, security: SecurityService) -> None:
        self.repository = repository
        self.security = security

    async def register(self, data: AuthCreate) -> model.Auth:
        username = data.username.strip()
        email = str(data.email).lower()
        password_hash = await self.security.hash_password(data.password)
        try:
            async with self.repository.session.begin():
                if await self.repository.get_by_email(email):
                    raise Conflict("An account with this email already exists")
                if await self.repository.get_by_username(username):
                    raise Conflict("This username is already taken")
                return await self.repository.create(
                    username=username, email=email, password_hash=password_hash
                )
        except Conflict:
            raise
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise Conflict(
                "An account with this email or username already exists"
            ) from exc

    async def login(self, data: AuthLogin) -> tuple[model.Auth, str, str, int]:
        async with self.repository.session.begin():
            auth = await self.repository.get_by_email(str(data.email).lower())
            password_ok = await self.security.verify_password(data.password, auth.password_hash if auth else None)
            if auth is None or not password_ok or not auth.is_active:
                raise Unauthorized("Invalid email or password")
            access_token = self.security.create_access_token(auth.id)
            refresh_token, token_hash, expires_at = self.security.create_refresh_token()
            await self.repository.create_refresh_token(
                auth_id=auth.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            await self.repository.update_last_login(auth)
        max_age = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
        return auth, access_token, refresh_token, max_age

    async def refresh(self, raw_token: str) -> tuple[model.Auth, str, str, int]:
        token_hash = self.security.hash_refresh_token(raw_token)
        async with self.repository.session.begin():
            stored_token = await self.repository.get_refresh_token(token_hash, lock=True)
            now = datetime.now(timezone.utc)
            if (
                stored_token is None
                or stored_token.revoked_at is not None
                or stored_token.expires_at <= now
            ):
                raise Unauthorized("Invalid or expired refresh token")

            auth = await self.repository.get_by_id(stored_token.auth_id)
            if auth is None or not auth.is_active:
                raise Unauthorized("Account unavailable")

            await self.repository.revoke_refresh_token(stored_token)
            new_raw_token, new_token_hash, expires_at = self.security.create_refresh_token()
            await self.repository.create_refresh_token(
                auth_id=auth.id,
                token_hash=new_token_hash,
                expires_at=expires_at,
            )
            access_token = self.security.create_access_token(auth.id)

        max_age = max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))
        return auth, access_token, new_raw_token, max_age

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        token_hash = self.security.hash_refresh_token(raw_token)
        async with self.repository.session.begin():
            stored_token = await self.repository.get_refresh_token(token_hash, lock=True)
            if stored_token is not None:
                await self.repository.revoke_refresh_token(stored_token)

    async def get_auth(self, auth_id: UUID) -> model.Auth | None:
        return await self.repository.get_by_id(auth_id)

    def decode_access_token(self, token: str) -> UUID:
        return self.security.decode_access_token(token)
