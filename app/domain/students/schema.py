from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from app.domain.students.model import Gender, StudentStatus

E164 = re.compile(r"^\+[1-9]\d{7,14}$")

Name100 = Annotated[str, StringConstraints(min_length=1, max_length=100)]


def _normalize_phone(v: str | None) -> str | None:
    if v is None:
        return None
    v = re.sub(r"[\s\-().]", "", v)  # strip spaces, dashes, brackets
    if not E164.match(v):
        raise ValueError("Phone must be in international format, e.g. +85512345678")
    return v


class StudentBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    first_name: Name100
    last_name: Name100
    date_of_birth: date | None = None
    gender: Gender | None = None

    email: EmailStr
    phone: str | None = None
    address: str | None = Field(default=None, max_length=1000)

    guardian_name: str | None = Field(default=None, max_length=150)
    guardian_phone: str | None = None

    enrolled_at: date | None = None
    note: str | None = Field(default=None, max_length=5000)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()  # matches the lower(email) unique index

    @field_validator("phone", "guardian_phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date | None) -> date | None:
        if v and v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v


class StudentCreate(StudentBase):
    """student_code, audit fields and deleted_at are set by the server."""

    status: StudentStatus = StudentStatus.active
    auth_id: UUID | None = None


class StudentUpdate(BaseModel):
    """PATCH: every field optional. Use data.model_dump(exclude_unset=True)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    first_name: Name100 | None = None
    last_name: Name100 | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None

    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = Field(default=None, max_length=1000)

    guardian_name: str | None = Field(default=None, max_length=150)
    guardian_phone: str | None = None

    status: StudentStatus | None = None
    enrolled_at: date | None = None
    note: str | None = Field(default=None, max_length=5000)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str | None) -> str | None:
        return v.lower() if v else v

    @field_validator("phone", "guardian_phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("date_of_birth")
    @classmethod
    def dob_not_future(cls, v: date | None) -> date | None:
        if v and v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_code: str
    auth_id: UUID | None

    first_name: str
    last_name: str
    full_name: str          # model @property
    date_of_birth: date | None
    age: int | None         # model @property
    gender: Gender | None

    email: EmailStr
    phone: str | None
    address: str | None

    guardian_name: str | None
    guardian_phone: str | None

    status: StudentStatus
    enrolled_at: date | None
    note: str | None

    created_at: datetime
    updated_at: datetime
    created_by_id: UUID | None
    updated_by_id: UUID | None


class StudentBrief(BaseModel):
    """Lightweight version for dropdowns and nested use (e.g. enrollments)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_code: str
    full_name: str
    status: StudentStatus


class StudentFilter(BaseModel):
    """Use with `filters: StudentFilter = Depends()` or `Annotated[StudentFilter, Query()]`."""

    q: str | None = Field(default=None, description="Search name, email, code or phone")
    status: StudentStatus | None = None
    gender: Gender | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class StudentPage(BaseModel):
    items: list[StudentOut]
    total: int
    page: int
    size: int