from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, Conflict, NotFound
from app.domain.auths.model import AuthRole
from app.domain.teachers.model import Teacher, TeacherStatus
from app.domain.teachers.schema import TeacherCreate, TeacherFilter, TeacherUpdate
from app.repositories.teacher_repositories import TeacherRepository


NOT_NULLABLE = {
    "first_name", "last_name", "email", "teacher_code", "employment_type", "status"
}


class TeacherService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TeacherRepository(session)

    async def get(self, teacher_id: UUID) -> Teacher:
        teacher = await self.repo.get(teacher_id)
        if teacher is None:
            raise NotFound("Teacher")
        return teacher

    async def get_by_auth_id(self, auth_id: UUID) -> Teacher:
        teacher = await self.repo.get_by_user_id(auth_id)
        if teacher is None:
            raise NotFound("Teacher profile")
        return teacher

    async def list(self, filters: TeacherFilter) -> tuple[list[Teacher], int]:
        return await self.repo.list(filters)

    async def create(self, data: TeacherCreate) -> Teacher:
        await self._validate_relations(email=data.email, phone=data.phone, auth_id=data.auth_id)
        teacher = Teacher(
            **data.model_dump(),
            teacher_code=await self.repo.next_teacher_code(),
        )
        try:
            await self.repo.add(teacher)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise Conflict("Teacher email, phone or account is already in use") from exc
        return teacher

    async def update(self, teacher_id: UUID, data: TeacherUpdate) -> Teacher:
        teacher = await self.get(teacher_id)
        changes = data.model_dump(exclude_unset=True)
        for field in NOT_NULLABLE.intersection(changes):
            if changes[field] is None:
                raise BadRequest(f"{field} cannot be null")

        if "hire_date" in changes or "end_date" in changes:
            hire_date = changes.get("hire_date", teacher.hire_date)
            end_date = changes.get("end_date", teacher.end_date)
            if hire_date and end_date and end_date < hire_date:
                raise BadRequest("end_date cannot be before hire_date")

        await self._validate_relations(
            email=changes.get("email"),
            phone=changes.get("phone"),
            exclude_id=teacher.id,
        )
        try:
            await self.repo.update(teacher, changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise Conflict("Teacher email or phone is already in use") from exc
        return teacher

    async def set_status(self, teacher_id: UUID, new_status: TeacherStatus) -> Teacher:
        return await self.update(teacher_id, TeacherUpdate(status=new_status))

    async def delete(self, teacher_id: UUID) -> None:
        teacher = await self.get(teacher_id)
        await self.repo.soft_delete(teacher)
        await self.session.commit()

    async def restore(self, teacher_id: UUID) -> Teacher:
        teacher = await self.repo.get(teacher_id, include_deleted=True)
        if teacher is None:
            raise NotFound("Teacher")
        if teacher.deleted_at is None:
            return teacher
        await self._validate_relations(
            email=teacher.email, phone=teacher.phone, exclude_id=teacher.id
        )
        try:
            await self.repo.restore(teacher)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise Conflict("Teacher email or phone is already in use") from exc
        return teacher

    async def _validate_relations(
        self,
        *,
        email: str | None = None,
        phone: str | None = None,
        auth_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> None:
        if email:
            existing = await self.repo.get_by_email(email)
            if existing and existing.id != exclude_id:
                raise Conflict("A teacher with this email already exists")
        if phone:
            existing = await self.repo.get_by_phone(phone)
            if existing and existing.id != exclude_id:
                raise Conflict("A teacher with this phone already exists")
        if auth_id:
            auth = await self.repo.get_auth(auth_id)
            if auth is None or not auth.is_active:
                raise BadRequest("auth_id must reference an active account")
            if auth.role != AuthRole.teacher:
                raise BadRequest("Linked account must have the teacher role")
            existing = await self.repo.get_by_auth_id(auth_id)
            if existing and existing.id != exclude_id:
                raise Conflict("This account is already linked to a teacher")
