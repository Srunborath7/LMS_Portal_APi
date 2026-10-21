from __future__ import annotations
import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import (CheckConstraint, DateTime, Enum, Index, Numeric, String, Text, Uuid, text,)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.audit import AuditMixin
from app.core.base import Base

class CourseLevel(str, enum.Enum):
    beginner = "beginner"
    elementary = "elementary"
    intermediate = "intermediate"
    upper_intermediate = "upper_intermediate"
    advanced = "advanced"
    all_levels = "all_levels"


class CourseStatus(str, enum.Enum):
    draft = "draft"            # being prepared, not visible to students
    published = "published"    # open for new classes and enrollment
    archived = "archived"      # no new classes, history kept


class Course(AuditMixin, Base):
    __tablename__ = "courses"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    course_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # CRS-000001

    # Catalog info
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    objectives: Mapped[str | None] = mapped_column(Text)        # what students will learn
    category: Mapped[str | None] = mapped_column(String(100))   # e.g. Language, IT, Business
    level: Mapped[CourseLevel] = mapped_column(
        Enum(CourseLevel, native_enum=False, length=20),
        nullable=False,
        default=CourseLevel.all_levels,
        server_default=CourseLevel.all_levels.value,
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default="en")  # teaching language
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))

    # Size and price (defaults; a class can override later)
    duration_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="USD")

    # Lifecycle
    status: Mapped[CourseStatus] = mapped_column(
        Enum(CourseStatus, native_enum=False, length=20),
        nullable=False,
        default=CourseStatus.draft,
        server_default=CourseStatus.draft.value,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Later: classes = relationship("Class", back_populates="course")

    __table_args__ = (
        CheckConstraint("fee >= 0", name="ck_courses_fee_nonneg"),
        CheckConstraint("duration_hours IS NULL OR duration_hours > 0", name="ck_courses_duration_pos"),
        # Name must be unique among non-deleted courses, so a deleted name can be reused
        Index("uq_courses_name_lower", text("lower(name)"), unique=True,postgresql_where=text("deleted_at IS NULL")),
        Index("ix_courses_status", "status"),
        Index("ix_courses_category", "category"),
        Index("ix_courses_level", "level"),
    )