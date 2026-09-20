from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Attendance = Literal["Yes", "No"]


class RSVPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str | None = Field(default=None, min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    attendance: Attendance
    guest_count: int = Field(ge=0, le=100)
    message: str = Field(default="", max_length=1000)
    website: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def validate_attendance_count(self) -> "RSVPRequest":
        if self.attendance == "No" and self.guest_count != 0:
            raise ValueError("guest_count must be 0 when attendance is No")
        if self.attendance == "Yes" and self.guest_count < 1:
            raise ValueError("guest_count must be at least 1 when attendance is Yes")
        return self


class RSVPResponse(BaseModel):
    ok: bool = True
    record_id: str


class ErrorResponse(BaseModel):
    ok: bool = False
    code: str
    message: str
