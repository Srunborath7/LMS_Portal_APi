from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import Select, Sequence, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.courses.model import Course, CourseStatus
from app.domain.courses.schema import CourseFilter

course_code_seq = Sequence("course_code_seq")

def _like(q: str) -> str:
    """Escape LIKE wildcards so input like '50%' is matched literally."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"

class CourseRepository:
    """Persists and queries courses. Never commits: the service owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base(self, include_deleted: bool = False) -> Select:
        stmt = select(Course)
        if not include_deleted:
            stmt = stmt.where(Course.deleted_at.is_(None))
        return stmt

    async def get(self, course_id: UUID, include_deleted: bool = False) -> Course | None:
        stmt = self._base(include_deleted).where(Course.id == course_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, course_code: str) -> Course | None:
        stmt = self._base().where(Course.course_code == course_code)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_name(self, name: str) -> Course | None:
        """Only live courses: the unique index on lower(name) ignores deleted rows."""
        stmt = self._base().where(func.lower(Course.name) == name.strip().lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, f: CourseFilter) -> tuple[list[Course], int]:
        stmt = self._base()

        if f.status:
            stmt = stmt.where(Course.status == f.status)
        if f.level:
            stmt = stmt.where(Course.level == f.level)
        if f.category:
            stmt = stmt.where(func.lower(Course.category) == f.category.strip().lower())
        if f.language:
            stmt = stmt.where(Course.language == f.language.strip().lower())
        if f.min_fee is not None:
            stmt = stmt.where(Course.fee >= f.min_fee)
        if f.max_fee is not None:
            stmt = stmt.where(Course.fee <= f.max_fee)
        if f.q:
            pattern = _like(f.q.strip())
            stmt = stmt.where(
                or_(
                    Course.name.ilike(pattern, escape="\\"),
                    Course.course_code.ilike(pattern, escape="\\"),
                    Course.category.ilike(pattern, escape="\\"),
                )
            )

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )

        stmt = (
            stmt.order_by(Course.name, Course.id)  # id = stable paging
            .offset((f.page - 1) * f.size)
            .limit(f.size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total or 0

    async def list_published(self) -> list[Course]:
        """For dropdowns, e.g. when creating a class."""
        stmt = (
            self._base()
            .where(Course.status == CourseStatus.published)
            .order_by(Course.name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def categories(self) -> list[str]:
        """Distinct categories for filter dropdowns."""
        stmt = (
            select(Course.category)
            .where(Course.deleted_at.is_(None), Course.category.is_not(None))
            .distinct()
            .order_by(Course.category)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def next_course_code(self) -> str:
        n = await self.session.scalar(select(course_code_seq.next_value()))
        return f"CRS-{date.today().year}-{n:06d}"

    async def add(self, course: Course) -> Course:
        self.session.add(course)
        await self.session.flush()
        await self.session.refresh(course)  # server defaults + joined audit users
        return course

    async def update(self, course: Course, changes: dict) -> Course:
        for key, value in changes.items():
            setattr(course, key, value)
        await self.session.flush()
        await self.session.refresh(course)  # new updated_at
        return course

    async def set_status(self, course: Course, status: CourseStatus) -> Course:
        course.status = status
        if status == CourseStatus.published and course.published_at is None:
            course.published_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(course)
        return course

    async def soft_delete(self, course: Course) -> None:
        course.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def restore(self, course: Course) -> Course:
        course.deleted_at = None
        await self.session.flush()
        await self.session.refresh(course)
        return course