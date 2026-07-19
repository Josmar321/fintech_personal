from fastapi import HTTPException, status


class AppException(HTTPException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Internal server error"

    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=self.status_code,
            detail=detail or self.detail,
        )


class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class UnauthorizedError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Not authenticated"

    def __init__(self, detail: str | None = None):
        super().__init__(detail=detail)
        self.headers = {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Forbidden"


class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource conflict"


class ValidationError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation failed"
