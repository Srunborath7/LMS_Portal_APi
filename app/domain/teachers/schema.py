from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.students.model import Gender
from app.domain.teachers.model import EmploymentType, TeacherStatus

E164 = re.compile(r"^\+[1-9]\d{7,14}$")

Name100 = Annotated[str, StringConstraints(min_length=1, max_length=100)]


def _normalize_phone(v: str | None) -> str | None:
    if v is None:
        return None
    v = re.sub(r"[\s\-().]", "", v)
    if not E164.match(v):
        raise ValueError("Phone must be in international format, e.g. +85512345678")
    return v


def _dob_not_future(v: date | None) -> date | None:
    if v and v > date.today():
        raise ValueError("date_of_birth cannot be in the future")
    return v


class TeacherBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    # Personal
    first_name: Name100
    last_name: Name100
    date_of_birth: date | None = None
    gender: Gender | None = None
    nationality: str | None = Field(default=None, max_length=50)

    # Contact
    email: EmailStr
    phone: str | None = None
    address: str | None = Field(default=None, max_length=1000)

    # Emergency contact
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = None

    # Professional
    title: str | None = Field(default=None, max_length=50)
    highest_degree: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=150)
    years_of_experience: int | None = Field(default=None, ge=0, le=60)
    bio: str | None = Field(default=None, max_length=3000)

    # Employment
    employment_type: EmploymentType = EmploymentType.full_time
    hire_date: date | None = None
    end_date: date | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)

    note: str | None = Field(default=None, max_length=5000)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("date_of_birth")
    @classmethod
    def check_dob(cls, v: date | None) -> date | None:
        return _dob_not_future(v)

    @model_validator(mode="after")
    def check_dates(self):
        if self.hire_date and self.end_date and self.end_date < self.hire_date:
            raise ValueError("end_date cannot be before hire_date")
        return self


class TeacherCreate(TeacherBase):
    """teacher_code, audit fields and deleted_at are set by the server."""

    status: TeacherStatus = TeacherStatus.active
    auth_id: UUID | None = None


class TeacherUpdate(BaseModel):
    """PATCH: every field optional. Use data.model_dump(exclude_unset=True)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    first_name: Name100 | None = None
    last_name: Name100 | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    nationality: str | None = Field(default=None, max_length=50)

    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = Field(default=None, max_length=1000)

    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = None

    title: str | None = Field(default=None, max_length=50)
    highest_degree: str | None = Field(default=None, max_length=100)
    specialization: str | None = Field(default=None, max_length=150)
    years_of_experience: int | None = Field(default=None, ge=0, le=60)
    bio: str | None = Field(default=None, max_length=3000)

    employment_type: EmploymentType | None = None
    status: TeacherStatus | None = None
    hire_date: date | None = None
    end_date: date | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)

    note: str | None = Field(default=None, max_length=5000)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str | None) -> str | None:
        return v.lower() if v else v

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("date_of_birth")
    @classmethod
    def check_dob(cls, v: date | None) -> date | None:
        return _dob_not_future(v)

    @model_validator(mode="after")
    def check_dates(self):
        if self.hire_date and self.end_date and self.end_date < self.hire_date:
            raise ValueError("end_date cannot be before hire_date")
        return self


class TeacherOut(BaseModel):
    """Full view for staff/admin. Includes pay, notes and audit fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_code: str
    auth_id: UUID | None

    first_name: str
    last_name: str
    full_name: str
    date_of_birth: date | None
    gender: Gender | None
    nationality: str | None
    image_url: str | None

    email: EmailStr
    phone: str | None
    address: str | None

    emergency_contact_name: str | None
    emergency_contact_phone: str | None

    title: str | None
    highest_degree: str | None
    specialization: str | None
    years_of_experience: int | None
    bio: str | None

    employment_type: EmploymentType
    status: TeacherStatus
    hire_date: date | None
    end_date: date | None
    hourly_rate: Decimal | None
    note: str | None

    created_at: datetime
    updated_at: datetime
    created_by_id: UUID | None
    updated_by_id: UUID | None


class TeacherPublic(BaseModel):
    """Safe view for students, parents and public pages.
    No pay, notes, emergency contact, address, date of birth or audit fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_code: str
    full_name: str
    title: str | None
    image_url: str | None
    highest_degree: str | None
    specialization: str | None
    years_of_experience: int | None
    bio: str | None
    email: EmailStr


class TeacherBrief(BaseModel):
    """Lightweight version for dropdowns and nesting (e.g. inside a class)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_code: str
    full_name: str
    image_url: str | None = None
    status: TeacherStatus


class TeacherFilter(BaseModel):
    """Use with `filters: Annotated[TeacherFilter, Query()]`."""

    q: str | None = Field(default=None, description="Search name, email, code or phone")
    status: TeacherStatus | None = None
    employment_type: EmploymentType | None = None
    specialization: str | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class TeacherPage(BaseModel):
    items: list[TeacherOut]
    total: int
    page: int
    size: int
