# Wedding RSVP API

FastAPI backend that resolves private invitation links and updates the matching RSVP row in the private Google Sheet. The browser never receives Google credentials or spreadsheet access.

## Spreadsheet contract

The configured worksheet must have this header order:

```text
record_id, received_at, name, attendance, guest_count, message, source
```

The current worksheet tab is `RSVP`. Share the spreadsheet with the Google service-account email as an Editor. The service reads the worksheet to resolve `record_id` and updates only columns `received_at` through `source` for the matching row.

## Google Cloud setup

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create or select the `wedding-509120` project.
2. Open **APIs & Services → Library**, search for **Google Sheets API**, and click **Enable**.
3. Open **IAM & Admin → Service Accounts** and create a service account.
4. Open the service account, choose **Keys → Add key → Create new key → JSON**, and download the key.
5. Move the downloaded JSON file outside this repository, for example `C:\secrets\wedding-rsvp-service-account.json`.
6. Copy the service account's email address from Google Cloud Console.
7. In Google Sheets, open the private spreadsheet, click **Share**, add that email, and grant **Editor** access.
8. Confirm the worksheet tab is named `Sheet1`, or change `WORKSHEET_NAME` in `.env` to the exact tab name.

Do not publish the spreadsheet to the web when it contains guest data. Do not commit the JSON key or paste its private key into source files. If a key is exposed, delete it under **Service Account → Keys** and create a replacement.

## Local setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Use the credential file option in `.env`; the path must point to the JSON file itself, not the JSON path in `GOOGLE_SERVICE_ACCOUNT_JSON`:

```dotenv
SPREADSHEET_ID=1TIWC3WabU40iqj-NtxEVbXNNT_-wD3Rh4f2rWuZO66I
WORKSHEET_NAME=Sheet1
GOOGLE_SERVICE_ACCOUNT_JSON=
GOOGLE_SERVICE_ACCOUNT_FILE=C:/path/to/service-account-key.json
```

Keep the credential outside source control. The service-account email must have Editor access to the spreadsheet.

The API is available at `GET http://localhost:8000/api/invitations/{record_id}` and `POST http://localhost:8000/api/rsvps`; health is available at `GET http://localhost:8000/health`.

## API behavior

- `record_id` must identify a pre-populated invitation row. The server preserves that row's `record_id` and `name`.
- `GET /api/invitations/{record_id}` returns the public `record_id`, `name`, `attendance`, `guest_count`, and `message` fields so the RSVP form can be edited later. It never returns `source` or other storage credentials/details. Unknown IDs and rows with blank names return `INVALID_INVITATION_LINK`.
- `POST /api/rsvps` updates the matching row; repeated valid submissions overwrite that row with the latest response and never append a second row.
- `attendance` must be `Yes` or `No`; declining guests must use `guest_count: 0`.
- `phone` and `guest_side` are not part of the RSVP request because they are not stored in the worksheet.
- `website` is an optional honeypot field and must remain empty for real guests.
- The optional `request_id` is accepted for client tracing but is not stored in the fixed worksheet schema.
- `PUT`, `PATCH`, and `DELETE` routes do not exist.
- Set `RSVP_DEADLINE` to an ISO 8601 timestamp to close both new RSVPs and edits.
  The API rejects submissions at or after this time with `RSVP_CLOSED`. Include
  a timezone, for example `2026-11-15T23:59:59+05:30` or
  `2026-11-15T18:00:00Z`. A date-only value such as `2026-11-15` is treated
  as midnight UTC.

## Test

```powershell
pytest
```

With the API running on port 8000, test a real invitation lookup and RSVP update from PowerShell. Replace
`yutre7i` with a populated `record_id` from the worksheet:

```powershell
curl.exe -i http://127.0.0.1:8000/api/invitations/yutre7i
curl.exe -i -X POST http://127.0.0.1:8000/api/rsvps `
  -H "Content-Type: application/json" `
  --data-raw '{"request_id":"curl-test-1","record_id":"yutre7i","attendance":"Yes","guest_count":1,"message":"Looking forward to celebrating with you."}'
```

Expected response:

```text
HTTP/1.1 200 OK
{"ok":true,"invitation":{"record_id":"yutre7i","name":"Yutre","attendance":"Yes","guest_count":1,"message":"Looking forward to celebrating with you."}}

HTTP/1.1 200 OK
{"ok":true,"record_id":"yutre7i"}
```

This updates the matching RSVP row. Repeat the POST to verify that the same row is overwritten rather than a second row being appended.

For production, run behind HTTPS and configure `CORS_ORIGINS` with only the wedding site's origin.

For the Vercel deployment, add an environment variable named `CORS_ORIGINS`
with the exact origin of the deployed frontend, for example:

```text
["https://your-wedding-site.vercel.app"]
```

Do not include a trailing slash or the `/api` path. Redeploy the backend after
changing the variable. The browser sends an `OPTIONS` preflight before the RSVP
`POST`; without this origin in `CORS_ORIGINS`, the preflight is rejected and
the frontend reports `Failed to fetch`, even though a direct `curl` request
works. The application also removes accidental trailing slashes when loading
this setting.
