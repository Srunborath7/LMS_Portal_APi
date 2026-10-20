from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, require_admin
from app.core.database import get_db
from app.domain.teachers.model import Teacher, TeacherStatus
from app.domain.teachers.schema import (
    TeacherCreate,
    TeacherFilter,
    TeacherOut,
    TeacherPage,
    TeacherUpdate,
)
from app.services.teacher_services import TeacherService


router = APIRouter(
    prefix="/teachers",
    tags=["teachers"],
    dependencies=[Depends(get_current_user_id)],
)


def get_service(db: AsyncSession = Depends(get_db)) -> TeacherService:
    return TeacherService(db)


Service = Annotated[TeacherService, Depends(get_service)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]


@router.get("/me", response_model=TeacherOut)
async def my_profile(user_id: CurrentUserId, svc: Service) -> Teacher:
    return await svc.get_by_auth_id(user_id)


@router.post("", response_model=TeacherOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_teacher(data: TeacherCreate, svc: Service) -> Teacher:
    return await svc.create(data)


@router.get("", response_model=TeacherPage, dependencies=[Depends(require_admin)])
async def list_teachers(
    filters: Annotated[TeacherFilter, Query()], svc: Service
) -> TeacherPage:
    items, total = await svc.list(filters)
    return TeacherPage(
        items=[TeacherOut.model_validate(item) for item in items],
        total=total,
        page=filters.page,
        size=filters.size,
    )


@router.get("/{teacher_id}", response_model=TeacherOut,
            dependencies=[Depends(require_admin)])
async def get_teacher(teacher_id: UUID, svc: Service) -> Teacher:
    return await svc.get(teacher_id)


@router.patch("/{teacher_id}", response_model=TeacherOut,
              dependencies=[Depends(require_admin)])
async def update_teacher(
    teacher_id: UUID, data: TeacherUpdate, svc: Service
) -> Teacher:
    return await svc.update(teacher_id, data)


@router.put("/{teacher_id}/image", response_model=TeacherOut,
            dependencies=[Depends(require_admin)])
async def upload_teacher_image(
    teacher_id: UUID, svc: Service, image: UploadFile = File(...)
) -> Teacher:
    return await svc.set_image(teacher_id, image)


@router.delete("/{teacher_id}/image", response_model=TeacherOut,
               dependencies=[Depends(require_admin)])
async def delete_teacher_image(teacher_id: UUID, svc: Service) -> Teacher:
    return await svc.delete_image(teacher_id)


@router.patch("/{teacher_id}/status", response_model=TeacherOut,
              dependencies=[Depends(require_admin)])
async def change_teacher_status(
    teacher_id: UUID,
    new_status: Annotated[TeacherStatus, Query(alias="status")],
    svc: Service,
) -> Teacher:
    return await svc.set_status(teacher_id, new_status)


@router.delete("/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_teacher(teacher_id: UUID, svc: Service) -> None:
    await svc.delete(teacher_id)


@router.post("/{teacher_id}/restore", response_model=TeacherOut,
             dependencies=[Depends(require_admin)])
async def restore_teacher(teacher_id: UUID, svc: Service) -> Teacher:
    return await svc.restore(teacher_id)
