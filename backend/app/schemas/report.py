import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator


class ReportRequest(BaseModel):
    request_id: uuid.UUID
    organizer_id: uuid.UUID
    recipient: Annotated[
        str, StringConstraints(max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    ]
    week: Annotated[str, StringConstraints(pattern=r"^\d{4}-W\d{2}$")]

    @field_validator("week")
    @classmethod
    def valid_week(cls, value: str) -> str:
        date.fromisocalendar(int(value[:4]), int(value[6:]), 1)
        return value

    @property
    def key(self) -> str:
        return f"requests/{self.organizer_id}/{self.request_id}.json"
