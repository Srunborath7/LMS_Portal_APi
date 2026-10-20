from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.requests import Request


class AppException(HTTPException):
    """Base application exception."""

    default_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        detail: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            status_code=status_code or self.default_status_code,
            detail=detail or self.default_message,
            headers=headers,
        )


class NotFound(AppException):
    default_status_code = status.HTTP_404_NOT_FOUND
    default_message = "Resource not found."

    def __init__(self, what: str = "Resource", headers: dict[str, str] | None = None):
        super().__init__(detail=f"{what} not found", headers=headers)


class Conflict(AppException):
    default_status_code = status.HTTP_409_CONFLICT
    default_message = "Resource conflict."


class BadRequest(AppException):
    default_status_code = status.HTTP_400_BAD_REQUEST
    default_message = "Bad request."


class Unauthorized(AppException):
    default_status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "Invalid username or password."

    def __init__(self, detail: str | None = None, headers: dict[str, str] | None = None):
        super().__init__(
            detail=detail,
            headers={"WWW-Authenticate": "Bearer", **(headers or {})},
        )


class Forbidden(AppException):
    default_status_code = status.HTTP_403_FORBIDDEN
    default_message = "Access forbidden."


class ServiceUnavailable(AppException):
    default_status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "The requested service is temporarily unavailable."


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)