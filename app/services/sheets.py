import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Protocol

import gspread
from google.oauth2.service_account import Credentials

from app.config import Settings


SHEET_HEADERS = [
    "record_id",
    "received_at",
    "name",
    "attendance",
    "guest_count",
    "message",
    "source",
]


@dataclass(frozen=True)
class InvitationRow:
    row_number: int
    record_id: str
    name: str
    attendance: str | None
    guest_count: int | None
    message: str


class InvitationRepository(Protocol):
    def get_public_by_record_id(self, record_id: str) -> InvitationRow | None:
        ...

    def update_rsvp(self, row_number: int, values: list[str | int]) -> None:
        ...


class GoogleSheetsRepository:
    _lock = Lock()

    def __init__(self, settings: Settings) -> None:
        if not settings.spreadsheet_id:
            raise RuntimeError("SPREADSHEET_ID is not configured")

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        if settings.google_service_account_json:
            credentials = Credentials.from_service_account_info(
                json.loads(settings.google_service_account_json), scopes=scopes
            )
        elif settings.google_service_account_file:
            credentials = Credentials.from_service_account_file(
                Path(settings.google_service_account_file), scopes=scopes
            )
        else:
            raise RuntimeError("Google service account credentials are not configured")

        client = gspread.authorize(credentials)
        self.worksheet = client.open_by_key(settings.spreadsheet_id).worksheet(settings.worksheet_name)

    def _rows_by_record_id(self, record_id: str) -> list[InvitationRow]:
        values = self.worksheet.get_all_values()
        if not values or values[0] != SHEET_HEADERS:
            raise RuntimeError("The worksheet does not match the required RSVP schema")

        matches: list[InvitationRow] = []
        for row_number, row in enumerate(values[1:], start=2):
            padded = row + [""] * (len(SHEET_HEADERS) - len(row))
            if padded[0].strip() == record_id:
                matches.append(
                    InvitationRow(
                        row_number=row_number,
                        record_id=padded[0].strip(),
                        name=padded[2].strip(),
                        attendance=padded[3].strip() or None,
                        guest_count=int(padded[4]) if padded[4].strip() else None,
                        message=padded[5],
                    )
                )
        return matches

    def get_public_by_record_id(self, record_id: str) -> InvitationRow | None:
        with self._lock:
            matches = self._rows_by_record_id(record_id)
        if len(matches) != 1 or not matches[0].name:
            return None
        return matches[0]

    def update_rsvp(self, row_number: int, values: list[str | int]) -> None:
        if len(values) != 5:
            raise ValueError("An RSVP update must contain exactly five values")
        with self._lock:
            self.worksheet.update(
                f"B{row_number}",
                [[values[0]]],
                value_input_option="RAW",
            )
            self.worksheet.update(
                f"D{row_number}:G{row_number}",
                [[values[1], values[2], values[3], values[4]]],
                value_input_option="RAW",
            )
