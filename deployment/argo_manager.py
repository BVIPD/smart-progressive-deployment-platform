
import json
import subprocess


ROLLOUT_NAME = "ccrg-platform"
NAMESPACE = "default"


def run_kubectl(arguments):
    try:
        result = subprocess.run(
            ["kubectl"] + arguments,
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr.strip()
            }

        return {
            "success": True,
            "output": result.stdout.strip()
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Kubernetes command timed out"
        }

    except FileNotFoundError:
        return {
            "success": False,
            "error": "kubectl not found"
        }


def get_rollout_status():
    result = run_kubectl([
        "get", "rollout", ROLLOUT_NAME,
        "-n", NAMESPACE, "-o", "json"
    ])

    if not result["success"]:
        return result

    try:
        rollout = json.loads(result["output"])
        status = rollout.get("status", {})
        spec = rollout.get("spec", {})

        return {
            "success": True,
            "name": ROLLOUT_NAME,
            "namespace": NAMESPACE,
            "phase": status.get("phase", "UNKNOWN"),
            "stable_revision_hash": status.get("stableRS"),
            "current_revision_hash": status.get("currentPodHash"),
            "current_step": status.get("currentStepIndex"),
            "replicas": status.get("replicas", 0),
            "ready_replicas": status.get("readyReplicas", 0),
            "available_replicas": status.get("availableReplicas", 0),
            "desired_replicas": spec.get("replicas", 0),
            "conditions": status.get("conditions", [])
        }

    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Unable to parse rollout JSON"
        }


def get_revision_inventory():
    rollout_result = run_kubectl([
        "get", "rollout", ROLLOUT_NAME,
        "-n", NAMESPACE, "-o", "json"
    ])

    if not rollout_result["success"]:
        return rollout_result

    replica_result = run_kubectl([
        "get", "replicasets",
        "-n", NAMESPACE,
        "-l", "app=ccrg-platform",
        "-o", "json"
    ])

    if not replica_result["success"]:
        return replica_result

    try:
        rollout = json.loads(rollout_result["output"])
        replica_data = json.loads(replica_result["output"])

        status = rollout.get("status", {})
        stable_hash = status.get("stableRS")
        current_hash = status.get("currentPodHash")

        revisions = []

        for rs in replica_data.get("items", []):
            metadata = rs.get("metadata", {})
            spec = rs.get("spec", {})
            rs_status = rs.get("status", {})

            annotations = metadata.get("annotations", {})
            labels = metadata.get("labels", {})

            containers = (
                spec.get("template", {})
                .get("spec", {})
                .get("containers", [])
            )

            revisions.append({
                "name": metadata.get("name"),
                "revision": annotations.get(
                    "rollout.argoproj.io/revision"
                ),
                "hash": labels.get(
                    "rollouts-pod-template-hash"
                ),
                "is_stable": (
                    labels.get("rollouts-pod-template-hash")
                    == stable_hash
                ),
                "is_current": (
                    labels.get("rollouts-pod-template-hash")
                    == current_hash
                ),
                "images": [
                    container.get("image")
                    for container in containers
                ],
                "replicas": rs_status.get("replicas", 0),
                "ready_replicas": rs_status.get(
                    "readyReplicas", 0
                )
            })

        revisions.sort(
            key=lambda item: int(item["revision"] or 0),
            reverse=True
        )

        stable_revision = next(
            (
                item["revision"]
                for item in revisions
                if item["is_stable"]
            ),
            None
        )

        return {
            "success": True,
            "phase": status.get("phase", "UNKNOWN"),
            "stable_hash": stable_hash,
            "current_hash": current_hash,
            "stable_revision": stable_revision,
            "current_step": status.get("currentStepIndex"),
            "revisions": revisions
        }

    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "success": False,
            "error": "Unable to inspect ReplicaSet revision data"
        }


def validate_rollback_target(revision):
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        return {
            "success": False,
            "eligible": False,
            "error": "A valid positive revision number is required"
        }

    inventory = get_revision_inventory()

    if not inventory["success"]:
        return {
            "success": False,
            "eligible": False,
            "error": inventory["error"]
        }

    stable_revision = inventory.get("stable_revision")
    stable_hash = inventory.get("stable_hash")
    current_hash = inventory.get("current_hash")

    target = next(
        (
            item for item in inventory["revisions"]
            if item["revision"] == str(revision)
        ),
        None
    )

    if target is None:
        return {
            "success": False,
            "eligible": False,
            "error": "Requested revision does not exist"
        }

    if not stable_hash or not stable_revision:
        return {
            "success": False,
            "eligible": False,
            "error": "Stable revision could not be identified"
        }

    if target["hash"] != stable_hash:
        return {
            "success": False,
            "eligible": False,
            "error": "Rollback target must be the current stable revision"
        }

    if current_hash == stable_hash:
        return {
            "success": False,
            "eligible": False,
            "error": "No rollback required: current version is already stable"
        }

    if inventory["phase"] in ("Healthy", "Completed"):
        return {
            "success": False,
            "eligible": False,
            "error": "Rollout is healthy; rollback is not required"
        }

    return {
        "success": True,
        "eligible": True,
        "requires_human_approval": True,
        "target_revision": revision,
        "target_hash": stable_hash,
        "target_images": target["images"],
        "message": "Target validated. Human approval is still required."
    }


def promote_rollout():
    return {
        "success": False,
        "error": "Promotion is disabled until health checks and execution safeguards are implemented"
    }


def rollback_rollout(revision):
    return {
        "success": False,
        "error": "Rollback execution is disabled until human approval is implemented"
    }
