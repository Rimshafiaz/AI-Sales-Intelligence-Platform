from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger, request_id_contextvar

logger = get_logger(__name__)

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    500: "internal_error",
    503: "service_unavailable",
}


def _error_response(
    code: str,
    message: str,
    status_code: int,
    details: list | None = None,
) -> JSONResponse:
    error_payload: dict = {
        "code": code,
        "message": message,
        "request_id": request_id_contextvar.get(),
    }
    if details is not None:
        error_payload["details"] = details

    return JSONResponse(
        status_code=status_code,
        content={"error": error_payload},
        headers={"X-Request-ID": request_id_contextvar.get()},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        logger.info("Request validation failed: %s", details)
        return _error_response(
            code="validation_error",
            message="Request validation failed.",
            status_code=422,
            details=details,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, f"http_{exc.status_code}")
        log_method = logger.warning if exc.status_code >= 500 else logger.info
        log_method("HTTP %s: %s", exc.status_code, exc.detail)
        return _error_response(
            code=code,
            message=str(exc.detail),
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return _error_response(
            code="internal_error",
            message="An unexpected error occurred. Please try again.",
            status_code=500,
        )
