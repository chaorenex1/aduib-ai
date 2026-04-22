from sqlalchemy.orm import Session


class BaseServiceError(ValueError):
    status_code = 500
    code = "service_error"

    def __init__(
        self,
        description: str | None = None,
        *,
        status_code: int | None = None,
        code: str | None = None,
        details: dict | None = None,
    ):
        message = description or "service error"
        super().__init__(message)
        self.description = message
        self.status_code = status_code or self.status_code
        self.code = code or self.code
        self.details = details or {}


class RepositoryBase:
    @staticmethod
    def commit_and_refresh(session: Session, entity):
        session.commit()
        session.refresh(entity)
        return entity
