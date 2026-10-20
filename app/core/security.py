import asyncio
import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from dotenv import load_dotenv

from app.core.exceptions import ServiceUnavailable


class SecurityService:
    """Owns password hashing and access-token creation and validation."""

    _scrypt_n = 2**14
    _scrypt_r = 8
    _scrypt_p = 1
    _issuer = "lms-portal-api"
    _audience = "lms-portal-api"
    _algorithm = "HS256"

    def __init__(self) -> None:
        load_dotenv()

    @staticmethod
    def _secret_key() -> str:
        load_dotenv()
        secret = os.getenv("JWT_SECRET_KEY", "")
        if len(secret) < 32:
            raise ServiceUnavailable(
                detail="Authentication is not configured. Set JWT_SECRET_KEY in .env."
            )
        return secret

    @classmethod
    def _hash_sync(cls, password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=cls._scrypt_n,
            r=cls._scrypt_r,
            p=cls._scrypt_p,
            dklen=32,
        )
        salt_text = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
        digest_text = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"scrypt${salt_text}${digest_text}${cls._scrypt_n}"

    async def hash_password(self, password: str) -> str:
        return await asyncio.to_thread(self._hash_sync, password)

    @classmethod
    def _verify_sync(cls, password: str, stored_hash: str | None) -> bool:
        if not stored_hash:
            return False
        try:
            algorithm, salt_text, digest_text, cost_text = stored_hash.split("$")
            cost = int(cost_text)
            if algorithm != "scrypt" or cost < cls._scrypt_n or cost > 2**18:
                return False
            salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
            expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
            if len(salt) < 16 or len(expected) != 32:
                return False
            actual = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=cost,
                r=cls._scrypt_r,
                p=cls._scrypt_p,
                dklen=len(expected),
            )
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    async def verify_password(self, password: str, stored_hash: str | None) -> bool:
        return await asyncio.to_thread(self._verify_sync, password, stored_hash)

    def create_access_token(self, subject: UUID) -> str:
        now = datetime.now(timezone.utc)
        try:
            expires_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        except ValueError as exc:
            raise ServiceUnavailable(detail="ACCESS_TOKEN_EXPIRE_MINUTES must be an integer.") from exc
        if not 1 <= expires_minutes <= 1440:
            raise ServiceUnavailable(
                detail="ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440."
            )
        payload = {
            "sub": str(subject),
            "iat": now,
            "exp": now + timedelta(minutes=expires_minutes),
            "typ": "access",
            "iss": self._issuer,
            "aud": self._audience,
        }
        return jwt.encode(payload, self._secret_key(), algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> UUID:
        payload = jwt.decode(
            token,
            self._secret_key(),
            algorithms=[self._algorithm],
            issuer=self._issuer,
            audience=self._audience,
            options={"require": ["sub", "iat", "exp", "typ", "iss", "aud"]},
        )
        if payload.get("typ") != "access":
            raise jwt.InvalidTokenError("Invalid token type")
        try:
            return UUID(payload["sub"])
        except (ValueError, TypeError, KeyError) as exc:
            raise jwt.InvalidTokenError("Invalid token subject") from exc

    @staticmethod
    def _refresh_token_days() -> int:
        try:
            days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
        except ValueError as exc:
            raise ServiceUnavailable(detail="REFRESH_TOKEN_EXPIRE_DAYS must be an integer.") from exc
        if not 1 <= days <= 90:
            raise ServiceUnavailable(detail="REFRESH_TOKEN_EXPIRE_DAYS must be between 1 and 90.")
        return days

    def create_refresh_token(self) -> tuple[str, str, datetime]:
        """Return the raw token, its database hash, and its UTC expiry."""
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._refresh_token_days())
        return raw_token, token_hash, expires_at

    @staticmethod
    def hash_refresh_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def refresh_cookie_options() -> dict[str, object]:
        secure_setting = os.getenv("REFRESH_COOKIE_SECURE", "false").strip().lower()
        if secure_setting not in {"true", "false", "1", "0", "yes", "no"}:
            raise ServiceUnavailable(detail="REFRESH_COOKIE_SECURE must be a boolean value.")
        same_site = os.getenv("REFRESH_COOKIE_SAMESITE", "lax").strip().lower()
        if same_site not in {"lax", "strict", "none"}:
            raise ServiceUnavailable(
                detail="REFRESH_COOKIE_SAMESITE must be lax, strict, or none."
            )
        secure = secure_setting in {"true", "1", "yes"}
        if same_site == "none" and not secure:
            raise ServiceUnavailable(detail="SameSite=None requires REFRESH_COOKIE_SECURE=true.")
        return {
            "httponly": True,
            "secure": secure,
            "samesite": same_site,
            "path": "/api/v1/auths",
        }
