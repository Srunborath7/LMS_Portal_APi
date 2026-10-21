from fastapi import APIRouter

from app.api.v1.auth_api import router as auth_router
from app.api.v1.student_api import router as student_router
from app.api.v1.teacher_api import router as teacher_router
from app.api.v1.course_api import router as course_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(student_router)
api_router.include_router(teacher_router)
api_router.include_router(course_router)
