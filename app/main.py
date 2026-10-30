
import os
import time
from pathlib import Path

import joblib
import numpy as np
import psutil

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST
)

from deployment.controller import DeploymentController

from deployment.database import (
    create_table,
    save_deployment,
    get_deployments,
    create_rollback_request,
    get_rollback_requests,
    review_rollback_request
)

from deployment.argo_manager import (
    get_rollout_status,
    validate_rollback_target,
    rollback_rollout
)


# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

app = FastAPI(
    title="Smart Progressive Deployment Platform",
    description="AI-driven progressive deployment and stability monitoring",
    version="1.0.0"
)

VERSION = os.getenv("APP_VERSION", "v1")

BASE_PATH = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_PATH / "ml" / "deployment_model.pkl"
DASHBOARD_PATH = Path(__file__).resolve().parent / "dashboard.html"

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"ML model not found: {MODEL_PATH}")

model = joblib.load(MODEL_PATH)

controller = DeploymentController()
create_table()


# --------------------------------------------------
# PROMETHEUS METRICS
# --------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request processing time",
    ["endpoint"]
)

CPU_GAUGE = Gauge(
    "system_cpu_usage_percent",
    "System CPU usage percentage"
)

MEMORY_GAUGE = Gauge(
    "system_memory_usage_percent",
    "System memory usage percentage"
)

DEPLOYMENT_CPU = Gauge(
    "deployment_cpu_usage_percent",
    "Deployment CPU usage percentage"
)

DEPLOYMENT_MEMORY = Gauge(
    "deployment_memory_usage_percent",
    "Deployment memory usage percentage"
)

DEPLOYMENT_LATENCY = Gauge(
    "deployment_latency_ms",
    "Average observed request latency in milliseconds"
)

DEPLOYMENT_ERROR_RATE = Gauge(
    "deployment_error_rate_percent",
    "HTTP server error rate percentage"
)

DEPLOYMENT_TRAFFIC = Gauge(
    "deployment_traffic",
    "Total observed HTTP requests"
)

ML_SUCCESS_PROBABILITY = Gauge(
    "ml_deployment_success_probability",
    "ML predicted deployment success probability"
)

DEPLOYMENT_DECISIONS = Counter(
    "deployment_decisions_total",
    "Total deployment decisions",
    ["decision"]
)


# --------------------------------------------------
# REQUEST MONITORING
# --------------------------------------------------

total_requests = 0
failed_requests = 0
total_latency = 0.0


@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    global total_requests, failed_requests, total_latency

    start_time = time.time()
    response = await call_next(request)

    duration = time.time() - start_time
    endpoint = request.url.path

    if endpoint != "/prometheus":
        total_requests += 1
        total_latency += duration

        if response.status_code >= 500:
            failed_requests += 1

        REQUEST_COUNT.labels(
            request.method,
            endpoint,
            str(response.status_code)
        ).inc()

        REQUEST_LATENCY.labels(endpoint).observe(duration)

        DEPLOYMENT_TRAFFIC.set(total_requests)

        DEPLOYMENT_ERROR_RATE.set(
            failed_requests / total_requests * 100
        )

        DEPLOYMENT_LATENCY.set(
            total_latency / total_requests * 1000
        )

    return response


# --------------------------------------------------
# INPUT VALIDATION
# --------------------------------------------------

class DeploymentMetrics(BaseModel):
    cpu_usage: float = Field(ge=0, le=100)
    memory_usage: float = Field(ge=0, le=100)
    latency: float = Field(ge=0)
    error_rate: float = Field(ge=0, le=100)
    traffic: float = Field(ge=0)


class RollbackRequest(BaseModel):
    target_revision: int = Field(gt=0)


class RollbackReview(BaseModel):
    request_id: str
    decision: str
    reviewer: str = Field(min_length=2, max_length=100)
    note: str = Field(default="", max_length=500)


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    if not DASHBOARD_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Dashboard HTML file not found"
        )

    return DASHBOARD_PATH.read_text(encoding="utf-8")


# --------------------------------------------------
# BASIC API ENDPOINTS
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "project": "Smart Progressive Deployment Platform",
        "version": VERSION,
        "status": "Running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": VERSION
    }


@app.get("/version")
def version():
    return {
        "current_version": VERSION
    }


# --------------------------------------------------
# SYSTEM METRICS
# --------------------------------------------------

@app.get("/metrics")
def metrics():
    cpu = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent

    CPU_GAUGE.set(cpu)
    MEMORY_GAUGE.set(memory)

    DEPLOYMENT_CPU.set(cpu)
    DEPLOYMENT_MEMORY.set(memory)

    return {
        "cpu_usage": cpu,
        "memory_usage": memory,
        "version": VERSION
    }


@app.get("/prometheus")
def prometheus_metrics():
    metrics()

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# --------------------------------------------------
# MACHINE LEARNING PREDICTION
# --------------------------------------------------

def get_prediction(data: DeploymentMetrics):
    x = np.array([[
        data.cpu_usage,
        data.memory_usage,
        data.latency,
        data.error_rate,
        data.traffic
    ]])

    prediction = int(model.predict(x)[0])

    probability = float(
        model.predict_proba(x)[0][1]
    )

    ML_SUCCESS_PROBABILITY.set(probability)

    return prediction, probability


def build_metrics_data(data: DeploymentMetrics):
    return {
        "cpu_usage": data.cpu_usage,
        "memory_usage": data.memory_usage,
        "latency": data.latency,
        "error_rate": data.error_rate,
        "traffic": data.traffic
    }


# --------------------------------------------------
# BASIC ML PREDICTION API
# --------------------------------------------------

@app.post("/predict")
def predict(data: DeploymentMetrics):
    prediction, probability = get_prediction(data)

    return {
        "deployment_prediction": (
            "SUCCESS" if prediction == 1 else "FAILURE"
        ),
        "success_probability": round(probability, 4),
        "recommendation": (
            "CONTINUE" if prediction == 1 else "ROLLBACK"
        )
    }


# --------------------------------------------------
# INTELLIGENT DEPLOYMENT EVALUATION
# --------------------------------------------------

@app.post("/deployment/evaluate")
def evaluate_deployment(data: DeploymentMetrics):
    prediction, probability = get_prediction(data)

    metrics_data = build_metrics_data(data)

    argo = get_rollout_status()

    result = controller.evaluate(
        prediction,
        probability,
        metrics_data,
        argo_status=argo
    )

    result["argo_status"] = argo

    save_deployment(result)

    decision = str(
        result.get("decision", "UNKNOWN")
    ).upper()

    DEPLOYMENT_DECISIONS.labels(decision).inc()

    return result


# --------------------------------------------------
# SAFE DEPLOYMENT DECISION DRY RUN
# --------------------------------------------------

@app.post("/deployment/dry-run")
def deployment_dry_run(data: DeploymentMetrics):
    prediction, probability = get_prediction(data)

    metrics_data = build_metrics_data(data)

    argo = get_rollout_status()

    breaches = [
        key
        for key, limit in controller.limits.items()
        if metrics_data.get(key, 0) >= limit
    ]

    if not argo.get("success"):
        decision = "HOLD"
        reason = "Argo Rollouts status unavailable"

    elif breaches:
        decision = "ROLLBACK"
        reason = "Critical metric breach: " + ", ".join(breaches)

    elif (
        probability < controller.rollback_threshold
        or prediction == 0
    ):
        decision = "ROLLBACK"
        reason = "ML model predicts deployment instability"

    elif argo.get("phase") in ("Degraded", "Unhealthy"):
        decision = "ROLLBACK"
        reason = "Argo Rollouts reports an unhealthy deployment"

    elif (
        probability >= controller.continue_threshold
        and prediction == 1
        and argo.get("phase") in ("Healthy", "Progressing")
    ):
        decision = "CONTINUE"
        reason = "ML prediction is stable and Argo health is acceptable"

    else:
        decision = "HOLD"
        reason = "Deployment requires further monitoring"

    if not argo.get("success"):
        proposed_action = "BLOCKED_ARGO_STATUS_UNAVAILABLE"

    elif decision == "ROLLBACK":
        proposed_action = "ROLLBACK_REQUIRES_APPROVAL"

    elif decision == "HOLD":
        proposed_action = "HOLD_NO_ACTION"

    elif (
        argo.get("phase") == "Healthy"
        and argo.get("current_step", 0) >= 7
    ):
        proposed_action = "NO_ACTION_ROLLOUT_ALREADY_COMPLETED"

    else:
        proposed_action = "PROMOTE_REQUIRES_APPROVAL"

    return {
        "execution_mode": "DRY_RUN_ONLY",
        "executed": False,
        "ml_prediction": (
            "SUCCESS" if prediction == 1 else "FAILURE"
        ),
        "success_probability": round(probability, 4),
        "decision": decision,
        "decision_reason": reason,
        "proposed_argo_action": proposed_action,
        "approval_required": decision in ("ROLLBACK", "CONTINUE"),
        "execution_performed": False,
        "metrics": metrics_data,
        "metric_breaches": breaches,
        "argo_status": argo
    }


# --------------------------------------------------
# LOCAL DEPLOYMENT STATUS
# --------------------------------------------------

@app.get("/deployment/status")
def deployment_status():
    return controller.get_status()


# --------------------------------------------------
# DEPLOYMENT HISTORY
# --------------------------------------------------

@app.get("/deployment/history")
def deployment_history():
    return get_deployments()


# --------------------------------------------------
# REAL KUBERNETES ARGO ROLLOUT STATUS
# --------------------------------------------------

@app.get("/argo/status")
def argo_status():
    result = get_rollout_status()

    if not result.get("success"):
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Unable to retrieve Argo Rollout status",
                "error": result.get("error", "Unknown error")
            }
        )

    return result


# --------------------------------------------------
# HUMAN-APPROVED ROLLBACK WORKFLOW
# --------------------------------------------------

@app.post("/deployment/rollback/request")
def request_rollback(data: RollbackRequest):
    validation = validate_rollback_target(data.target_revision)

    if not validation.get("success"):
        raise HTTPException(
            status_code=400,
            detail=validation.get("error")
        )

    result = create_rollback_request(
        revision=data.target_revision,
        target_hash=validation["target_hash"],
        images=validation["target_images"]
    )

    if not result["success"]:
        raise HTTPException(
            status_code=409,
            detail=result
        )

    return {
        "message": "Rollback approval request created",
        "approval": result,
        "target": validation,
        "execution_performed": False
    }


@app.get("/deployment/rollback/pending")
def pending_rollback_requests():
    return get_rollback_requests("PENDING")


@app.post("/deployment/rollback/approve")
def approve_rollback(data: RollbackReview):
    decision = data.decision.upper()

    if decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=400,
            detail="Decision must be APPROVED or REJECTED"
        )

    # Retrieve the pending request before reviewing it.
    pending_requests = get_rollback_requests("PENDING")

    approval = next(
        (
            item for item in pending_requests
            if item["request_id"] == data.request_id
        ),
        None
    )

    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Pending rollback request not found or already reviewed"
        )

    # Record the human review decision.
    review_result = review_rollback_request(
        request_id=data.request_id,
        decision=decision,
        reviewer=data.reviewer,
        note=data.note
    )

    if not review_result["success"]:
        raise HTTPException(
            status_code=400,
            detail=review_result["error"]
        )

    # A rejection is recorded but never executes a rollback.
    if decision == "REJECTED":
        return {
            "message": "Rollback request rejected",
            "result": review_result,
            "execution_performed": False
        }

    # Execute only after the approval has been recorded.
    execution = rollback_rollout(
        revision=int(approval["target_revision"]),
        expected_hash=approval["target_hash"]
    )

    if not execution.get("success"):
        return {
            "message": "Approval recorded, but rollback execution failed",
            "result": review_result,
            "execution": execution,
            "execution_performed": False
        }

    return {
        "message": "Rollback approved and command submitted to Argo Rollouts",
        "result": review_result,
        "execution": execution,
        "execution_performed": True
    }
