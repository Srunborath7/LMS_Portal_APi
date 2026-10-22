from datetime import datetime, timedelta, timezone
import hashlib
import os
from uuid import UUID
from sqlalchemy.exc import IntegrityError
from app.core.exceptions import Conflict, Unauthorized, BadRequest, NotFound
from app.core.security import SecurityService
from app.core.email import send_password_reset_email
from app.domain.auths import model
from app.domain.auths.schema import AuthCreate, AuthLogin, AuthUpdate
from app.domain.auths.model import Auth, AuthRole
from app.repositories.auth_repositories import AuthRepository

NOT_NULLABLE = {"username", "email", "role", "is_active", "is_verified"}
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_DURATION = timedelta(minutes=15)


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
        login_failed = False
        failure_message = "Invalid email or password"
        async with self.repository.session.begin():
            auth = await self.repository.get_by_email(
                str(data.email).lower(), lock=True
            )
            now = datetime.now(timezone.utc)

            if auth is None or not auth.is_active:
                login_failed = True
            else:
                locked_until = auth.locked_until
                if locked_until is not None and locked_until.tzinfo is None:
                    locked_until = locked_until.replace(tzinfo=timezone.utc)

                if locked_until is not None and locked_until > now:
                    login_failed = True
                    failure_message = (
                        "Account temporarily locked. Try again after "
                        f"{locked_until.isoformat()}"
                    )
                else:
                    # Start a fresh attempt window after an expired lock.
                    auth.failed_login_attempts = 0
                    auth.locked_until = None
                    password_ok = await self.security.verify_password(
                        data.password, auth.password_hash
                    )
                    if not password_ok:
                        auth.failed_login_attempts += 1
                        if auth.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                            auth.locked_until = now + LOGIN_LOCK_DURATION
                            failure_message = (
                                "Invalid email or password. Account locked for "
                                f"{int(LOGIN_LOCK_DURATION.total_seconds() // 60)} minutes "
                                "after too many failed attempts."
                            )
                        else:
                            remaining = (
                                MAX_FAILED_LOGIN_ATTEMPTS - auth.failed_login_attempts
                            )
                            failure_message = (
                                "Invalid email or password. "
                                f"You have {remaining} "
                                f"attempt{'s' if remaining != 1 else ''} remaining."
                            )
                        login_failed = True
                    else:
                        auth.failed_login_attempts = 0
                        auth.locked_until = None
                        access_token = self.security.create_access_token(auth.id)
                        refresh_token, token_hash, expires_at = self.security.create_refresh_token()
                        await self.repository.create_refresh_token(
                            auth_id=auth.id,
                            token_hash=token_hash,
                            expires_at=expires_at,
                        )
                        await self.repository.update_last_login(auth)

        # Raise outside the transaction so failed-attempt updates are committed.
        if login_failed:
            raise Unauthorized(failure_message)
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

    async def request_password_reset(self, email: str) -> None:
        auth = await self.repository.get_by_email(email.lower())
        if auth is None or not auth.is_active:
            return
        reset_page = os.getenv("PASSWORD_RESET_URL", "").strip()
        if not reset_page:
            from app.core.exceptions import ServiceUnavailable
            raise ServiceUnavailable("Password reset is not configured")
        raw_token, token_hash, expires_at = self.security.create_password_reset_token()
        await self.repository.create_password_reset_token(auth.id, token_hash, expires_at)
        await self.repository.session.commit()
        separator = "&" if "?" in reset_page else "?"
        await send_password_reset_email(auth.email, f"{reset_page}{separator}token={raw_token}")

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        try:
            reset_token = await self.repository.get_password_reset_token(token_hash, lock=True)
            now = datetime.now(timezone.utc)
            if reset_token is None or reset_token.used_at is not None or reset_token.expires_at <= now:
                raise BadRequest("Invalid or expired password reset link")
            auth = await self.repository.get_by_id(reset_token.auth_id)
            if auth is None or not auth.is_active:
                raise BadRequest("Invalid or expired password reset link")
            auth.password_hash = await self.security.hash_password(new_password)
            auth.failed_login_attempts = 0
            auth.locked_until = None
            reset_token.used_at = now
            await self.repository.revoke_all_refresh_tokens(auth.id)
            await self.repository.session.commit()
        except Exception:
            await self.repository.session.rollback()
            raise

    async def get_auth(self, auth_id: UUID) -> model.Auth | None:
        return await self.repository.get_by_id(auth_id)

    async def list_auths(
        self,
        *,
        q: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[model.Auth], int]:
        return await self.repository.list(
            q=q, is_active=is_active, page=page, size=size
        )

    def decode_access_token(self, token: str) -> UUID:
        return self.security.decode_access_token(token)

    async def update_auth(self, auth_id: UUID, data: AuthUpdate, current_user_id: UUID) -> Auth:
        auth = await self.repository.get_by_id(auth_id)
        if not auth:
            raise NotFound("Account")

        changes = data.model_dump(exclude_unset=True)
        if "username" in changes and changes["username"] is not None:
            changes["username"] = changes["username"].strip()
        if "email" in changes and changes["email"] is not None:
            changes["email"] = str(changes["email"]).lower()
        for field in NOT_NULLABLE & changes.keys():
            if changes[field] is None:
                raise BadRequest(f"{field} cannot be null")

        if "email" in changes:
            other = await self.repository.get_by_email(changes["email"])
            if other and other.id != auth.id:
                raise Conflict("This email is already in use")
        if "username" in changes:
            other = await self.repository.get_by_username(changes["username"])
            if other and other.id != auth.id:
                raise Conflict("This username is already in use")

        # Protect against locking yourself or the whole system out
        demoting = changes.get("role") not in (None, AuthRole.admin) and auth.role == AuthRole.admin
        deactivating = changes.get("is_active") is False
        if auth.id == current_user_id and (demoting or deactivating):
            raise BadRequest("You cannot demote or deactivate your own account")
        if auth.role == AuthRole.admin and auth.is_active and (demoting or deactivating):
            if await self.repository.count_active_admins() <= 1:
                raise BadRequest("At least one active admin is required")

        try:
            await self.repository.update(auth, changes)
            if deactivating:
                await self.repository.revoke_all_refresh_tokens(auth.id)   # force logout
            await self.repository.session.commit()
        except IntegrityError:
            await self.repository.session.rollback()
            raise Conflict("Email or username is already in use")
        return auth

    async def delete_auth(self, auth_id: UUID, current_user_id: UUID) -> None:
        auth = await self.repository.get_by_id(auth_id)
        if not auth:
            raise NotFound("Account")
        if auth.id == current_user_id:
            raise BadRequest("You cannot delete your own account")
        if auth.role == AuthRole.admin and auth.is_active and await self.repository.count_active_admins() <= 1:
            raise BadRequest("At least one active admin is required")

        try:
            await self.repository.delete(auth)
            await self.repository.session.commit()
        except IntegrityError as exc:
            await self.repository.session.rollback()
            raise Conflict("This account is still referenced and cannot be deleted") from exc
