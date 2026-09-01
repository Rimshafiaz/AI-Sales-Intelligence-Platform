import time
import uuid

from fastapi import FastAPI, Request

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger, request_id_contextvar
from app.api.routes.users import router as user_router
from app.api.routes.companies import router as company_router
from app.api.routes.research_requests import router as research_requests_router
from app.api.routes.reports import router as reports_router
from app.api.routes.company_discovery import router as company_discovery_router
from app.api.routes.dashboard import router as dashboard_router

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title = settings.app_name,
    version = settings.app_version,
)
app.include_router(user_router)
app.include_router(company_router)
app.include_router(research_requests_router)
app.include_router(reports_router)
app.include_router(company_discovery_router)
app.include_router(dashboard_router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = uuid.uuid4().hex
    request_id_contextvar.set(request_id)

    started = time.perf_counter()
    status_code = "-"
    try:
        response = await call_next(request)
        status_code = response.status_code
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "%s %s -> %s (%.0f ms)",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )

    response.headers["X-Request-ID"] = request_id
    return response


register_exception_handlers(app)


@app.get("/")
def root():
    return {"message" : "Welcome to AI Sales Intelligence Platform"}

@app.get("/health")
def health():
    return {"status" : "healthy"}