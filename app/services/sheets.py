import json
from pathlib import Path
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


class AppendRepository(Protocol):
    def append(self, row: list[str | int]) -> None:
        ...


class GoogleSheetsRepository:
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

    def append(self, row: list[str | int]) -> None:
        self.worksheet.append_row(row, value_input_option="RAW", insert_data_option="INSERT_ROWS")
