from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.domain.courses.model import CourseLevel, CourseStatus

Name150 = Annotated[str, StringConstraints(min_length=1, max_length=150)]
CurrencyCode = Annotated[str, StringConstraints(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]
LanguageCode = Annotated[str, StringConstraints(min_length=2, max_length=10)]


class CourseBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: Name150
    description: str | None = Field(default=None, max_length=5000)
    objectives: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=100)
    level: CourseLevel = CourseLevel.all_levels
    language: LanguageCode = "en"
    thumbnail_url: str | None = Field(default=None, max_length=500)

    duration_hours: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=1)
    fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    currency: CurrencyCode = "USD"

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("language")
    @classmethod
    def lower_language(cls, v: str) -> str:
        return v.lower()


class CourseCreate(CourseBase):
    """course_code, published_at, audit fields and deleted_at are set by the server.
    Status starts as draft; use the publish/archive endpoints to change it."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "English Level 1",
                "description": "Basic English for beginners.",
                "objectives": "Introduce yourself, ask simple questions, read short texts.",
                "category": "Language",
                "level": "beginner",
                "language": "en",
                "duration_hours": 48.0,
                "fee": 120.00,
                "currency": "USD",
            }
        },
    )


class CourseUpdate(BaseModel):
    """PATCH: every field optional. Use data.model_dump(exclude_unset=True).
    Status is not here on purpose: change it through publish / archive."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: Name150 | None = None
    description: str | None = Field(default=None, max_length=5000)
    objectives: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=100)
    level: CourseLevel | None = None
    language: LanguageCode | None = None
    thumbnail_url: str | None = Field(default=None, max_length=500)

    duration_hours: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=1)
    fee: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    currency: CurrencyCode | None = None

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("language")
    @classmethod
    def lower_language(cls, v: str | None) -> str | None:
        return v.lower() if v else v


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_code: str

    name: str
    description: str | None
    objectives: str | None
    category: str | None
    level: CourseLevel
    language: str
    thumbnail_url: str | None

    duration_hours: Decimal | None
    fee: Decimal
    currency: str

    status: CourseStatus
    published_at: datetime | None

    created_at: datetime
    updated_at: datetime
    created_by_id: UUID | None
    updated_by_id: UUID | None


class CoursePublic(BaseModel):
    """Catalog view for students and visitors: no audit fields or internal status."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_code: str
    name: str
    description: str | None
    objectives: str | None
    category: str | None
    level: CourseLevel
    language: str
    thumbnail_url: str | None
    duration_hours: Decimal | None
    fee: Decimal
    currency: str


class CourseBrief(BaseModel):
    """Lightweight version for dropdowns and nesting (e.g. inside a class)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_code: str
    name: str
    level: CourseLevel
    status: CourseStatus


class CourseFilter(BaseModel):
    """Use with `filters: Annotated[CourseFilter, Query()]`."""

    q: str | None = Field(default=None, description="Search name, code or category")
    status: CourseStatus | None = None
    level: CourseLevel | None = None
    category: str | None = None
    language: str | None = None
    min_fee: Decimal | None = Field(default=None, ge=0)
    max_fee: Decimal | None = Field(default=None, ge=0)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class CoursePage(BaseModel):
    items: list[CourseOut]
    total: int
    page: int
    size: int

class CoursePublicPage(BaseModel):
    items: list[CoursePublic]
    total: int
    page: int
    size: int