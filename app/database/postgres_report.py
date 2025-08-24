from __future__ import annotations
from datetime import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select, func, literal_column

from app.database.report_repository import ReportRepository
from app.database.tables import metadata, teacher_assignments, assignments, submissions, reviews

logger = logging.getLogger("report.repository")

def normalizer(string: str) -> str:
    return string.strip().lower() if isinstance(string, str) else string

class PostgresReportRepository(ReportRepository):
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def ensure_schema(self) -> None:
        logger.info("Ensuring schema for report tables")
        async with self.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        logger.info("Schema ready")

    # 1) teacher_assignments (idempotente)
    async def insert_teacher_assignment(self, *, assignment_id: str, teacher_id: str) -> None:
        if not assignment_id or not teacher_id:
            raise ValueError("assignment_id e teacher_id sono obbligatori")
        stmt = pg_insert(teacher_assignments).values(
            assignment_id=assignment_id,
            teacher_id=teacher_id,
        ).on_conflict_do_nothing(
            index_elements=[teacher_assignments.c.teacher_id, teacher_assignments.c.assignment_id]
        )
        async with self.session_factory() as session:
            await session.execute(stmt)
            await session.commit()
        logger.debug("Linked teacher↔assignment", extra={"assignment_id": assignment_id, "teacher_id": teacher_id})

    # 2) assignments (upsert su stato)
    async def insert_assignment_event(self, *, assignment_id: str, status: str) -> None:
        status = normalizer(status)
        assignment_id = normalizer(assignment_id)

        if not assignment_id or not status:
            raise ValueError("assignment_id e status sono obbligatori")
        stmt = pg_insert(assignments).values(
            assignment_id=assignment_id,
            stato=status,
        ).on_conflict_do_update(
            index_elements=[assignments.c.assignment_id],
            set_={"stato": status},
        )
        async with self.session_factory() as session:
            await session.execute(stmt)
            await session.commit()
        logger.debug("Assignment upserted", extra={"assignment_id": assignment_id, "stato": status})

    # 3) submissions (upsert su submission_id)
    async def insert_submission_event(
        self, *, assignment_id: str, submission_id: str, student_id: str, delivered_at: datetime
    ) -> None:
        if not submission_id or not assignment_id or not student_id:
            raise ValueError("submission_id, assignment_id, student_id obbligatori")

        stmt = pg_insert(submissions).values(
            submission_id=submission_id,
            assignment_id=assignment_id,
            student_id=student_id,
            delivered_at=delivered_at,
        ).on_conflict_do_update(
            index_elements=[submissions.c.submission_id],
            set_={
                "assignment_id": assignment_id,
                "student_id": student_id,
                "delivered_at": delivered_at,
            },
        )

        async with self.session_factory() as session:
            await session.execute(stmt)
            await session.commit()
        logger.debug("Submission upserted",
                    extra={"submission_id": submission_id, "assignment_id": assignment_id, "student_id": student_id, "delivered_at": delivered_at})

    # 4) reviews (upsert su submission_id)
    async def insert_review_event(
        self, *, submission_id: str, review_id: str, punteggio: int, delivered_at: datetime
    ) -> None:
        if not submission_id:
            raise ValueError("submission_id è obbligatorio")
        if not review_id:
            raise ValueError("review_id è obbligatorio")

        stmt = pg_insert(reviews).values(
            submission_id=submission_id,
            review_id=review_id,
            punteggio=int(punteggio),
            delivered_at=delivered_at,
        ).on_conflict_do_update(
            index_elements=[reviews.c.review_id],   # <--- upsert per review_id (PK)
            set_={
                "punteggio": int(punteggio),
                "delivered_at": delivered_at,
            },
        )

        async with self.session_factory() as session:
            await session.execute(stmt)
            await session.commit()

        logger.debug(
            "Review upserted",
            extra={"submission_id": submission_id, "review_id": review_id, "punteggio": int(punteggio)},
        )


    async def get_report_assignments(self) -> list[dict]:
        """
        Ritorna righe: { teacherId, assignments_aperti, assignments_completati }
        """
        stmt = (
            select(
                teacher_assignments.c.teacher_id.label("teacherId"),
                func.count().filter(assignments.c.stato == literal_column("'open'")).label("assignments_aperti"),
                func.count().filter(assignments.c.stato == literal_column("'completed'")).label("assignments_completati"),
            )
            .select_from(
                teacher_assignments.join(
                    assignments,
                    teacher_assignments.c.assignment_id == assignments.c.assignment_id
                )
            )
            .group_by(teacher_assignments.c.teacher_id)
            .order_by(teacher_assignments.c.teacher_id)
        )
        async with self.session_factory() as session:
            rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def get_report_submissions(self) -> list[dict]:
        """
        Ritorna righe: { assignmentId, teacherId, submissions }
        """
        stmt = (
            select(
                submissions.c.assignment_id.label("assignmentId"),
                teacher_assignments.c.teacher_id.label("teacherId"),
                func.count(submissions.c.submission_id).label("submissions")
            )
            .select_from(
                submissions.join(
                    teacher_assignments,
                    submissions.c.assignment_id == teacher_assignments.c.assignment_id
                )
            )
            .group_by(submissions.c.assignment_id, teacher_assignments.c.teacher_id)
            .order_by(submissions.c.assignment_id, teacher_assignments.c.teacher_id)
        )
        async with self.session_factory() as session:
            rows = (await session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def get_report_reviews(self) -> list[dict]:
        """
        Ritorna righe: { studentId, voto_medio }
        - media dei punteggi delle review per le submissions consegnate dallo studente
        """
        stmt = (
            select(
                submissions.c.student_id.label("studentId"),
                func.avg(reviews.c.punteggio).label("voto_medio")
            )
            .select_from(
                reviews.join(submissions, reviews.c.submission_id == submissions.c.submission_id)
            )
            .group_by(submissions.c.student_id)
            .order_by(submissions.c.student_id)
        )
        async with self.session_factory() as session:
            rows = (await session.execute(stmt)).mappings().all()
        # cast a float “pulito”
        return [{"studentId": r["studentId"], "voto_medio": float(r["voto_medio"]) if r["voto_medio"] is not None else None} for r in rows]