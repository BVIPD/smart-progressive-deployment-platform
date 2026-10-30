
import pytest
from fastapi.testclient import TestClient

import app.main as main
import deployment.database as db


client = TestClient(main.app)


@pytest.fixture
def test_database(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_deployments.db"

    monkeypatch.setattr(db, "DB_PATH", test_db_path)
    db.create_table()

    monkeypatch.setattr(
        main,
        "validate_rollback_target",
        lambda revision: {
            "success": True,
            "target_revision": revision,
            "target_hash": "test-hash-123",
            "target_images": ["ccrg-platform:v4"],
            "requires_human_approval": True
        }
    )

    return test_db_path


def test_create_rollback_request(test_database):
    response = client.post(
        "/deployment/rollback/request",
        json={"target_revision": 4}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Rollback approval request created"
    assert data["approval"]["status"] == "PENDING"
    assert data["execution_performed"] is False


def test_get_pending_rollback_requests(test_database):
    db.create_rollback_request(
        4,
        "test-hash-123",
        ["ccrg-platform:v4"]
    )

    response = client.get("/deployment/rollback/pending")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "PENDING"


def test_approve_rollback_request(test_database):
    request = db.create_rollback_request(
        4,
        "test-hash-123",
        ["ccrg-platform:v4"]
    )

    response = client.post(
        "/deployment/rollback/approve",
        json={
            "request_id": request["request_id"],
            "decision": "APPROVED",
            "reviewer": "Admin",
            "note": "Approved for testing"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["result"]["status"] == "APPROVED"
    assert data["execution_performed"] is False


def test_reject_rollback_request(test_database):
    request = db.create_rollback_request(
        4,
        "test-hash-123",
        ["ccrg-platform:v4"]
    )

    response = client.post(
        "/deployment/rollback/approve",
        json={
            "request_id": request["request_id"],
            "decision": "REJECTED",
            "reviewer": "Admin",
            "note": "Deployment is healthy"
        }
    )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "REJECTED"


def test_invalid_rollback_decision(test_database):
    request = db.create_rollback_request(
        4,
        "test-hash-123",
        ["ccrg-platform:v4"]
    )

    response = client.post(
        "/deployment/rollback/approve",
        json={
            "request_id": request["request_id"],
            "decision": "INVALID",
            "reviewer": "Admin"
        }
    )

    assert response.status_code == 400


def test_rollback_request_invalid_revision(test_database):
    response = client.post(
        "/deployment/rollback/request",
        json={"target_revision": 0}
    )

    assert response.status_code == 422


def test_rollback_target_validation_failure(test_database, monkeypatch):
    monkeypatch.setattr(
        main,
        "validate_rollback_target",
        lambda revision: {
            "success": False,
            "error": "No rollback required"
        }
    )

    response = client.post(
        "/deployment/rollback/request",
        json={"target_revision": 7}
    )

    assert response.status_code == 400
