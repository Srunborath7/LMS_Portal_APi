from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.router import api_router
from app.core.database import engine, get_db
from app.core.exceptions import register_exception_handlers
from app.core.upload import get_upload_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="LMS Portal API", lifespan=lifespan)
register_exception_handlers(app)
app.mount("/uploads", StaticFiles(directory=str(get_upload_dir()), check_dir=False), name="uploads")
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "LMS Portal API is running"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict[str, int | str]:
    result = await db.execute(text("SELECT 1"))
    return {"status": "ok", "result": result.scalar_one()}
