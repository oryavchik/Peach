import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints


class MeetingCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    starts_at: AwareDatetime
    duration_minutes: int = Field(ge=1, le=1440)
    participant_count: int = Field(ge=1, le=2147483647)


class MeetingRead(MeetingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class MeetingList(BaseModel):
    items: list[MeetingRead]
    total: int


class MeetingStats(BaseModel):
    week_start: datetime
    week_end: datetime
    meeting_count: int
    total_hours: float
    previous_meeting_count: int
    previous_total_hours: float
