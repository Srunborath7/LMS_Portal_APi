from __future__ import annotations

import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.audit import AuditMixin
from app.core.base import Base


class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"

class StudentStatus(str, enum.Enum):
    prospect = "prospect"
    active = "active"
    suspended = "suspended"
    graduated = "graduated"
    withdrawn = "withdrawn"


class Student(AuditMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("auth_id", name="uq_students_auth_id"),
        UniqueConstraint("student_code", name="uq_students_student_code"),
        Index("uq_students_email_lower", text("lower(email)"), unique=True),
        Index(
            "uq_students_phone",
            "phone",
            unique=True,
            postgresql_where=text("phone IS NOT NULL"),
        ),
        Index("ix_students_status", "status"),
        Index("ix_students_name", "last_name", "first_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    auth_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("auths.id", ondelete="SET NULL"), nullable=True)
    student_code: Mapped[str] = mapped_column(String(20), nullable=False)
    # Personal
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender, native_enum=False, length=20))
    # Contact
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))  # E.164
    address: Mapped[str | None] = mapped_column(Text)
    # Guardian
    guardian_name: Mapped[str | None] = mapped_column(String(150))
    guardian_phone: Mapped[str | None] = mapped_column(String(20))
    # Lifecycle
    status: Mapped[StudentStatus] = mapped_column(
        Enum(StudentStatus, native_enum=False, length=20),
        nullable=False,
        default=StudentStatus.active,
        server_default=StudentStatus.active.value,
    )
    enrolled_at: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Relationships (foreign_keys is required: 3 FKs point to auths)
    auth = relationship("Auth", foreign_keys=[auth_id], back_populates="student", uselist=False)
    created_by = relationship("Auth", foreign_keys="Student.created_by_id")
    updated_by = relationship("Auth", foreign_keys="Student.updated_by_id")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        t = date.today()
        return t.year - self.date_of_birth.year - (
            (t.month, t.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
