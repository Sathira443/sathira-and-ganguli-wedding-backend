from fastapi.testclient import TestClient

from app.main import app, get_repository
from app.config import get_settings


class FakeRepository:
    def __init__(self) -> None:
        self.rows: list[list[str | int]] = []

    def append(self, row: list[str | int]) -> None:
        self.rows.append(row)


repository = FakeRepository()
app.dependency_overrides[get_repository] = lambda: repository
client = TestClient(app)


def setup_function() -> None:
    repository.rows.clear()


def test_valid_rsvp_appends_one_row() -> None:
    response = client.post(
        "/api/rsvps",
        json={
            "request_id": "request-1",
            "name": "Asha Perera",
            "phone": "+94 (77) 123-4567",
            "attendance": "Yes",
            "guest_count": 2,
            "guest_side": "Bride",
            "message": "Vegetarian meal, please.",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert len(repository.rows) == 1
    assert repository.rows[0][2:9] == [
        "Asha Perera",
        "+94771234567",
        "Yes",
        2,
        "Bride",
        "Vegetarian meal, please.",
        "website",
    ]


def test_declining_guest_must_have_zero_count() -> None:
    response = client.post(
        "/api/rsvps",
        json={
            "name": "Nimal Silva",
            "phone": "0771234567",
            "attendance": "No",
            "guest_count": 1,
            "guest_side": "Groom",
        },
    )

    assert response.status_code == 422
    assert len(repository.rows) == 0


def test_unknown_fields_are_rejected() -> None:
    response = client.post(
        "/api/rsvps",
        json={
            "name": "Nimal Silva",
            "phone": "0771234567",
            "attendance": "Yes",
            "guest_count": 1,
            "guest_side": "Unknown",
            "record_id": "client-chosen-id",
        },
    )

    assert response.status_code == 422
    assert len(repository.rows) == 0


def test_malformed_payload_uses_public_error_contract() -> None:
    response = client.post("/api/rsvps", json={"name": "Incomplete"})

    assert response.status_code == 422
    assert response.json() == {
        "ok": False,
        "code": "VALIDATION_ERROR",
        "message": "Please check the submitted fields.",
    }
    assert len(repository.rows) == 0
