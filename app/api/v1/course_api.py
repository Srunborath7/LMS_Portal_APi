from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, require_staff
from app.core.database import get_db
from app.core.exceptions import BadRequest
from app.domain.courses.model import CourseLevel
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

@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED, dependencies=[Staff])
async def create_course(
    svc: Service,
    name: str = Form(...),
    description: str | None = Form(None),
    objectives: str | None = Form(None),
    category: str | None = Form(None),
    level: CourseLevel = Form(CourseLevel.all_levels),
    language: str = Form("en"),
    duration_hours: str | None = Form(None),
    fee: str = Form("0"),
    currency: str = Form("USD"),
    thumbnail_url: str | None = Form(None),
    image: UploadFile | None = File(None),
):
    parsed_duration: Decimal | None = None
    if duration_hours and duration_hours.strip():
        try:
            parsed_duration = Decimal(duration_hours.strip())
        except Exception:
            raise BadRequest("duration_hours must be a valid number")

    parsed_fee = Decimal("0")
    if fee and fee.strip():
        try:
            parsed_fee = Decimal(fee.strip())
        except Exception:
            raise BadRequest("fee must be a valid number")

    clean_description = description.strip() if description and description.strip() else None
    clean_objectives = objectives.strip() if objectives and objectives.strip() else None
    clean_category = category.strip() if category and category.strip() else None
    clean_thumbnail_url = thumbnail_url.strip() if thumbnail_url and thumbnail_url.strip() else None

    course_data = CourseCreate(
        name=name.strip(),
        description=clean_description,
        objectives=clean_objectives,
        category=clean_category,
        level=level,
        language=language.strip(),
        duration_hours=parsed_duration,
        fee=parsed_fee,
        currency=currency.strip(),
        thumbnail_url=clean_thumbnail_url,
    )
    return await svc.create_with_image(course_data, image)

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
async def update_course(
    course_id: UUID,
    svc: Service,
    request: Request,
    name: str | None = Form(None),
    description: str | None = Form(None),
    objectives: str | None = Form(None),
    category: str | None = Form(None),
    level: CourseLevel | None = Form(None),
    language: str | None = Form(None),
    duration_hours: str | None = Form(None),
    fee: str | None = Form(None),
    currency: str | None = Form(None),
    thumbnail_url: str | None = Form(None),
    image: UploadFile | None = File(None),
):
    form_data = await request.form()
    updates: dict = {}

    if "name" in form_data:
        clean_name = name.strip() if name and name.strip() else None
        if clean_name is None:
            raise BadRequest("name cannot be null or empty")
        updates["name"] = clean_name

    if "description" in form_data:
        updates["description"] = description.strip() if description and description.strip() else None

    if "objectives" in form_data:
        updates["objectives"] = objectives.strip() if objectives and objectives.strip() else None

    if "category" in form_data:
        updates["category"] = category.strip() if category and category.strip() else None

    if "level" in form_data:
        if level is None:
            raise BadRequest("level cannot be null")
        updates["level"] = level

    if "language" in form_data:
        clean_lang = language.strip() if language and language.strip() else None
        if clean_lang is None:
            raise BadRequest("language cannot be null or empty")
        updates["language"] = clean_lang

    if "duration_hours" in form_data:
        if duration_hours is not None and duration_hours.strip():
            try:
                updates["duration_hours"] = Decimal(duration_hours.strip())
            except Exception:
                raise BadRequest("duration_hours must be a valid number")
        else:
            updates["duration_hours"] = None

    if "fee" in form_data:
        if fee is not None and fee.strip():
            try:
                updates["fee"] = Decimal(fee.strip())
            except Exception:
                raise BadRequest("fee must be a valid number")
        else:
            raise BadRequest("fee cannot be null")

    if "currency" in form_data:
        clean_curr = currency.strip() if currency and currency.strip() else None
        if clean_curr is None:
            raise BadRequest("currency cannot be null or empty")
        updates["currency"] = clean_curr

    if "thumbnail_url" in form_data:
        updates["thumbnail_url"] = thumbnail_url.strip() if thumbnail_url and thumbnail_url.strip() else None

    course_data = CourseUpdate(**updates)
    return await svc.update_with_image(course_id, course_data, image)

@router.put("/{course_id}/image", response_model=CourseOut, dependencies=[Staff])
async def upload_course_image(
    course_id: UUID, svc: Service, image: UploadFile = File(...)
):
    return await svc.set_image(course_id, image)

@router.delete("/{course_id}/image", response_model=CourseOut, dependencies=[Staff])
async def delete_course_image(course_id: UUID, svc: Service):
    return await svc.delete_image(course_id)

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