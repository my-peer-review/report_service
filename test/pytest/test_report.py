import pytest
import asyncio

from app.services.report_service import ReportService
from app.schemas.context import UserContext

# Fake repository con metodi minimi
class FakeReportRepo:
    async def get_report_assignments(self):
        return [{"teacherId": "t1", "assignments_aperti": 2, "assignments_completati": 3}]
    
    async def get_report_submissions(self):
        return [{"assignmentId": "a1", "teacherId": "t1", "submissions": 5}]
    
    async def get_report_reviews(self):
        return [{"studentId": "s1", "voto_medio": 7.5}]

@pytest.mark.asyncio
async def test_reports_with_supervisor():
    user = UserContext(user_id="u1", role="supervisore")
    repo = FakeReportRepo()

    assignments = await ReportService.assignments(user, repo)
    submissions = await ReportService.submissions(user, repo)
    reviews = await ReportService.reviews(user, repo)

    assert assignments[0]["teacherId"] == "t1"
    assert submissions[0]["submissions"] == 5
    assert reviews[0]["voto_medio"] == 7.5

@pytest.mark.asyncio
async def test_reports_forbidden_for_non_supervisor():
    user = UserContext(user_id="u2", role="studente")  # non supervisore
    repo = FakeReportRepo()

    with pytest.raises(PermissionError):
        await ReportService.assignments(user, repo)

    with pytest.raises(PermissionError):
        await ReportService.submissions(user, repo)

    with pytest.raises(PermissionError):
        await ReportService.reviews(user, repo)
