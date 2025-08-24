# app/services/report_service.py
from typing import Sequence
from app.schemas.context import UserContext
from app.database.report_repository import ReportRepository

def is_supervisor(role: str) -> bool:
    return role == "supervisore"

class ReportService:
    @staticmethod
    async def assignments(user: UserContext, repo: ReportRepository) -> Sequence[dict]:
        if not is_supervisor(user.role):
            raise PermissionError("Solo i supervisori possono accedere ai report")
        return await repo.get_report_assignments()

    @staticmethod
    async def submissions(user: UserContext, repo: ReportRepository) -> Sequence[dict]:
        if not is_supervisor(user.role):
            raise PermissionError("Solo i supervisori possono accedere ai report")
        return await repo.get_report_submissions()

    @staticmethod
    async def reviews(user: UserContext, repo: ReportRepository) -> Sequence[dict]:
        if not is_supervisor(user.role):
            raise PermissionError("Solo i supervisori possono accedere ai report")
        return await repo.get_report_reviews()
