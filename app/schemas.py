from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Attendance = Literal["Yes", "No"]
GuestSide = Literal["Bride", "Groom", "Unknown"]


class RSVPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str | None = Field(default=None, min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    attendance: Attendance
    guest_count: int = Field(ge=0, le=100)
    guest_side: GuestSide = "Unknown"
    message: str = Field(default="", max_length=1000)
    website: str = Field(default="", max_length=100)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not normalized.replace("+", "").isdigit() or normalized.count("+") > 1 or ("+" in normalized and not normalized.startswith("+")):
            raise ValueError("phone must contain a valid phone number")
        if len(normalized.replace("+", "")) < 7:
            raise ValueError("phone must contain at least 7 digits")
        return normalized

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
