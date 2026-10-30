
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_home():
    response = client.get("/")
    assert response.status_code == 200


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200


def test_version():
    response = client.get("/version")
    assert response.status_code == 200


def test_deployment_status():
    response = client.get("/deployment/status")
    assert response.status_code == 200


def test_deployment_history():
    response = client.get("/deployment/history")
    assert response.status_code == 200


def test_prediction():
    response = client.post(
        "/predict",
        json={
            "cpu_usage": 45,
            "memory_usage": 50,
            "latency": 120,
            "error_rate": 0.5,
            "traffic": 3000
        }
    )

    assert response.status_code == 200
    assert "deployment_prediction" in response.json()
