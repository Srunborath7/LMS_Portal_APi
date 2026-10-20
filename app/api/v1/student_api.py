from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, require_staff
from app.core.database import get_db
from app.domain.students.model import Student, StudentStatus
from app.domain.students.schema import (
    StudentCreate,
    StudentFilter,
    StudentOut,
    StudentPage,
    StudentUpdate,
)
from app.services.student_services import StudentService

router = APIRouter(
    prefix="/students",
    tags=["students"],
    dependencies=[Depends(get_current_user_id)],  # sets the audit ContextVar
)


def get_service(db: AsyncSession = Depends(get_db)) -> StudentService:
    return StudentService(db)


Service = Annotated[StudentService, Depends(get_service)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]


# NOTE: /me must be declared BEFORE /{student_id}, or "me" is parsed as a UUID (422)
@router.get("/me", response_model=StudentOut)
async def my_profile(user_id: CurrentUserId, svc: Service) -> Student:
    """The logged-in student's own profile."""
    return await svc.get_by_auth_id(user_id)


@router.post(
    "",
    response_model=StudentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff)],
)
async def create_student(data: StudentCreate, svc: Service) -> Student:
    return await svc.create(data)


@router.get("", response_model=StudentPage, dependencies=[Depends(require_staff)])
async def list_students(
    filters: Annotated[StudentFilter, Query()], svc: Service
) -> StudentPage:
    items, total = await svc.list(filters)
    return StudentPage(
        items=[StudentOut.model_validate(student) for student in items],
        total=total,
        page=filters.page,
        size=filters.size,
    )


@router.get("/{student_id}", response_model=StudentOut, dependencies=[Depends(require_staff)])
async def get_student(student_id: UUID, svc: Service) -> Student:
    return await svc.get(student_id)


@router.patch("/{student_id}", response_model=StudentOut, dependencies=[Depends(require_staff)])
async def update_student(student_id: UUID, data: StudentUpdate, svc: Service) -> Student:
    return await svc.update(student_id, data)


@router.put("/{student_id}/image", response_model=StudentOut,
            dependencies=[Depends(require_staff)])
async def upload_student_image(
    student_id: UUID, svc: Service, image: UploadFile = File(...)
) -> Student:
    return await svc.set_image(student_id, image)


@router.delete("/{student_id}/image", response_model=StudentOut,
               dependencies=[Depends(require_staff)])
async def delete_student_image(student_id: UUID, svc: Service) -> Student:
    return await svc.delete_image(student_id)


@router.patch(
    "/{student_id}/status",
    response_model=StudentOut,
    dependencies=[Depends(require_staff)],
)
async def change_status(
    student_id: UUID,
    new_status: Annotated[StudentStatus, Query(alias="status")],
    svc: Service,
) -> Student:
    return await svc.set_status(student_id, new_status)


@router.delete(
    "/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_staff)],
)
async def delete_student(student_id: UUID, svc: Service):
    await svc.delete(student_id)


@router.post(
    "/{student_id}/restore",
    response_model=StudentOut,
    dependencies=[Depends(require_staff)],
)
async def restore_student(student_id: UUID, svc: Service) -> Student:
    return await svc.restore(student_id)
