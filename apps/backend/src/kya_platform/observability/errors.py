"""Stable problem-detail responses that never expose internal exceptions."""

import logging
from dataclasses import dataclass
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHttpException

LOGGER = logging.getLogger("kya_platform.error")


class ProblemDetail(BaseModel):
    """RFC 9457-compatible failure envelope with stable KYA extensions."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ApiError(Exception):
    """Expected application failure with a public, stable error code."""

    status_code: int
    code: str
    title: str
    detail: str


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unavailable")


def _problem_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
) -> JSONResponse:
    problem = ProblemDetail(
        type=f"https://errors.kya-energy.com/{code}",
        title=title,
        status=status_code,
        detail=detail,
        instance=request.url.path,
        code=code,
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


async def api_error_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ApiError):
        raise TypeError("api_error_handler received an unexpected exception type") from error
    return _problem_response(
        request,
        status_code=error.status_code,
        code=error.code,
        title=error.title,
        detail=error.detail,
    )


async def validation_error_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise TypeError("validation_error_handler received an unexpected exception type") from error
    return _problem_response(
        request,
        status_code=422,
        code="request_validation_failed",
        title="Requête invalide",
        detail="La requête ne respecte pas le contrat attendu.",
    )


async def http_error_handler(request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, StarletteHttpException):
        raise TypeError("http_error_handler received an unexpected exception type") from error
    status_code = error.status_code
    try:
        title = HTTPStatus(status_code).phrase
    except ValueError:
        title = "HTTP error"
    return _problem_response(
        request,
        status_code=status_code,
        code=f"http_{status_code}",
        title=title,
        detail=title,
    )


async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
    LOGGER.exception(
        "request.failed",
        exc_info=error,
        extra={"correlation_id": _correlation_id(request)},
    )
    return _problem_response(
        request,
        status_code=500,
        code="internal_error",
        title="Erreur interne",
        detail="Une erreur interne est survenue.",
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHttpException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)


__all__ = ["ApiError", "ProblemDetail", "install_error_handlers"]
