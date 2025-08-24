from fastapi import Request
from app.database.report_repository import ReportRepository

def get_repository(request: Request) -> ReportRepository:
    repo = getattr(request.app.state, "report_repo", None)
    if repo is None:
        raise RuntimeError("Repository Review non inizializzato")
    return repo