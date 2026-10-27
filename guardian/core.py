"""CloudBuild Guardian: isolated, auditable incident response sandbox.

IMPORTANT: this package deliberately has NO kubectl, shell execution or live-cluster connector.
It can change only in-memory copies of three synthetic Kubernetes incident fixtures.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from .fixtures import SCENARIOS


class GuardianError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_text(value: Any, limit: int = 850) -> str:
    """Display bounded plain text, not model-produced HTML."""
    if not isinstance(value, str):
        raise GuardianError("Model output is missing required text")
    val = value.strip()
    if not val or len(val) > limit:
        raise GuardianError("Model explanation is empty or too long")
    return val


class Guardian:
    MAX_SESSIONS = 40

    def __init__(self, *, mode: str = "demo", model_client=None):
        if mode not in {"demo", "meta"}:
            raise ValueError("mode must be demo or meta")
        if mode == "meta" and model_client is None:
            raise ValueError("Meta mode requires an explicit model client")
        self.mode = mode
        self.model_client = model_client
        self.sessions: OrderedDict[str, dict] = OrderedDict()
        self.lock = threading.RLock()

    def overview(self) -> dict:
        with self.lock:
            return {
                "product": "CloudBuild Guardian",
                "mode": self.mode,
                "model": "muse-spark-1.3" if self.mode == "meta" else None,
                "execution_scope": "isolated synthetic incident simulation only",
                "live_cluster_access": False,
                "active_sessions": len(self.sessions),
                "scenarios": [{"id": key, "name": item["name"], "service": item["service"],
                               "severity": item["severity"], "summary": item["summary"]}
                              for key, item in SCENARIOS.items()],
            }

    def _event(self, session: dict, event_type: str, detail: dict):
        events = session["events"]
        prev = events[-1]["hash"] if events else "GENESIS"
        body = {
            "seq": len(events) + 1,
            "timestamp": now(),
            "kind": event_type,
            "detail": detail,
            "previous_hash": prev,
        }
        body["hash"] = digest(body)
        events.append(body)

    def _get(self, id_: str) -> dict:
        session = self.sessions.get(id_)
        if session is None:
            raise GuardianError("Incident not found", 404)
        return session

    @staticmethod
    def _public(session: dict) -> dict:
        # Only synthetic safe fields; never return internal client or secret values.
        return {
            k: json.loads(json.dumps(session[k])) for k in
            ("id", "scenario", "title", "namespace", "service", "severity",
             "stage", "revision", "observations", "evidence_hash",
             "diagnosis", "proposal", "validation", "events", "created_at")
        }

    def create(self, scenario_id: str) -> dict:
        if scenario_id not in SCENARIOS:
            raise GuardianError("Unknown scenario; choose one of the listed synthetic incidents")
        fixture = SCENARIOS[scenario_id]
        with self.lock:
            incident_id = secrets.token_hex(8)
            observations = json.loads(json.dumps(fixture["observations"]))
            session = {
                "id": incident_id,
                "scenario": scenario_id,
                "title": fixture["name"],
                "namespace": "guardian-lab",
                "service": fixture["service"],
                "severity": fixture["severity"],
                "stage": "detected",
                "revision": 1,
                "observations": observations,
                "evidence_hash": digest(observations),
                "diagnosis": None,
                "proposal": None,
                "validation": None,
                "events": [],
                "created_at": now(),
            }
            self._event(session, "incident.detected", {
                "scenario": scenario_id, "evidence_hash": session["evidence_hash"],
            })
            self.sessions[incident_id] = session
            if len(self.sessions) > self.MAX_SESSIONS:
                self.sessions.popitem(last=False)
            return self._public(session)

    def get(self, incident_id: str) -> dict:
        with self.lock:
            return self._public(self._get(incident_id))

    def investigate(self, incident_id: str) -> dict:
        with self.lock:
            session = self._get(incident_id)
            if session["stage"] != "detected":
                raise GuardianError("Incident can only be investigated once")
            snapshot = self._public(session)
            fixture = SCENARIOS[session["scenario"]]

            if self.mode == "meta":
                try:
                    raw = self.model_client.diagnose(
                        title=session["title"],
                        service=session["service"],
                        evidence=snapshot["observations"],
                        allowed_actions=[s["repair"]["action"] for s in SCENARIOS.values()],
                    )
                except Exception:
                    # Avoid echoing provider errors (they may contain sensitive information).
                    self._event(session, "model.failed", {
                        "provider": "meta", "safe_message": "Provider unavailable or invalid response"
                    })
                    raise GuardianError("Meta inference failed. No action was proposed or executed.", 502)
                if not isinstance(raw, dict):
                    raise GuardianError("Meta model returned an invalid diagnosis", 502)
                proposed = raw.get("proposed_action")
                explanation = safe_text(raw.get("root_cause"))
                reason = safe_text(raw.get("reasoning"))
                ids = raw.get("evidence_ids")
                if not isinstance(ids, list) or not ids or len(ids) > 8 or any(not isinstance(x, str) for x in ids):
                    raise GuardianError("Model did not cite valid evidence IDs", 502)
                if len(ids) != len(set(ids)):
                    raise GuardianError("Model duplicated evidence IDs", 502)
                source = "meta:muse-spark-1.3"
            else:
                # Never misrepresent the offline fixture diagnosis as AI output.
                proposed = fixture["repair"]["action"]
                explanation = fixture["root_cause"]
                reason = fixture["reasoning"]
                ids = fixture["evidence_ids"]
                source = "scripted-fixture:NOT_AI"

            allowed = fixture["repair"]["action"]
            actual_ids = {e["id"] for e in session["observations"]}
            required = set(fixture["required_evidence_ids"])
            if (not hmac.compare_digest(str(proposed), allowed)
                    or not set(ids).issubset(actual_ids)
                    or not required.issubset(set(ids))):
                self._event(session, "policy.rejected", {
                    "reason": "Action or mandatory corroborating evidence failed the fixture policy",
                    "source": source,
                })
                raise GuardianError("Safety gate blocked proposed action: missing essential evidence or action mismatch", 409)

            session["diagnosis"] = {
                "root_cause": explanation, "reasoning": reason, "evidence_ids": ids,
                "source": source,
            }
            session["proposal"] = {
                "action": allowed, "target": f"guardian-lab/{session['service']}",
                "patch_preview": fixture["repair"]["patch_preview"],
                "risk": "SIMULATED ONLY — no Kubernetes API access",
                "requires_approval": True,
            }
            session["stage"] = "awaiting_approval"
            session["revision"] += 1
            self._event(session, "investigation.completed", {
                "source": source, "action": allowed, "evidence_hash": session["evidence_hash"],
            })
            return self._public(session)

    def approve_and_apply(self, incident_id: str, revision: int, approved: bool) -> dict:
        with self.lock:
            session = self._get(incident_id)
            if session["stage"] != "awaiting_approval":
                raise GuardianError("No pending proposal awaiting approval", 409)
            if type(revision) is not int or revision != session["revision"]:
                raise GuardianError("Stale approval: reload incident before approving", 409)
            if type(approved) is not bool:
                raise GuardianError("Explicit approval or rejection is required", 400)
            if not approved:
                session["stage"] = "rejected"
                session["revision"] += 1
                self._event(session, "human.rejected", {"action": session["proposal"]["action"]})
                return self._public(session)

            fixture = SCENARIOS[session["scenario"]]
            if session["proposal"]["action"] != fixture["repair"]["action"]:
                raise GuardianError("Action allowlist check failed", 409)
            self._event(session, "human.approved", {
                "action": session["proposal"]["action"], "revision": revision,
            })
            # This is intentionally an in-memory synthetic patch. No kubectl client or shell.
            session["observations"] = json.loads(json.dumps(fixture["after"]))
            session["evidence_hash"] = digest(session["observations"])
            session["stage"] = "applied_simulation"
            session["revision"] += 1
            self._event(session, "simulation.patched", {
                "scope": "in-memory", "action": fixture["repair"]["action"],
                "evidence_hash": session["evidence_hash"],
            })
            return self._public(session)

    def verify(self, incident_id: str) -> dict:
        with self.lock:
            session = self._get(incident_id)
            if session["stage"] not in {"applied_simulation", "verified"}:
                raise GuardianError("Human-approved sandbox patch must run before verification", 409)
            fixture = SCENARIOS[session["scenario"]]
            expected = digest(fixture["after"])
            observed = digest(session["observations"])
            passed = hmac.compare_digest(expected, observed)
            if session["stage"] != "verified":
                session["validation"] = {
                    "passed": passed,
                    "proof": fixture["verification"],
                    "expected_hash": expected,
                    "observed_hash": observed,
                    "environment": "synthetic guardian-lab",
                    "claim": "Simulated recovery verified; no real infrastructure modified",
                }
                session["stage"] = "verified" if passed else "failed_verification"
                session["revision"] += 1
                self._event(session, "verification.completed", {"passed": passed, "hash": observed})
            return self._public(session)

    def check_ledger(self, incident_id: str) -> bool:
        with self.lock:
            events = self._get(incident_id)["events"]
            prev = "GENESIS"
            for idx, item in enumerate(events, 1):
                payload = {key: val for key, val in item.items() if key != "hash"}
                if item["seq"] != idx or item["previous_hash"] != prev:
                    return False
                if digest(payload) != item["hash"]:
                    return False
                prev = item["hash"]
            return True
