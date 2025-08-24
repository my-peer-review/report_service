from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Assignment(BaseModel):
    assignmentId: str = Field(..., alias="assignment_id")
    status: str
    createdAt: datetime = Field(..., alias="created_at")
    completedAt: Optional[datetime] = Field(None, alias="completed_at")