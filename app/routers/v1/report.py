# app/api/report.py
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.deps import get_repository
from app.database.report_repository import ReportRepository
from app.services.report_service import ReportService
from app.schemas.context import UserContext
from app.services.auth_service import AuthService

router = APIRouter()
ReportRepoDep = Annotated[ReportRepository, Depends(get_repository)]
UserDep = Annotated[UserContext, Depends(AuthService.get_current_user)]

@router.get("/report/assignments")
async def report_assignments(user: UserDep, repo: ReportRepoDep):
    try:
        return await ReportService.assignments(user, repo)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.get("/report/submissions")
async def report_submissions(user: UserDep, repo: ReportRepoDep):
    try:
        return await ReportService.submissions(user, repo)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.get("/report/reviews")
async def report_reviews(user: UserDep, repo: ReportRepoDep):
    try:
        return await ReportService.reviews(user, repo)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
