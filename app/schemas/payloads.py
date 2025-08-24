from __future__ import annotations
from typing import Optional, TypedDict
from datetime import datetime

# ---- Tipi payload ----
class AssignmentInsertPayload(TypedDict):
    assignmentId: str
    status: str
    createdAt: str | datetime
    completedAt: Optional[str | datetime]

class AssignmentUpdatePayload(TypedDict, total=False):
    assignmentId: str
    status: str
    completedAt: Optional[str | datetime]

class SubmissionPayload(TypedDict):
    assignmentId: str
    submissionId: str
    createdAt: str | datetime

class ReviewPayload(TypedDict):
    submissionId: str
    punteggio: int
