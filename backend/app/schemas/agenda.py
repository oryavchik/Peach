from datetime import date
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Owner = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class AgendaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: Text
    owner: Owner | None = None
    minutes: int | None = Field(default=None, ge=1, le=480, strict=True)


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: Text
    owner: Owner | None = None
    due: date | None = None


class ParsedAgenda(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
        | None
    ) = None
    starts_at: AwareDatetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=600, strict=True)
    items: list[AgendaItem] = Field(max_length=50)
    action_items: list[ActionItem] = Field(default_factory=list, max_length=50)
    language: str = Field(pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,8})?$")


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=10000)
    today: date
    tz: str = Field(max_length=100)

    @field_validator("tz")
    @classmethod
    def valid_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Use an IANA timezone, for example Europe/Kyiv") from error
        return value


class AISuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agenda: ParsedAgenda
    model: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=100)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0, allow_inf_nan=False)
    latency_ms: int = Field(default=0, ge=0)


class AgendaSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agenda: ParsedAgenda
    ai_suggestion: AISuggestion | None = None
