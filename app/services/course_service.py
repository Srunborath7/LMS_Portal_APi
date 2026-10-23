from __future__ import annotations

from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, Conflict, NotFound
from app.core.upload import remove_image, save_image
from app.domain.courses.model import Course, CourseStatus
from app.repositories.course_repositories import CourseRepository
from app.domain.courses.schema import CourseCreate, CourseFilter, CourseUpdate

# Columns declared nullable=False: PATCH must not set these to null
NOT_NULLABLE = {"name", "level", "language", "fee", "currency"}

# Allowed status changes
TRANSITIONS: dict[CourseStatus, set[CourseStatus]] = {
    CourseStatus.draft: {CourseStatus.published},
    CourseStatus.published: {CourseStatus.archived, CourseStatus.draft},
    CourseStatus.archived: {CourseStatus.published},
}


class CourseService:
    """Business rules for courses. Owns the transaction (commit / rollback)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CourseRepository(session)

    async def get(self, course_id: UUID) -> Course:
        course = await self.repo.get(course_id)
        if not course:
            raise NotFound("Course")
        return course

    async def list(self, filters: CourseFilter) -> tuple[list[Course], int]:
        if (
            filters.min_fee is not None
            and filters.max_fee is not None
            and filters.min_fee > filters.max_fee
        ):
            raise BadRequest("min_fee cannot be greater than max_fee")
        return await self.repo.list(filters)

    async def list_published(self) -> list[Course]:
        return await self.repo.list_published()

    async def categories(self) -> list[str]:
        return await self.repo.categories()

    async def create(self, data: CourseCreate) -> Course:
        await self._ensure_name_free(data.name)

        course = Course(
            **data.model_dump(),
            course_code=await self.repo.next_course_code(),
            status=CourseStatus.draft,  # always starts as draft
        )
        try:
            await self.repo.add(course)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise Conflict("A course with this name already exists")
        return course

    async def create_with_image(
        self, data: CourseCreate, upload: UploadFile | None = None
    ) -> Course:
        has_file = (
            upload is not None
            and bool(getattr(upload, "filename", None))
            and bool(upload.filename.strip())
        )
        new_url: str | None = None
        if has_file:
            new_url = await save_image(upload, "courses")
            data = data.model_copy(update={"thumbnail_url": new_url})
        try:
            return await self.create(data)
        except Exception:
            if new_url:
                await remove_image(new_url)
            raise

    async def update_with_image(
        self, course_id: UUID, data: CourseUpdate, upload: UploadFile | None = None
    ) -> Course:
        has_file = (
            upload is not None
            and bool(getattr(upload, "filename", None))
            and bool(upload.filename.strip())
        )
        if has_file:
            course = await self.get(course_id)
            if course.status == CourseStatus.archived:
                raise BadRequest("Archived courses cannot be edited. Publish it again first.")
            new_url = await save_image(upload, "courses")
            old_url = course.thumbnail_url
            data = data.model_copy(update={"thumbnail_url": new_url})
            try:
                updated = await self.update(course_id, data)
                if old_url and old_url != new_url:
                    await remove_image(old_url)
                return updated
            except Exception:
                if new_url:
                    await remove_image(new_url)
                raise
        return await self.update(course_id, data)

    async def set_image(self, course_id: UUID, upload: UploadFile) -> Course:
        course = await self.get(course_id)
        new_url = await save_image(upload, "courses")
        old_url = course.thumbnail_url
        try:
            await self.repo.update(course, {"thumbnail_url": new_url})
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await remove_image(new_url)
            raise
        if old_url and old_url != new_url:
            await remove_image(old_url)
        return course

    async def delete_image(self, course_id: UUID) -> Course:
        course = await self.get(course_id)
        old_url = course.thumbnail_url
        if old_url is None:
            return course
        await self.repo.update(course, {"thumbnail_url": None})
        await self.session.commit()
        await remove_image(old_url)
        return course

    async def update(self, course_id: UUID, data: CourseUpdate) -> Course:
        course = await self.get(course_id)
        if course.status == CourseStatus.archived:
            raise BadRequest("Archived courses cannot be edited. Publish it again first.")

        changes = data.model_dump(exclude_unset=True)

        for field in NOT_NULLABLE & changes.keys():
            if changes[field] is None:
                raise BadRequest(f"{field} cannot be null")

        if "name" in changes:
            await self._ensure_name_free(changes["name"], exclude_id=course.id)

        # A published course must stay publishable
        if course.status == CourseStatus.published:
            merged_description = changes.get("description", course.description)
            if not merged_description:
                raise BadRequest("A published course must keep its description")

        try:
            await self.repo.update(course, changes)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise Conflict("A course with this name already exists")
        return course

    async def publish(self, course_id: UUID) -> Course:
        course = await self.get(course_id)
        self._check_transition(course, CourseStatus.published)

        missing = []
        if not course.description:
            missing.append("description")
        if not course.duration_hours:
            missing.append("duration_hours")
        if missing:
            raise BadRequest(f"Cannot publish. Missing: {', '.join(missing)}")

        return await self._change_status(course, CourseStatus.published)

    async def unpublish(self, course_id: UUID) -> Course:
        """published -> draft. Blocked while classes are running."""
        course = await self.get(course_id)
        self._check_transition(course, CourseStatus.draft)
        await self._ensure_no_active_classes(course)
        return await self._change_status(course, CourseStatus.draft)

    async def archive(self, course_id: UUID) -> Course:
        """No new classes. Existing history is kept."""
        course = await self.get(course_id)
        self._check_transition(course, CourseStatus.archived)
        return await self._change_status(course, CourseStatus.archived)

    async def delete(self, course_id: UUID) -> None:
        course = await self.get(course_id)
        await self._ensure_no_active_classes(course)
        await self.repo.soft_delete(course)
        await self.session.commit()

    async def restore(self, course_id: UUID) -> Course:
        course = await self.repo.get(course_id, include_deleted=True)
        if not course:
            raise NotFound("Course")
        if course.deleted_at is None:
            return course

        # A live course may have taken the name while this one was deleted
        await self._ensure_name_free(course.name, exclude_id=course.id)

        try:
            await self.repo.restore(course)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise Conflict("A course with this name already exists")
        return course

    async def _change_status(self, course: Course, new_status: CourseStatus) -> Course:
        await self.repo.set_status(course, new_status)
        await self.session.commit()
        return course

    @staticmethod
    def _check_transition(course: Course, target: CourseStatus) -> None:
        if course.status == target:
            raise BadRequest(f"Course is already {target.value}")
        if target not in TRANSITIONS[course.status]:
            raise BadRequest(
                f"Cannot change status from {course.status.value} to {target.value}"
            )

    async def _ensure_name_free(self, name: str, exclude_id: UUID | None = None) -> None:
        """Friendly pre-check. The partial unique index remains the real guarantee."""
        other = await self.repo.get_by_name(name)
        if other and other.id != exclude_id:
            raise Conflict("A course with this name already exists")

    async def _ensure_no_active_classes(self, course: Course) -> None:
        """Hook: block when classes still use this course.

        Fill this in when the classes domain exists, for example:
            if await ClassRepository(self.session).count_active(course.id):
                raise Conflict("Course has active classes")
        """
        return None
    
    async def list_catalog(self, filters: CourseFilter) -> tuple[list[Course], int]:
        """Students only ever see published courses, whatever status they send."""
        return await self.list(filters.model_copy(update={"status": CourseStatus.published}))

    async def get_published(self, course_id: UUID) -> Course:
        course = await self.get(course_id)
        if course.status != CourseStatus.published:
            raise NotFound("Course")   # same 404 as a missing course, so drafts aren't revealed
        return course