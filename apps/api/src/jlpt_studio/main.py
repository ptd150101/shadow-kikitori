from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from jlpt_studio.api.router import router
from jlpt_studio.core.config import get_settings
from jlpt_studio.core.errors import StudioError
from jlpt_studio.core.logging import configure_logging
from jlpt_studio.db.init import initialize_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    initialize_database()
    yield


app = FastAPI(
    title="JLPT Listening Studio API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(StudioError)
async def studio_error_handler(_request: Request, error: StudioError) -> JSONResponse:
    response = JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "message": error.message, "detail": error.detail},
    )
    response.headers["X-Request-ID"] = getattr(_request.state, "request_id", "")
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request.state.request_id = request.headers.get("X-Request-ID") or uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response
