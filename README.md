# Wedding RSVP API

FastAPI backend that validates RSVP submissions and appends one row to the private Google Sheet. The browser never receives Google credentials or spreadsheet access.

## Spreadsheet contract

The configured worksheet must have this header order:

```text
record_id, received_at, name, phone, attendance, guest_count, guest_side, message, source
```

Share the spreadsheet with the Google service-account email as an Editor. The service only calls `append_row`; it does not update or delete existing rows.

## Local setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Set either `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_FILE` in `.env`. Keep the credential outside source control. `SPREADSHEET_ID` is already set to the provided spreadsheet; `WORKSHEET_NAME` should match its tab name.

The API is available at `POST http://localhost:8000/api/rsvps` and health is available at `GET http://localhost:8000/health`.

## API behavior

- `record_id`, `received_at`, and `source` are generated server-side.
- `attendance` must be `Yes` or `No`; declining guests must use `guest_count: 0`.
- Phone values are normalized to digits with an optional leading `+`.
- `website` is an optional honeypot field and must remain empty for real guests.
- A client retry creates a new append. The frontend should disable submission while a request is in progress and generate a `request_id` for tracing; the fixed worksheet schema does not store that ID.
- `PUT`, `PATCH`, and `DELETE` routes do not exist.
- Set `RSVP_DEADLINE` to an ISO 8601 UTC timestamp to close submissions.

## Test

```powershell
pytest
```

For production, run behind HTTPS and configure `CORS_ORIGINS` with only the wedding site's origin.
