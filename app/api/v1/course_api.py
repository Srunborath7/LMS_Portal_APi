from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, require_staff
from app.core.database import get_db
from app.domain.courses.schema import (
    CourseBrief,
    CourseCreate,
    CourseFilter,
    CourseOut,
    CoursePage,
    CoursePublic,
    CoursePublicPage,
    CourseUpdate,
)
from app.services.course_service import CourseService

router = APIRouter(prefix="/courses",tags=["courses"])
AuthDep = Depends(get_current_user_id)

def get_service(db: AsyncSession = Depends(get_db)) -> CourseService:
    return CourseService(db)

Service = Annotated[CourseService, Depends(get_service)]
Staff = Depends(require_staff)

# Fixed paths must be declared BEFORE /{course_id}, or "catalog" is parsed as a UUID (422).
@router.get("/catalog", response_model=CoursePublicPage)
async def catalog(filters: Annotated[CourseFilter, Query()], svc: Service):
    items, total = await svc.list_catalog(filters)
    return CoursePublicPage(
        items=[CoursePublic.model_validate(c) for c in items],
        total=total, page=filters.page, size=filters.size,
    )

@router.get("/catalog/{course_id}", response_model=CoursePublic)
async def catalog_detail(course_id: UUID, svc: Service):
    return await svc.get_published(course_id)

@router.get("/categories", response_model=list[str])
async def categories(svc: Service):
    return await svc.categories()

@router.get("/options", response_model=list[CourseBrief], dependencies=[Staff])
async def course_options(svc: Service):
    """Published courses for dropdowns, e.g. when creating a class."""
    return await svc.list_published()

@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED, dependencies=[Staff],)
async def create_course(data: CourseCreate, svc: Service):
    return await svc.create(data)

@router.get("", response_model=CoursePage, dependencies=[Staff])
async def list_courses(filters: Annotated[CourseFilter, Query()], svc: Service):
    items, total = await svc.list(filters)
    return CoursePage(
        items=[CourseOut.model_validate(c) for c in items],
        total=total, page=filters.page, size=filters.size,
    )

@router.get("/{course_id}", response_model=CourseOut, dependencies=[Staff])
async def get_course(course_id: UUID, svc: Service):
    return await svc.get(course_id)

@router.patch("/{course_id}", response_model=CourseOut, dependencies=[Staff])
async def update_course(course_id: UUID, data: CourseUpdate, svc: Service):
    return await svc.update(course_id, data)

@router.post("/{course_id}/publish", response_model=CourseOut, dependencies=[Staff])
async def publish_course(course_id: UUID, svc: Service):
    return await svc.publish(course_id)

@router.post("/{course_id}/unpublish", response_model=CourseOut, dependencies=[Staff])
async def unpublish_course(course_id: UUID, svc: Service):
    return await svc.unpublish(course_id)

@router.post("/{course_id}/archive", response_model=CourseOut, dependencies=[Staff])
async def archive_course(course_id: UUID, svc: Service):
    return await svc.archive(course_id)

@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Staff])
async def delete_course(course_id: UUID, svc: Service):
    await svc.delete(course_id)

@router.post("/{course_id}/restore", response_model=CourseOut, dependencies=[Staff])
async def restore_course(course_id: UUID, svc: Service):
    return await svc.restore(course_id)