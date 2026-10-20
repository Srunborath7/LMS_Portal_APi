from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import Select, Sequence, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.students.model import Student
from app.domain.students.schema import StudentFilter

student_code_seq = Sequence("student_code_seq", metadata=Student.metadata)


def _like(q: str) -> str:
    """Escape LIKE wildcards so user input like '50%' is matched literally."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class StudentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _base(self, include_deleted: bool = False) -> Select:
        stmt = select(Student)
        if not include_deleted:
            stmt = stmt.where(Student.deleted_at.is_(None))
        return stmt

    async def get(self, student_id: UUID, include_deleted: bool = False) -> Student | None:
        stmt = self._base(include_deleted).where(Student.id == student_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str, include_deleted: bool = True) -> Student | None:
        stmt = self._base(include_deleted).where(func.lower(Student.email) == email.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_phone(self, phone: str, include_deleted: bool = True) -> Student | None:
        stmt = self._base(include_deleted).where(Student.phone == phone)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_auth_id(self, auth_id: UUID, include_deleted: bool = True) -> Student | None:
        stmt = self._base(include_deleted).where(Student.auth_id == auth_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, f: StudentFilter) -> tuple[list[Student], int]:
        stmt = self._base()

        if f.status:
            stmt = stmt.where(Student.status == f.status)
        if f.gender:
            stmt = stmt.where(Student.gender == f.gender)
        if f.q:
            pattern = _like(f.q.strip())
            full_name = func.concat(Student.first_name, " ", Student.last_name)
            stmt = stmt.where(
                or_(
                    full_name.ilike(pattern, escape="\\"),
                    Student.email.ilike(pattern, escape="\\"),
                    Student.student_code.ilike(pattern, escape="\\"),
                    Student.phone.ilike(pattern, escape="\\"),
                )
            )

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )

        stmt = (
            stmt.order_by(Student.last_name, Student.first_name, Student.id)  # id = stable paging
            .offset((f.page - 1) * f.size)
            .limit(f.size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total or 0

    async def next_student_code(self) -> str:
        n = await self.session.scalar(select(student_code_seq.next_value()))
        return f"STU-{date.today().year}-{n:06d}"

    async def add(self, student: Student) -> Student:
        self.session.add(student)
        await self.session.flush()
        await self.session.refresh(student)  # load server defaults (created_at, ...)
        return student

    async def update(self, student: Student, changes: dict) -> Student:
        for key, value in changes.items():
            setattr(student, key, value)
        await self.session.flush()
        await self.session.refresh(student)  # load the new updated_at
        return student

    async def soft_delete(self, student: Student) -> None:
        student.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def restore(self, student: Student) -> Student:
        student.deleted_at = None
        await self.session.flush()
        await self.session.refresh(student)
        return student
