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
