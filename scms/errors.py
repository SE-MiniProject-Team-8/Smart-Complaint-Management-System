"""Typed application errors mapped to the Section 4.8 error contract."""


class AppError(Exception):
    def __init__(self, status, code, message, fields=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields


def validation_error(fields):
    return AppError(422, "VALIDATION_ERROR", "Check the highlighted fields.", fields)


def not_found():
    # Same response for unknown and invisible records so existence is not disclosed.
    return AppError(404, "NOT_FOUND", "Resource not found.")


def forbidden(message="You are not permitted to perform this action."):
    return AppError(403, "FORBIDDEN", message)


def conflict(code, message):
    return AppError(409, code, message)


def persistence_unavailable():
    return AppError(503, "PERSISTENCE_UNAVAILABLE",
                    "The request could not be saved. Nothing was changed; please try again.")
