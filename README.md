# Wedding RSVP API

FastAPI backend that validates RSVP submissions and appends one row to the private Google Sheet. The browser never receives Google credentials or spreadsheet access.

## Spreadsheet contract

The configured worksheet must have this header order:

```text
record_id, received_at, name, attendance, guest_count, message, source
```

The current worksheet tab is `Sheet1`. Share the spreadsheet with the Google service-account email as an Editor. The service only calls `append_row`; it does not update or delete existing rows.

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

The API is available at `POST http://localhost:8000/api/rsvps` and health is available at `GET http://localhost:8000/health`.

## API behavior

- `record_id`, `received_at`, and `source` are generated server-side.
- `attendance` must be `Yes` or `No`; declining guests must use `guest_count: 0`.
- `phone` is required and normalized for request validation, but is not stored because the worksheet has no phone column.
- `guest_side` may be accepted from older clients, but is not stored because the worksheet has no guest-side column.
- `website` is an optional honeypot field and must remain empty for real guests.
- A client retry creates a new append. The frontend should disable submission while a request is in progress and generate a `request_id` for tracing; the fixed worksheet schema does not store that ID.
- `PUT`, `PATCH`, and `DELETE` routes do not exist.
- Set `RSVP_DEADLINE` to an ISO 8601 UTC timestamp to close submissions.

## Test

```powershell
pytest
```

With the API running on port 8000, test a real append from PowerShell:

```powershell
Push-Location 'D:\Codes\sathira-and-ganguli-wedding-backend'; py -c "import httpx; payload={'name':'Column Order Test','phone':'0771234567','attendance':'Yes','guest_count':1,'message':'Seven column test'}; response=httpx.post('http://127.0.0.1:8000/api/rsvps', json=payload); print(f'HTTP {response.status_code}'); print(response.text)"; Pop-Location
```

Expected response:

```text
HTTP 200
{"ok":true,"record_id":"generated-id"}
```

This creates a test row in `Sheet1`; remove test rows manually before production.

For production, run behind HTTPS and configure `CORS_ORIGINS` with only the wedding site's origin.
