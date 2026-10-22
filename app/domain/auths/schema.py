from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.auths.model import AuthRole


class AuthCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def trim_username(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Username must contain at least 3 non-space characters")
        return value


class AuthLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: EmailStr
    role: AuthRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class RefreshTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    auth_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthRead

class AuthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: EmailStr
    is_active: bool
    is_verified: bool
    failed_login_attempts: int
    locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime


class AuthFilter(BaseModel):
    q: str | None = None
    is_active: bool | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class AuthPage(BaseModel):
    items: list[AuthOut]
    total: int
    page: int
    size: int

class AuthUpdate(BaseModel):
    """Admin PATCH: every field optional. Use data.model_dump(exclude_unset=True)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = None
    role: AuthRole | None = None
    is_active: bool | None = None
    is_verified: bool | None = None

    @field_validator("username")
    @classmethod
    def trim_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Username must contain at least 3 non-space characters")
        return value

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str | None) -> str | None:
        return v.lower() if v else v


class AuthPasswordChange(BaseModel):
    """For the logged-in user changing their own password."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)
