from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import Sequence, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auths.model import Auth
from app.domain.teachers.model import Teacher
from app.domain.teachers.schema import TeacherFilter


teacher_code_seq = Sequence("teacher_code_seq", metadata=Teacher.metadata)


def _like(value: str) -> str:
    value = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{value}%"


class TeacherRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base(self, include_deleted: bool = False) -> Select:
        stmt = select(Teacher)
        if not include_deleted:
            stmt = stmt.where(Teacher.deleted_at.is_(None))
        return stmt

    async def get(self, teacher_id: UUID, *, include_deleted: bool = False) -> Teacher | None:
        result = await self.session.execute(
            self._base(include_deleted).where(Teacher.id == teacher_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Teacher | None:
        result = await self.session.execute(
            self._base(include_deleted=True).where(func.lower(Teacher.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> Teacher | None:
        result = await self.session.execute(
            self._base(include_deleted=True).where(Teacher.phone == phone)
        )
        return result.scalar_one_or_none()

    async def get_by_auth_id(self, auth_id: UUID) -> Teacher | None:
        result = await self.session.execute(
            self._base(include_deleted=True).where(Teacher.auth_id == auth_id)
        )
        return result.scalar_one_or_none()

    async def get_auth(self, auth_id: UUID) -> Auth | None:
        return await self.session.get(Auth, auth_id)

    async def get_by_user_id(self, auth_id: UUID) -> Teacher | None:
        result = await self.session.execute(
            self._base().where(Teacher.auth_id == auth_id)
        )
        return result.scalar_one_or_none()

    async def list(self, filters: TeacherFilter) -> tuple[list[Teacher], int]:
        stmt = self._base()
        if filters.status:
            stmt = stmt.where(Teacher.status == filters.status)
        if filters.employment_type:
            stmt = stmt.where(Teacher.employment_type == filters.employment_type)
        if filters.specialization:
            stmt = stmt.where(Teacher.specialization.ilike(_like(filters.specialization.strip()), escape="\\"))
        if filters.q:
            pattern = _like(filters.q.strip())
            full_name = func.concat(Teacher.first_name, " ", Teacher.last_name)
            stmt = stmt.where(or_(
                full_name.ilike(pattern, escape="\\"),
                Teacher.email.ilike(pattern, escape="\\"),
                Teacher.teacher_code.ilike(pattern, escape="\\"),
                Teacher.phone.ilike(pattern, escape="\\"),
            ))

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        stmt = (
            stmt.order_by(Teacher.last_name, Teacher.first_name, Teacher.id)
            .offset((filters.page - 1) * filters.size)
            .limit(filters.size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total or 0

    async def next_teacher_code(self) -> str:
        number = await self.session.scalar(select(teacher_code_seq.next_value()))
        return f"TCH-{date.today().year}-{number:06d}"

    async def add(self, teacher: Teacher) -> Teacher:
        self.session.add(teacher)
        await self.session.flush()
        await self.session.refresh(teacher)
        return teacher

    async def update(self, teacher: Teacher, changes: dict) -> Teacher:
        for field, value in changes.items():
            setattr(teacher, field, value)
        await self.session.flush()
        await self.session.refresh(teacher)
        return teacher

    async def soft_delete(self, teacher: Teacher) -> None:
        teacher.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def restore(self, teacher: Teacher) -> Teacher:
        teacher.deleted_at = None
        await self.session.flush()
        await self.session.refresh(teacher)
        return teacher
