"""Synthetic Kubernetes incident fixtures. Invented data; not taken from production."""
SCENARIOS = {
    "readiness": {
        "name": "Broken readiness probe",
        "summary": "A healthy API cannot receive production traffic because its probe targets the wrong path.",
        "service": "checkout-api",
        "severity": "HIGH",
        "observations": [
            {"id": "OBS-01", "source": "kubectl get pods", "text":
             "deployment/checkout-api: 2 desired, 2 running, 0 ready (guardian-lab)."},
            {"id": "OBS-02", "source": "kubectl describe pod", "text":
             "Readiness probe HTTP GET /ready on port 8080 returned 404; 14 failures in 4m."},
            {"id": "OBS-03", "source": "application access log", "text":
             "GET /healthz responded HTTP 200 repeatedly; GET /ready responded 404."},
            {"id": "OBS-04", "source": "deployment spec", "text":
             "readinessProbe.httpGet.path=/ready; container listens on port 8080."},
        ],
        "root_cause": "ReadinessProbe points to /ready, but the application exposes /healthz.",
        "reasoning": "The process runs and /healthz returns 200; only the configured /ready health endpoint fails with 404. Routing excludes unready pods.",
        "evidence_ids": ["OBS-01", "OBS-02", "OBS-03", "OBS-04"],
        "required_evidence_ids": ["OBS-02", "OBS-03"],
        "repair": {
            "action": "correct_readiness_probe",
            "patch_preview": "spec.template.spec.containers[0].readinessProbe.httpGet.path: /ready → /healthz",
        },
        "after": [
            {"id": "POST-01", "source": "synthetic kubelet", "text":
             "HTTP GET /healthz on :8080 returned HTTP 200 for both simulated pods."},
            {"id": "POST-02", "source": "synthetic deployment", "text":
             "checkout-api: desired 2, running 2, ready 2 (sandbox simulation)."},
            {"id": "POST-03", "source": "synthetic service", "text":
             "Service endpoints: 2 ready simulated endpoints."},
        ],
        "verification": "Expected 2/2 simulated pods ready and GET /healthz -> 200.",
    },
    "oom": {
        "name": "OOMKilled worker",
        "summary": "A batch worker repeatedly restarts after exhausting its configured memory limit.",
        "service": "image-worker",
        "severity": "HIGH",
        "observations": [
            {"id": "OBS-01", "source": "kubectl get pods", "text":
             "image-worker-0: CrashLoopBackOff, restartCount=6, lastExit=137."},
            {"id": "OBS-02", "source": "kubectl describe pod", "text":
             "lastState.terminated.reason=OOMKilled; container memory limit 128Mi."},
            {"id": "OBS-03", "source": "synthetic metrics", "text":
             "Working set before termination reached 124Mi; profiling test peak 188Mi."},
            {"id": "OBS-04", "source": "capacity simulation", "text":
             "Sandbox node has 2Gi unallocated capacity; raising limit to 256Mi fits."},
        ],
        "root_cause": "The worker's 128Mi memory limit is below its observed 188Mi task peak.",
        "reasoning": "The OOMKilled termination and memory profile match. A bounded 256Mi limit passes the synthetic capacity check.",
        "evidence_ids": ["OBS-01", "OBS-02", "OBS-03", "OBS-04"],
        "required_evidence_ids": ["OBS-02", "OBS-03"],
        "repair": {
            "action": "set_memory_limit_256mi",
            "patch_preview": "spec.template.spec.containers[0].resources.limits.memory: 128Mi → 256Mi",
        },
        "after": [
            {"id": "POST-01", "source": "synthetic deployment", "text":
             "image-worker: memory limit now 256Mi; restartCount remained 0 in the simulated check."},
            {"id": "POST-02", "source": "synthetic metrics", "text":
             "Task working set max 188Mi < 256Mi sandbox limit."},
            {"id": "POST-03", "source": "synthetic queue", "text":
             "10/10 synthetic image jobs completed without OOM."},
        ],
        "verification": "Simulated memory stays under 256Mi and batch test succeeds 10/10.",
    },
    "imagepull": {
        "name": "Unpullable container image",
        "summary": "A rollout stalls because a deployment references an unavailable image tag.",
        "service": "notification-service",
        "severity": "MEDIUM",
        "observations": [
            {"id": "OBS-01", "source": "kubectl get pods", "text":
             "notification-service: 0 ready; ErrImagePull / ImagePullBackOff."},
            {"id": "OBS-02", "source": "synthetic pod events", "text":
             "Failed pulling registry.demo.invalid/team/notifier:v9-typo: manifest unknown."},
            {"id": "OBS-03", "source": "synthetic release manifest", "text":
             "Latest signed release tag for this fixture is v8.2.1 (verified fixture digest)."},
            {"id": "OBS-04", "source": "synthetic policy", "text":
             "Allowed rollback target is only the fixture's pinned digest, not arbitrary image refs."},
        ],
        "root_cause": "The workload references a nonexistent container image tag.",
        "reasoning": "Image pull event reports manifest unknown and the local signed-fixture manifest records the last good immutable image.",
        "evidence_ids": ["OBS-01", "OBS-02", "OBS-03", "OBS-04"],
        "required_evidence_ids": ["OBS-02", "OBS-03"],
        "repair": {
            "action": "restore_pinned_image",
            "patch_preview": "container image: v9-typo → notifier@sha256:<fixture-approved-digest> (simulation)",
        },
        "after": [
            {"id": "POST-01", "source": "synthetic registry", "text":
             "Fixture-approved immutable digest resolves and signature check passes."},
            {"id": "POST-02", "source": "synthetic deployment", "text":
             "notification-service: 1/1 simulated pods Ready."},
            {"id": "POST-03", "source": "synthetic test", "text":
             "Synthetic notification health endpoint responds 200."},
        ],
        "verification": "Simulated registry digest verified and deployment is 1/1 ready.",
    },
}
