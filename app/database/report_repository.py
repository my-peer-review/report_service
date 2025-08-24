from __future__ import annotations
from datetime import datetime
from abc import ABC, abstractmethod

class ReportRepository(ABC):

    @abstractmethod
    async def insert_teacher_assignment(self, *, assignment_id: str, teacher_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def insert_assignment_event(self, *, assignment_id: str, status: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def insert_submission_event(
        self, *, assignment_id: str, submission_id: str, student_id: str, delivered_at: datetime
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def insert_review_event(
        self, *, submission_id: str, review_id: str, punteggio: int, delivered_at: datetime
    ) -> None:
        raise NotImplementedError

    # Report aggregati
    @abstractmethod
    async def get_report_assignments(self) -> list[dict]:
        """Ritorna: { teacherId, assignments_aperti, assignments_completati }"""
        raise NotImplementedError

    @abstractmethod
    async def get_report_submissions(self) -> list[dict]:
        """Ritorna: { assignmentId, teacherId, submissions }"""
        raise NotImplementedError

    @abstractmethod
    async def get_report_reviews(self) -> list[dict]:
        """Ritorna: { studentId, voto_medio }"""
        raise NotImplementedError
