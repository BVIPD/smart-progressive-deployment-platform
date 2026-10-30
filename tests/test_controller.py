
from deployment.controller import DeploymentController


def test_continue():
    c = DeploymentController()
    result = c.evaluate(1, 0.95, {
        "cpu_usage": 40,
        "memory_usage": 50,
        "latency": 100,
        "error_rate": 0.5
    })
    assert result["decision"] == "CONTINUE"


def test_hold():
    c = DeploymentController()
    result = c.evaluate(1, 0.70, {
        "cpu_usage": 40,
        "memory_usage": 50,
        "latency": 100,
        "error_rate": 0.5
    })
    assert result["decision"] == "HOLD"


def test_rollback():
    c = DeploymentController()
    result = c.evaluate(0, 0.30, {
        "cpu_usage": 40,
        "memory_usage": 50,
        "latency": 100,
        "error_rate": 0.5
    })
    assert result["decision"] == "ROLLBACK"


def test_critical_metric_breach():
    c = DeploymentController()
    result = c.evaluate(1, 0.95, {
        "cpu_usage": 98,
        "memory_usage": 50,
        "latency": 100,
        "error_rate": 0.5
    })
    assert result["decision"] == "ROLLBACK"
    assert "cpu_usage" in result["decision_reason"]
