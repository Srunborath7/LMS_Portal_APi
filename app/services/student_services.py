from __future__ import annotations

from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, Conflict, NotFound
from app.core.upload import remove_image, save_image
from app.domain.students.model import Student, StudentStatus
from app.repositories.student_repositories import StudentRepository
from app.domain.students.schema import StudentCreate, StudentFilter, StudentUpdate

# Columns declared nullable=False: PATCH must not set these to null
NOT_NULLABLE = {"first_name", "last_name", "email", "status"}


class StudentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = StudentRepository(session)

    async def get(self, student_id: UUID) -> Student:
        student = await self.repo.get(student_id)
        if not student:
            raise NotFound("Student not found")
        return student

    async def get_by_auth_id(self, auth_id: UUID) -> Student:
        student = await self.repo.get_by_auth_id(auth_id, include_deleted=False)
        if student is None:
            raise NotFound("Student profile")
        return student

    async def list(self, filters: StudentFilter) -> tuple[list[Student], int]:
        return await self.repo.list(filters)

    async def create(self, data: StudentCreate) -> Student:
        await self._ensure_unique(email=data.email, phone=data.phone, auth_id=data.auth_id)

        student = Student(
            **data.model_dump(),
            student_code=await self.repo.next_student_code(),
        )
        try:
            await self.repo.add(student)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            # Lost a race with a concurrent request; the DB constraint caught it
            raise Conflict("Email, phone or account is already in use")
        return student

    async def update(self, student_id: UUID, data: StudentUpdate) -> Student:
        student = await self.get(student_id)
        changes = data.model_dump(exclude_unset=True)

        for field in NOT_NULLABLE & changes.keys():
            if changes[field] is None:
                raise BadRequest(f"{field} cannot be null")

        await self._ensure_unique(
            email=changes.get("email"),
            phone=changes.get("phone"),
            exclude_id=student.id,
        )

        try:
            await self.repo.update(student, changes)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise Conflict("Email or phone is already in use")
        return student

    async def delete(self, student_id: UUID) -> None:
        student = await self.get(student_id)
        await self.repo.soft_delete(student)
        await self.session.commit()

    async def restore(self, student_id: UUID) -> Student:
        student = await self.repo.get(student_id, include_deleted=True)
        if not student:
            raise NotFound("Student not found")
        if student.deleted_at is None:
            return student
        await self._ensure_unique(
            email=student.email, phone=student.phone, exclude_id=student.id
        )
        try:
            await self.repo.restore(student)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise Conflict("Email or phone is already in use") from exc
        return student

    async def set_status(self, student_id: UUID, new_status: StudentStatus) -> Student:
        return await self.update(student_id, StudentUpdate(status=new_status))

    async def set_image(self, student_id: UUID, upload: UploadFile) -> Student:
        student = await self.get(student_id)
        new_url = await save_image(upload, "students")
        old_url = student.image_url
        try:
            await self.repo.update(student, {"image_url": new_url})
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await remove_image(new_url)
            raise
        if old_url and old_url != new_url:
            await remove_image(old_url)
        return student

    async def delete_image(self, student_id: UUID) -> Student:
        student = await self.get(student_id)
        old_url = student.image_url
        if old_url is None:
            return student
        await self.repo.update(student, {"image_url": None})
        await self.session.commit()
        await remove_image(old_url)
        return student

    async def _ensure_unique(
        self,
        *,
        email: str | None = None,
        phone: str | None = None,
        auth_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> None:
        """Friendly pre-check. The DB unique indexes remain the real guarantee."""
        if email:
            other = await self.repo.get_by_email(email)
            if other and other.id != exclude_id:
                raise Conflict("A student with this email already exists")
        if phone:
            other = await self.repo.get_by_phone(phone)
            if other and other.id != exclude_id:
                raise Conflict("A student with this phone already exists")
        if auth_id:
            other = await self.repo.get_by_auth_id(auth_id)
            if other and other.id != exclude_id:
                raise Conflict("This account is already linked to a student")
