import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .errors import AppError
from .routers import chat

logger = logging.getLogger(__name__)

app = FastAPI(title="Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def app_error_handler(request: Request, exc: AppError):
    if exc.status_code >= 500:
        logger.error("AppError %s: %s", exc.code, exc.message, exc_info=exc.__cause__ or exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(chat.router)
