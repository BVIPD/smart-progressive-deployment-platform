
import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "deployments.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def create_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deployment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT,
                decision TEXT,
                active_version TEXT,
                deployment_status TEXT,
                success_probability REAL,
                decision_reason TEXT,
                cpu_usage REAL,
                memory_usage REAL,
                latency REAL,
                error_rate REAL,
                traffic REAL
            )
        """)

        columns = {
            row[1] for row in
            conn.execute("PRAGMA table_info(deployment_history)")
        }

        additions = {
            "decision_reason": "TEXT",
            "cpu_usage": "REAL",
            "memory_usage": "REAL",
            "latency": "REAL",
            "error_rate": "REAL",
            "traffic": "REAL"
        }

        for name, dtype in additions.items():
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE deployment_history ADD COLUMN {name} {dtype}"
                )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS rollback_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT UNIQUE NOT NULL,
                requested_at TEXT NOT NULL,
                target_revision INTEGER NOT NULL,
                target_hash TEXT NOT NULL,
                target_images TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                reviewed_at TEXT,
                reviewed_by TEXT,
                decision_note TEXT
            )
        """)


def save_deployment(data):
    metrics = data.get("metrics", {})

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO deployment_history (
                time, decision, active_version, deployment_status,
                success_probability, decision_reason,
                cpu_usage, memory_usage, latency, error_rate, traffic
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["time"],
            data["decision"],
            data["active_version"],
            data["deployment_status"],
            data["success_probability"],
            data.get("decision_reason", ""),
            metrics.get("cpu_usage"),
            metrics.get("memory_usage"),
            metrics.get("latency"),
            metrics.get("error_rate"),
            metrics.get("traffic")
        ))


def get_deployments():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT * FROM deployment_history ORDER BY id"
        ).fetchall()

        return [dict(row) for row in rows]


def create_rollback_request(revision, target_hash, images):
    request_id = str(uuid.uuid4())

    with sqlite3.connect(DB_PATH) as conn:
        pending = conn.execute("""
            SELECT request_id FROM rollback_approvals
            WHERE status = 'PENDING'
            LIMIT 1
        """).fetchone()

        if pending:
            return {
                "success": False,
                "error": "A rollback approval request is already pending",
                "request_id": pending[0]
            }

        conn.execute("""
            INSERT INTO rollback_approvals (
                request_id, requested_at, target_revision,
                target_hash, target_images, status
            )
            VALUES (?, ?, ?, ?, ?, 'PENDING')
        """, (
            request_id,
            datetime.now().isoformat(timespec="seconds"),
            revision,
            target_hash,
            json.dumps(images)
        ))

    return {
        "success": True,
        "request_id": request_id,
        "status": "PENDING"
    }


def get_rollback_requests(status=None):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        if status:
            rows = conn.execute("""
                SELECT * FROM rollback_approvals
                WHERE status = ?
                ORDER BY id DESC
            """, (status.upper(),)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM rollback_approvals
                ORDER BY id DESC
            """).fetchall()

        results = [dict(row) for row in rows]

        for item in results:
            item["target_images"] = json.loads(
                item["target_images"]
            )

        return results


def review_rollback_request(request_id, decision, reviewer, note=""):
    decision = decision.upper()

    if decision not in ("APPROVED", "REJECTED"):
        return {
            "success": False,
            "error": "Decision must be APPROVED or REJECTED"
        }

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT * FROM rollback_approvals
            WHERE request_id = ?
        """, (request_id,)).fetchone()

        if row is None:
            return {
                "success": False,
                "error": "Rollback request not found"
            }

        if row["status"] != "PENDING":
            return {
                "success": False,
                "error": "Request has already been reviewed"
            }

        conn.execute("""
            UPDATE rollback_approvals
            SET status = ?, reviewed_at = ?,
                reviewed_by = ?, decision_note = ?
            WHERE request_id = ? AND status = 'PENDING'
        """, (
            decision,
            datetime.now().isoformat(timespec="seconds"),
            reviewer,
            note,
            request_id
        ))

    return {
        "success": True,
        "request_id": request_id,
        "status": decision,
        "execution_performed": False
    }
