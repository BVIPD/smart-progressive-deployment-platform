
from datetime import datetime


class DeploymentController:

    def __init__(self):
        self.stable_version = "v1"
        self.candidate_version = "v2"
        self.active_version = "v2"
        self.status = "CANARY_RUNNING"
        self.history = []

        self.continue_threshold = 0.85
        self.rollback_threshold = 0.60

        self.limits = {
            "cpu_usage": 95,
            "memory_usage": 95,
            "latency": 2000,
            "error_rate": 5
        }

    def evaluate(
        self,
        prediction,
        probability,
        metrics=None,
        argo_status=None
    ):
        metrics = metrics or {}

        breaches = [
            key
            for key, limit in self.limits.items()
            if key in metrics and metrics[key] >= limit
        ]

        argo_available = (
            argo_status is None
            or argo_status.get("success", False)
        )

        argo_phase = (
            argo_status.get("phase", "UNKNOWN")
            if argo_status
            else "NOT_CHECKED"
        )

        if not argo_available:
            decision = "HOLD"
            reason = "Argo Rollouts status unavailable"

        elif breaches:
            decision = "ROLLBACK"
            reason = "Critical metric breach: " + ", ".join(breaches)

        elif probability < self.rollback_threshold or prediction == 0:
            decision = "ROLLBACK"
            reason = "ML model predicts deployment instability"

        elif argo_phase in ("Degraded", "Unhealthy"):
            decision = "ROLLBACK"
            reason = "Argo Rollouts reports an unhealthy deployment"

        elif (
            probability >= self.continue_threshold
            and prediction == 1
            and argo_phase in (
                "Healthy",
                "Progressing",
                "NOT_CHECKED"
            )
        ):
            decision = "CONTINUE"
            reason = (
                "ML prediction is stable and Argo health is acceptable"
            )

        else:
            decision = "HOLD"
            reason = "Deployment requires further monitoring"

        if decision == "ROLLBACK":
            self.status = "ROLLBACK_PENDING_APPROVAL"

        elif decision == "HOLD":
            self.status = "DEPLOYMENT_ON_HOLD"

        else:
            self.status = "DEPLOYMENT_CONTINUED"

        result = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "decision": decision,
            "active_version": self.active_version,
            "deployment_status": self.status,
            "success_probability": round(float(probability), 4),
            "decision_reason": reason,
            "metric_breaches": breaches,
            "argo_phase": argo_phase,
            "metrics": metrics,
            "approval_required": decision == "ROLLBACK",
            "execution_performed": False
        }

        self.history.append(result)

        return result

    def get_status(self):
        return {
            "stable_version": self.stable_version,
            "candidate_version": self.candidate_version,
            "active_version": self.active_version,
            "deployment_status": self.status
        }

    def get_history(self):
        return self.history
