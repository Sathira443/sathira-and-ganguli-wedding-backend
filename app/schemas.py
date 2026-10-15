import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Attendance = Literal["Yes", "No"]


def validate_record_id(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ValueError("Invalid record ID")
    return value


class RSVPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str | None = Field(default=None, min_length=1, max_length=100)
    record_id: str = Field(min_length=1, max_length=64)
    attendance: Attendance
    guest_count: int = Field(ge=0, le=100)
    message: str = Field(default="", max_length=1000)
    website: str = Field(default="", max_length=100)

    @field_validator("record_id")
    @classmethod
    def validate_record_id_format(cls, value: str) -> str:
        return validate_record_id(value)

    @model_validator(mode="after")
    def validate_attendance_count(self) -> "RSVPRequest":
        if self.attendance == "No" and self.guest_count != 0:
            raise ValueError("guest_count must be 0 when attendance is No")
        if self.attendance == "Yes" and self.guest_count < 1:
            raise ValueError("guest_count must be at least 1 when attendance is Yes")
        return self


class Invitation(BaseModel):
    record_id: str
    name: str
    attendance: Attendance | None = None
    guest_count: int | None = None
    message: str = ""


class InvitationResponse(BaseModel):
    ok: bool = True
    invitation: Invitation


class RSVPResponse(BaseModel):
    ok: bool = True
    record_id: str


class ErrorResponse(BaseModel):
    ok: bool = False
    code: str
    message: str
