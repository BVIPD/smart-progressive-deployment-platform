# Smart Progressive Deployment Platform

An ML-driven progressive delivery platform that evaluates deployment stability using application metrics, integrates with Kubernetes and Argo Rollouts, and provides monitoring through Prometheus and Grafana.

## Project overview

The platform combines a FastAPI application, a trained machine-learning model, deployment decision logic, Kubernetes rollout inspection, and monitoring endpoints. It evaluates CPU usage, memory usage, latency, error rate, and traffic to estimate deployment success and produce a deployment recommendation.

The decision controller can return:

- **CONTINUE** — the model and available rollout information meet the configured continuation conditions.
- **HOLD** — more monitoring is required or rollout status cannot be confirmed.
- **ROLLBACK** — the model, configured metric limits, or rollout health indicates instability. This is a decision state, not proof that a Kubernetes rollback has been executed.

The project includes a human-review workflow for rollback requests. At the current implementation stage, approving a request records the review in SQLite; it does **not** execute a Kubernetes rollback.

## Main features

- FastAPI service with interactive API documentation.
- ML prediction endpoint backed by a trained scikit-learn model.
- Deployment evaluation using CPU, memory, latency, error rate, and traffic inputs.
- Configurable CONTINUE / HOLD / ROLLBACK decision thresholds.
- Argo Rollouts status and revision inventory integration.
- Dry-run deployment evaluation that reports proposed actions without executing them.
- SQLite deployment history and rollback approval records.
- Prometheus metrics endpoint and scrape configuration for Docker, Kubernetes stable, and Kubernetes canary services.
- Grafana monitoring dashboard.
- Browser-based deployment dashboard showing system metrics, deployment status, success probability, and deployment history.
- Automated tests for API, controller, rollback API, and rollback database behavior.

## Architecture

```text
                    +-----------------------------+
                    |       Browser Dashboard     |
                    |       /dashboard            |
                    +--------------+--------------+
                                   |
                                   v
+------------------+     +---------+----------+      +-------------------+
| Metrics / Inputs |---->|       FastAPI      |----->| ML Model          |
| CPU, memory,     |     | /predict           |      | deployment_model  |
| latency, errors, |     | /deployment/evaluate|     | .pkl              |
| traffic          |     | /deployment/dry-run |     +-------------------+
+------------------+     +---------+----------+
                                   |
                                   v
                         +---------+----------+
                         | Deployment         |
                         | Controller         |
                         | CONTINUE / HOLD /  |
                         | ROLLBACK decision  |
                         +---------+----------+
                                   |
                    +--------------+---------------+
                    |                              |
                    v                              v
          +---------------------+       +----------------------+
          | Argo Rollouts       |       | SQLite               |
          | status/revisions    |       | deployment history   |
          | target validation   |       | rollback reviews     |
          +---------------------+       +----------------------+

       Prometheus scrapes Docker, Kubernetes stable and canary
                              |
                              v
                         +---------+
                         | Grafana |
                         +---------+
```

## Technology stack

| Layer | Technology |
|---|---|
| API and dashboard backend | Python, FastAPI, Uvicorn |
| Machine learning | scikit-learn, pandas, NumPy, joblib |
| System metrics | psutil |
| Containerization | Docker |
| Orchestration | Kubernetes |
| Progressive delivery | Argo Rollouts |
| Traffic management | Istio |
| Metrics collection | Prometheus |
| Monitoring visualization | Grafana |
| Persistence | SQLite |
| Testing | pytest, FastAPI TestClient |

## Repository structure

```text
CCRG_PR1/
├── app/
│   ├── main.py
│   ├── dashboard.html
│   └── __init__.py
├── dataset/
│   ├── deployment_metrics.csv
│   └── generate_dataset.py
├── deployment/
│   ├── argo_manager.py
│   ├── controller.py
│   └── database.py
├── evidence/
│   ├── analysis-runs.txt
│   ├── final-pods.txt
│   ├── final-rollout.txt
│   └── final-virtualservice.yaml
├── kubernetes/
│   ├── analysis-run-test.yaml
│   ├── analysis-template.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── virtualservice.yaml
├── ml/
│   ├── deployment_model.pkl
│   └── train_model.py
├── monitoring/
│   └── prometheus.yml
├── tests/
│   ├── test_api.py
│   ├── test_controller.py
│   ├── test_rollback_api.py
│   └── test_rollback_database.py
├── .dockerignore
├── .gitignore
├── Dockerfile
├── LICENSE
└── requirements.txt
```

## Prerequisites

Install or configure:

- Python 3.13 or a compatible Python version for the Docker image.
- Docker Desktop.
- Kubernetes enabled in Docker Desktop, or another Kubernetes cluster.
- `kubectl`.
- Argo Rollouts controller and the `kubectl-argo-rollouts` plugin.
- Istio when using the included Istio traffic-routing configuration.
- Prometheus and Grafana for monitoring.

The Kubernetes resources and service names in the included configuration are project-specific. Review namespace, image names, ports, and cluster context before applying manifests to another environment.

## Run the FastAPI application locally

From the project root:

```powershell
cd C:\CCRG_PR1

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt

uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

Open:

- Dashboard: http://127.0.0.1:8002/dashboard
- API documentation: http://127.0.0.1:8002/docs
- Health: http://127.0.0.1:8002/health
- Prometheus exposition: http://127.0.0.1:8002/prometheus

The application expects the trained model at `ml/deployment_model.pkl`.

## Build and run with Docker

Build the image:

```powershell
docker build -t ccrg-platform:v1 .
```

Run the container:

```powershell
docker run -d --name ccrg-platform-local -p 8000:8000 ccrg-platform:v1
```

Check the service:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

If the container name or host port is already in use, choose a different container name or host port.

## Machine-learning workflow

The dataset is stored in `dataset/deployment_metrics.csv`. The dataset generation script is `dataset/generate_dataset.py`, and model training is implemented in `ml/train_model.py`.

Generate the dataset when required:

```powershell
python dataset/generate_dataset.py
```

Train the model:

```powershell
python ml/train_model.py
```

The trained model is stored as `ml/deployment_model.pkl`.

The model predicts deployment success from the metric features used during training. The deployment controller combines the prediction and probability with metric thresholds and Argo Rollouts status to produce a decision. A prediction is an estimate, not a guarantee of deployment safety.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Root endpoint |
| GET | `/dashboard` | Browser monitoring dashboard |
| GET | `/health` | Application health |
| GET | `/version` | Application version |
| GET | `/metrics` | Application/system metrics in JSON |
| GET | `/prometheus` | Prometheus exposition format |
| POST | `/predict` | ML deployment prediction |
| POST | `/deployment/evaluate` | Evaluate deployment and record decision |
| POST | `/deployment/dry-run` | Evaluate a proposed action without executing it |
| GET | `/deployment/status` | Controller deployment status |
| GET | `/deployment/history` | Recorded deployment history |
| GET | `/argo/status` | Argo Rollouts status |
| POST | `/deployment/rollback/request` | Validate target and create approval request |
| GET | `/deployment/rollback/pending` | List pending rollback requests |
| POST | `/deployment/rollback/approve` | Record approval or rejection |

See `/docs` for the request and response schemas.

## Deployment decisions

The controller uses configured limits and probability thresholds. The current controller configuration is:

| Metric / threshold | Value |
|---|---:|
| CPU usage limit | 95% |
| Memory usage limit | 95% |
| Latency limit | 2000 ms |
| Error rate limit | 5% |
| Continue probability threshold | 0.85 |
| Rollback probability threshold | 0.60 |

These are project configuration values, not universal production thresholds. They should be calibrated for the application and workload before production use.

The dry-run endpoint explicitly reports that no deployment action was executed. The evaluation endpoint records the decision and checks Argo status; it does not itself prove that traffic was promoted or rolled back.

## Kubernetes and Argo Rollouts

The `kubernetes/` directory contains the deployment, service, analysis template, test analysis run, and Istio VirtualService manifests.

Inspect the rollout:

```powershell
kubectl-argo-rollouts get rollout ccrg-platform -n default
```

Inspect pods:

```powershell
kubectl get pods -n default
```

Review the manifests and current cluster context before applying any resource changes. Do not apply a new rollout or trigger a rollback merely to test the API.

### Rollback workflow limitation

The current rollback workflow supports target inspection/validation, request creation, pending-request listing, and approval/rejection recording. The `rollback_rollout()` function is intentionally disabled, and the approval API returns `execution_performed: false`.

Therefore, **actual Kubernetes rollback execution after approval is not implemented in this repository version**. The platform should be described as providing rollback decision support and a human-reviewed approval record, not as automatically executing rollback.

## Prometheus and Grafana

Prometheus scrape configuration is in `monitoring/prometheus.yml`. It defines three targets:

- Docker application: `host.docker.internal:8000`
- Kubernetes stable service: `host.docker.internal:8001`
- Kubernetes canary service: `host.docker.internal:8003`

The scrape path is `/prometheus`, with a configured scrape interval of five seconds.

Useful local addresses in the demonstrated environment:

- Prometheus: http://127.0.0.1:9090
- Prometheus targets: http://127.0.0.1:9090/targets
- Grafana: http://127.0.0.1:3000

The Grafana dashboard used in the demonstrated environment is titled **Smart Progressive Deployment Monitoring**. Its visible panels include application availability, CPU/memory usage, HTTP request rate, application health, and ML deployment success probability.

Prometheus target health `UP` confirms successful metric scraping; it does not independently guarantee application-level correctness. The application latency metric is an observed average, not a p95 latency measurement. The traffic metric is a cumulative request count, not requests per second.

## Tests

Run the test suite from the project root:

```powershell
python -m pytest tests -q
```

The verified project test run completed with **26 passed**. Three non-failing warnings were reported: a Starlette/httpx deprecation warning and scikit-learn feature-name warnings.

Run syntax checks:

```powershell
python -m py_compile app/main.py deployment/controller.py deployment/argo_manager.py deployment/database.py
```

## Verified environment snapshot

The following were verified in the demonstrated local environment during project validation:

- FastAPI dashboard returned HTTP 200.
- Application health endpoint returned `healthy`.
- Argo Rollouts reported `Healthy`, step 7/7, with five desired and five ready replicas.
- Prometheus reported all three configured scrape targets as `UP`.
- Grafana health endpoint returned HTTP 200.
- The test suite reported 26 passed.

These are environment-specific verification results, not a guarantee that a fresh installation will have the same cluster state.

## Safety and production considerations

This repository is an academic project and demonstration environment. Before production use, add appropriate authentication and authorization, secure reviewer identity, protect secrets, validate rollback targets against an explicit known-good revision policy, add concurrency safeguards, and test rollback execution in an isolated cluster. Review metric thresholds and model performance against representative production data.

Do not expose Prometheus, Grafana, or the API publicly without appropriate access controls.

## License

This project includes the MIT License. See [LICENSE](LICENSE).
