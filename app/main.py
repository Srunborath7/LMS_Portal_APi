
from fastapi import FastAPI

app = FastAPI(title="My First API")


@app.get("/")
async def root():
    return {"message": "Hello, FastAPI!"}


@app.get("/hello")
async def hello():
    return {"message": "Welcome to FastAPI"}
