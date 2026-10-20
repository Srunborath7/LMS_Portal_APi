
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.v1.auth_api import router as auth_router


app = FastAPI(title="LMS PORTAL")
app.include_router(auth_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Hello, FastAPI!"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT 1"))
    return {"status": "ok", "result": result.scalar()}
