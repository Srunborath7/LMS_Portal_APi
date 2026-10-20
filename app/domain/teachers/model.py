from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, Uuid, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.audit import AuditMixin
from app.core.base import Base
from app.domain.students.model import Gender  # better: move shared enums to app/models/enums.py


class EmploymentType(str, enum.Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    volunteer = "volunteer"


class TeacherStatus(str, enum.Enum):
    active = "active"
    on_leave = "on_leave"
    resigned = "resigned"
    terminated = "terminated"


class Teacher(AuditMixin, Base):
    __tablename__ = "teachers"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)

    # Login account (1:1), nullable so you can pre-register teachers
    auth_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auths.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    teacher_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # TCH-2026-000001

    # Personal
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender, native_enum=False, length=20))
    nationality: Mapped[str | None] = mapped_column(String(50))
    image_url: Mapped[str | None] = mapped_column(String(500))

    # Contact
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))  # E.164
    address: Mapped[str | None] = mapped_column(Text)

    # Emergency contact
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(20))

    # Professional
    title: Mapped[str | None] = mapped_column(String(50))             # Mr., Ms., Dr., Prof.
    highest_degree: Mapped[str | None] = mapped_column(String(100))   # BSc, MA, PhD
    specialization: Mapped[str | None] = mapped_column(String(150))   # e.g. English, Mathematics
    years_of_experience: Mapped[int | None] = mapped_column()
    bio: Mapped[str | None] = mapped_column(Text)

    # Employment
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType, native_enum=False, length=20),
        nullable=False,
        default=EmploymentType.full_time,
        server_default=EmploymentType.full_time.value,
    )
    status: Mapped[TeacherStatus] = mapped_column(
        Enum(TeacherStatus, native_enum=False, length=20),
        nullable=False,
        default=TeacherStatus.active,
        server_default=TeacherStatus.active.value,
    )
    hire_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    hourly_rate: Mapped[float | None] = mapped_column(Numeric(10, 2))  # optional, see note below

    note: Mapped[str | None] = mapped_column(Text)  # staff-only
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    auth = relationship("Auth", foreign_keys=[auth_id], back_populates="teacher", uselist=False)
    created_by = relationship("Auth", foreign_keys="Teacher.created_by_id")
    updated_by = relationship("Auth", foreign_keys="Teacher.updated_by_id")

    __table_args__ = (
        Index("uq_teachers_email_lower", text("lower(email)"), unique=True),
        Index("uq_teachers_phone", "phone", unique=True,
              postgresql_where=text("phone IS NOT NULL")),
        Index("ix_teachers_status", "status"),
        Index("ix_teachers_name", "last_name", "first_name"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
