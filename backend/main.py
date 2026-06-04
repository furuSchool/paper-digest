import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from database import init_db
from routers import sources, digest, auth


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    yield


app = FastAPI(title="Paper Digest API", lifespan=lifespan)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router)
app.include_router(digest.router)
app.include_router(auth.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
