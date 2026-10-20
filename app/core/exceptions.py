from typing import Any
from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application exception supporting clean OOP hierarchy."""

    default_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        detail: str | None = None,
        status_code: int | None = None,
        headers: dict[str, Any] | None = None,
    ):
        super().__init__(
            status_code=status_code or self.default_status_code,
            detail=detail or self.default_message,
            headers=headers,
        )


class NotFound(AppException):
    default_status_code = status.HTTP_404_NOT_FOUND
    default_message = "Resource not found."

    def __init__(self, what: str = "Resource", headers: dict[str, Any] | None = None):
        super().__init__(detail=f"{what} not found", headers=headers)


class Conflict(AppException):
    default_status_code = status.HTTP_409_CONFLICT
    default_message = "Resource conflict."

    def __init__(self, detail: str = "Resource conflict.", headers: dict[str, Any] | None = None):
        super().__init__(detail=detail, headers=headers)


class BadRequest(AppException):
    default_status_code = status.HTTP_400_BAD_REQUEST
    default_message = "Bad request."

    def __init__(self, detail: str = "Bad request.", headers: dict[str, Any] | None = None):
        super().__init__(detail=detail, headers=headers)


class Unauthorized(AppException):
    default_status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "Invalid username or password"

    def __init__(
        self,
        message: str = "Invalid username or password",
        headers: dict[str, Any] | None = None,
    ):
        auth_headers = {"WWW-Authenticate": "Bearer"}
        if headers:
            auth_headers.update(headers)
        super().__init__(detail=message, headers=auth_headers)


class Forbidden(AppException):
    default_status_code = status.HTTP_403_FORBIDDEN
    default_message = "Access forbidden."

    def __init__(self, detail: str = "Access forbidden.", headers: dict[str, Any] | None = None):
        super().__init__(detail=detail, headers=headers)


class ServiceUnavailable(AppException):
    default_status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "The requested service is temporarily unavailable."
