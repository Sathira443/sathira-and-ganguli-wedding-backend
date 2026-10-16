from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app, get_repository
from app.services.sheets import GoogleSheetsRepository, InvitationRow


class FakeRepository:
    def __init__(self) -> None:
        self.rows: dict[str, InvitationRow] = {
            "yutre7i": InvitationRow(
                row_number=2,
                record_id="yutre7i",
                name="Yutre",
                attendance="Yes",
                guest_count=2,
                message="Vegetarian meal, please.",
            ),
            "blank123": InvitationRow(
                row_number=3,
                record_id="blank123",
                name="",
                attendance=None,
                guest_count=None,
                message="",
            ),
        }
        self.updates: list[tuple[int, list[str | int]]] = []
        self.failure: Exception | None = None

    def get_public_by_record_id(self, record_id: str) -> InvitationRow | None:
        if self.failure:
            raise self.failure
        row = self.rows.get(record_id)
        if row is None or not row.name:
            return None
        return row

    def update_rsvp(self, row_number: int, values: list[str | int]) -> None:
        if self.failure:
            raise self.failure
        self.updates.append((row_number, values))


repository = FakeRepository()
app.dependency_overrides[get_repository] = lambda: repository
client = TestClient(app)


def setup_function() -> None:
    repository.updates.clear()
    repository.failure = None
    get_settings.cache_clear()


def valid_rsvp(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_id": "request-1",
        "record_id": "yutre7i",
        "attendance": "Yes",
        "guest_count": 2,
        "message": "Looking forward to celebrating with you.",
    }
    payload.update(overrides)
    return payload


def test_valid_invitation_returns_prefill_fields_without_storage_fields() -> None:
    response = client.get("/api/invitations/yutre7i")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "invitation": {
            "record_id": "yutre7i",
            "name": "Yutre",
            "attendance": "Yes",
            "guest_count": 2,
            "message": "Vegetarian meal, please.",
        },
    }


def test_unknown_invitation_uses_controlled_error() -> None:
    response = client.get("/api/invitations/unknown123")

    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "code": "INVALID_INVITATION_LINK",
        "message": "This invitation link is invalid. Please open the link sent by the bride or groom.",
    }


def test_blank_name_invitation_is_invalid() -> None:
    response = client.get("/api/invitations/blank123")

    assert response.status_code == 404
    assert response.json()["code"] == "INVALID_INVITATION_LINK"


def test_valid_rsvp_updates_matching_row_without_changing_identity() -> None:
    response = client.post("/api/rsvps", json=valid_rsvp())

    assert response.status_code == 200
    assert response.json() == {"ok": True, "record_id": "yutre7i"}
    assert repository.updates[0][0] == 2
    assert repository.updates[0][1] == [
        repository.updates[0][1][0],
        "Yes",
        2,
        "Looking forward to celebrating with you.",
        "website",
    ]
    assert repository.rows["yutre7i"].record_id == "yutre7i"
    assert repository.rows["yutre7i"].name == "Yutre"


def test_rsvp_deadline_closes_new_and_existing_submissions(monkeypatch) -> None:
    monkeypatch.setenv("RSVP_DEADLINE", "2000-01-01T00:00:00Z")
    get_settings.cache_clear()

    response = client.post("/api/rsvps", json=valid_rsvp())

    assert response.status_code == 409
    assert response.json() == {
        "ok": False,
        "code": "RSVP_CLOSED",
        "message": "RSVP submissions are closed.",
    }
    assert repository.updates == []


def test_repeated_valid_rsvp_updates_same_row() -> None:
    first = client.post("/api/rsvps", json=valid_rsvp())
    second = client.post(
        "/api/rsvps",
        json=valid_rsvp(attendance="No", guest_count=0, message="Sorry, cannot attend."),
    )

    assert first.status_code == second.status_code == 200
    assert [update[0] for update in repository.updates] == [2, 2]
    assert repository.updates[1][1][1:] == ["No", 0, "Sorry, cannot attend.", "website"]


def test_rsvp_without_record_id_is_rejected() -> None:
    payload = valid_rsvp()
    del payload["record_id"]

    response = client.post("/api/rsvps", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert repository.updates == []


def test_submitted_name_is_rejected_and_cannot_select_identity() -> None:
    response = client.post("/api/rsvps", json=valid_rsvp(name="Someone Else"))

    assert response.status_code == 422
    assert repository.updates == []


def test_unknown_rsvp_never_updates_a_row() -> None:
    response = client.post("/api/rsvps", json=valid_rsvp(record_id="unknown123"))

    assert response.status_code == 404
    assert response.json()["code"] == "INVALID_INVITATION_LINK"
    assert repository.updates == []


def test_invalid_attendance_count_is_rejected() -> None:
    response = client.post("/api/rsvps", json=valid_rsvp(attendance="No", guest_count=1))

    assert response.status_code == 422
    assert repository.updates == []


def test_honeypot_is_rejected() -> None:
    response = client.post("/api/rsvps", json=valid_rsvp(website="bot"))

    assert response.status_code == 422
    assert repository.updates == []


def test_storage_failure_is_not_reported_as_invalid_link() -> None:
    repository.failure = RuntimeError("sheet unavailable")

    response = client.get("/api/invitations/yutre7i")

    assert response.status_code == 503
    assert response.json() == {
        "ok": False,
        "code": "STORAGE_ERROR",
        "message": "The invitation could not be loaded. Please try again.",
    }


def test_rsvp_storage_failure_returns_503() -> None:
    repository.failure = RuntimeError("sheet unavailable")

    response = client.post("/api/rsvps", json=valid_rsvp())

    assert response.status_code == 503
    assert response.json()["code"] == "STORAGE_ERROR"


def test_max_guest_count_is_enforced() -> None:
    response = client.post("/api/rsvps", json=valid_rsvp(guest_count=11))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert repository.updates == []


def test_sheet_update_skips_name_column() -> None:
    class FakeWorksheet:
        def __init__(self) -> None:
            self.calls: list[tuple[str, list[list[str | int]]]] = []

        def update(self, cell_range: str, values: list[list[str | int]], **kwargs: object) -> None:
            self.calls.append((cell_range, values))

    worksheet = FakeWorksheet()
    sheets_repository = GoogleSheetsRepository.__new__(GoogleSheetsRepository)
    sheets_repository.worksheet = worksheet

    sheets_repository.update_rsvp(7, ["timestamp", "No", 0, "Cannot attend.", "website"])

    assert worksheet.calls == [
        ("B7", [["timestamp"]]),
        ("D7:G7", [["No", 0, "Cannot attend.", "website"]]),
    ]
