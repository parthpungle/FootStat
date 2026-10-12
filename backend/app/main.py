"""FootStat FastAPI application.

Run from the backend/ directory:

    uvicorn app.main:app --reload --port 8000
"""

import math
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.services.data_store import load_store

FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _json_safe(value):
    """Replace NaN/Infinity (not valid JSON) with their string form."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default handler echoes the offending input, which crashes with
    # a 500 when that input is NaN or Infinity.
    return JSONResponse({"detail": _json_safe(jsonable_encoder(exc.errors()))}, status_code=422)


def create_app(**store_paths) -> FastAPI:
    """Build the app. store_paths override file locations (used by tests)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = load_store(**store_paths)
        yield

    app = FastAPI(title="FootStat API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=FRONTEND_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(router)
    return app


app = create_app()
