from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import Settings, get_settings
from app.schemas import (
    ErrorResponse,
    InvitationResponse,
    RSVPRequest,
    RSVPResponse,
    validate_record_id,
)
from app.services.sheets import GoogleSheetsRepository, InvitationRepository


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


def get_repository(settings: Settings = Depends(get_settings)) -> InvitationRepository:
    try:
        return GoogleSheetsRepository(settings)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "STORAGE_UNAVAILABLE", "message": "RSVP storage is not available."},
        ) from exc


def check_deadline(settings: Settings) -> None:
    if not settings.rsvp_deadline:
        return
    deadline = datetime.fromisoformat(settings.rsvp_deadline.replace("Z", "+00:00"))
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= deadline.astimezone(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "RSVP_CLOSED", "message": "RSVP submissions are closed."},
        )


def invalid_invitation() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "INVALID_INVITATION_LINK",
            "message": "This invitation link is invalid. Please open the link sent by the bride or groom.",
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/invitations/{record_id}",
    response_model=InvitationResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_invitation(
    record_id: str,
    response: Response,
    settings: Settings = Depends(get_settings),
    repository: InvitationRepository = Depends(get_repository),
) -> InvitationResponse:
    response.headers["Cache-Control"] = settings.invitation_cache_control
    try:
        normalized_id = validate_record_id(record_id)
        invitation = repository.get_public_by_record_id(normalized_id)
    except ValueError:
        raise invalid_invitation()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "STORAGE_ERROR", "message": "The invitation could not be loaded. Please try again."},
        ) from exc
    if invitation is None:
        raise invalid_invitation()
    return InvitationResponse(
        invitation={
            "record_id": invitation.record_id,
            "name": invitation.name,
            "attendance": invitation.attendance,
            "guest_count": invitation.guest_count,
            "message": invitation.message,
        }
    )


@app.post(
    "/api/rsvps",
    response_model=RSVPResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def create_rsvp(
    payload: RSVPRequest,
    settings: Settings = Depends(get_settings),
    repository: InvitationRepository = Depends(get_repository),
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

    try:
        invitation = repository.get_public_by_record_id(payload.record_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "STORAGE_ERROR", "message": "The RSVP could not be saved. Please try again."},
        ) from exc
    if invitation is None:
        raise invalid_invitation()

    received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    values = [received_at, payload.attendance, payload.guest_count, payload.message, "website"]
    try:
        repository.update_rsvp(invitation.row_number, values)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "STORAGE_ERROR", "message": "The RSVP could not be saved. Please try again."},
        ) from exc
    return RSVPResponse(record_id=invitation.record_id)


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
