from sqlalchemy import (
    MetaData, Table, Column, String, Integer,
    UniqueConstraint, func, DateTime, ForeignKey
)

metadata = MetaData()

assignments = Table(
    "assignments",
    metadata,
    Column("assignment_id", String(100), primary_key=True),
    Column("stato", String(32), nullable=False),
)

teacher_assignments = Table(
    "teacher_assignments",
    metadata,
    Column("teacher_id", String(100), nullable=False, index=True),
    Column(
        "assignment_id",
        String(100),
        ForeignKey("assignments.assignment_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    ),
    UniqueConstraint("teacher_id", "assignment_id", name="uq_teacher_assignment"),
)

submissions = Table(
    "submissions",
    metadata,
    Column("submission_id", String(100), primary_key=True),
    Column(
        "assignment_id",
        String(100),
        ForeignKey("assignments.assignment_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("student_id", String(100), nullable=False, index=True),
    Column("delivered_at", DateTime(timezone=True), nullable=True, server_default=func.now()),
)

reviews = Table(
    "reviews",
    metadata,
    Column(
        "submission_id",
        String(100),
        ForeignKey("submissions.submission_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("review_id", String(100), primary_key=True),
    Column("punteggio", Integer, nullable=False),
    Column("delivered_at", DateTime(timezone=True), nullable=True, server_default=func.now()),
)
