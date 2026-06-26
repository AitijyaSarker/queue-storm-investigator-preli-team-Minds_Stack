"""Schema validation tests: malformed input, missing fields, invalid enums."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_missing_ticket_id():
    r = client.post("/analyze-ticket", json={"complaint": "I have an issue"})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_request"


def test_missing_complaint():
    r = client.post("/analyze-ticket", json={"ticket_id": "TKT-001"})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_request"


def test_blank_complaint_422():
    r = client.post("/analyze-ticket", json={"ticket_id": "TKT-001", "complaint": "   "})
    assert r.status_code == 422


def test_invalid_enum_language():
    r = client.post(
        "/analyze-ticket",
        json={"ticket_id": "TKT-001", "complaint": "I have an issue", "language": "klingon"},
    )
    assert r.status_code == 400


def test_invalid_txn_status_enum():
    r = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-001",
            "complaint": "Failed payment",
            "transaction_history": [
                {
                    "transaction_id": "TXN-1",
                    "timestamp": "2026-04-14T14:08:22Z",
                    "type": "transfer",
                    "amount": 1000,
                    "counterparty": "+8801711111111",
                    "status": "successful",  # invalid — should be "completed"
                }
            ],
        },
    )
    assert r.status_code == 400


def test_extra_field_rejected():
    r = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "TKT-001",
            "complaint": "Issue",
            "sneaky_extra": True,
        },
    )
    assert r.status_code == 400


def test_malformed_json_returns_400():
    r = client.post("/analyze-ticket", data="{not json")
    assert r.status_code in (400, 422)  # FastAPI parses JSON itself; either is acceptable.


@pytest.mark.parametrize("path", ["/nope", "/analyze", "/Analyze-Ticket"])
def test_unknown_paths_404(path):
    r = client.get(path)
    assert r.status_code == 404
