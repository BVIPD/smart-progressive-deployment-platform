
import pytest
import deployment.database as db


@pytest.fixture
def test_database(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_deployments.db"

    monkeypatch.setattr(db, "DB_PATH", test_db_path)

    db.create_table()

    return test_db_path


def test_create_rollback_request(test_database):
    result = db.create_rollback_request(
        revision=4,
        target_hash="test-hash-123",
        images=["ccrg-platform:v4"]
    )

    assert result["success"] is True
    assert result["status"] == "PENDING"
    assert result["request_id"]

    requests = db.get_rollback_requests("PENDING")

    assert len(requests) == 1
    assert requests[0]["target_revision"] == 4
    assert requests[0]["target_hash"] == "test-hash-123"
    assert requests[0]["target_images"] == ["ccrg-platform:v4"]


def test_duplicate_pending_request_is_blocked(test_database):
    first = db.create_rollback_request(
        4, "hash-1", ["image:v4"]
    )

    second = db.create_rollback_request(
        3, "hash-2", ["image:v3"]
    )

    assert first["success"] is True
    assert second["success"] is False
    assert "already pending" in second["error"]


def test_approve_rollback_request(test_database):
    request = db.create_rollback_request(
        4, "hash-1", ["image:v4"]
    )

    result = db.review_rollback_request(
        request_id=request["request_id"],
        decision="APPROVED",
        reviewer="Admin",
        note="Approved for testing"
    )

    assert result["success"] is True
    assert result["status"] == "APPROVED"
    assert result["execution_performed"] is False

    approved = db.get_rollback_requests("APPROVED")

    assert len(approved) == 1
    assert approved[0]["reviewed_by"] == "Admin"
    assert approved[0]["decision_note"] == "Approved for testing"


def test_reject_rollback_request(test_database):
    request = db.create_rollback_request(
        4, "hash-1", ["image:v4"]
    )

    result = db.review_rollback_request(
        request_id=request["request_id"],
        decision="REJECTED",
        reviewer="Admin",
        note="Deployment is healthy"
    )

    assert result["success"] is True
    assert result["status"] == "REJECTED"
    assert result["execution_performed"] is False

    rejected = db.get_rollback_requests("REJECTED")

    assert len(rejected) == 1
    assert rejected[0]["decision_note"] == "Deployment is healthy"


def test_invalid_review_decision(test_database):
    request = db.create_rollback_request(
        4, "hash-1", ["image:v4"]
    )

    result = db.review_rollback_request(
        request_id=request["request_id"],
        decision="INVALID",
        reviewer="Admin"
    )

    assert result["success"] is False
    assert result["error"] == "Decision must be APPROVED or REJECTED"


def test_unknown_request_cannot_be_reviewed(test_database):
    result = db.review_rollback_request(
        request_id="unknown-request",
        decision="APPROVED",
        reviewer="Admin"
    )

    assert result["success"] is False
    assert result["error"] == "Rollback request not found"


def test_already_reviewed_request_cannot_be_reviewed_again(test_database):
    request = db.create_rollback_request(
        4, "hash-1", ["image:v4"]
    )

    first = db.review_rollback_request(
        request_id=request["request_id"],
        decision="APPROVED",
        reviewer="Admin"
    )

    second = db.review_rollback_request(
        request_id=request["request_id"],
        decision="REJECTED",
        reviewer="Another Admin"
    )

    assert first["success"] is True
    assert second["success"] is False
    assert second["error"] == "Request has already been reviewed"


def test_all_rollback_requests_can_be_retrieved(test_database):
    first = db.create_rollback_request(
        4, "hash-1", ["image:v4"]
    )

    db.review_rollback_request(
        first["request_id"],
        "APPROVED",
        "Admin"
    )

    db.create_rollback_request(
        3, "hash-2", ["image:v3"]
    )

    all_requests = db.get_rollback_requests()

    assert len(all_requests) == 2
    assert {item["status"] for item in all_requests} == {
        "APPROVED",
        "PENDING"
    }
