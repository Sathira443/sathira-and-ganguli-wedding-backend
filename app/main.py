from datetime import datetime, timezone
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import Settings, get_settings
from app.schemas import ErrorResponse, RSVPRequest, RSVPResponse
from app.services.sheets import AppendRepository, GoogleSheetsRepository


app = FastAPI(title="Wedding RSVP API", version="1.0.0")


def configure_cors(settings: Settings) -> None:
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["POST", "GET"],
            allow_headers=["Content-Type"],
        )


configure_cors(get_settings())


def get_repository(settings: Settings = Depends(get_settings)) -> AppendRepository:
    try:
        return GoogleSheetsRepository(settings)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "STORAGE_UNAVAILABLE", "message": "RSVP storage is not available."},
        ) from exc


def make_record_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{secrets.token_urlsafe(6)}"


def check_deadline(settings: Settings) -> None:
    if not settings.rsvp_deadline:
        return
    deadline = datetime.fromisoformat(settings.rsvp_deadline.replace("Z", "+00:00"))
    if datetime.now(timezone.utc) >= deadline.astimezone(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "RSVP_CLOSED", "message": "RSVP submissions are closed."},
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/rsvps",
    response_model=RSVPResponse,
    responses={
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def create_rsvp(
    payload: RSVPRequest,
    settings: Settings = Depends(get_settings),
    repository: AppendRepository = Depends(get_repository),
) -> RSVPResponse:
    check_deadline(settings)
    if payload.website:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "VALIDATION_ERROR", "message": "Please check the submitted fields."},
        )
    if payload.guest_count > settings.max_guest_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "VALIDATION_ERROR", "message": "Guest count exceeds the allowed maximum."},
        )

    record_id = make_record_id()
    received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    row = [
        record_id,
        received_at,
        payload.name,
        payload.attendance,
        payload.guest_count,
        payload.message,
        "website",
    ]
    try:
        repository.append(row)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "STORAGE_ERROR", "message": "The RSVP could not be saved. Please try again."},
        ) from exc
    return RSVPResponse(record_id=record_id)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "REQUEST_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"ok": False, **detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"ok": False, "code": "VALIDATION_ERROR", "message": "Please check the submitted fields."},
    )
