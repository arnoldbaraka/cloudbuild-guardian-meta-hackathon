"""One-shot Meta Muse Spark activation and credit-usage verification.

Run *interactively on your own trusted terminal*:
    python3 -m guardian.activate

The API key is entered using getpass and held only in process memory.
No file, command line argument, browser field, shell history or deployment change.
One small request is attempted; no automatic retries or subsequent calls.
"""
from __future__ import annotations

import getpass
import json
import os
import sys

from .core import Guardian, GuardianError
from .meta import MetaClient


def one_live_check(client: MetaClient) -> dict:
    """Make one bounded Muse Spark call using a synthetic incident, nothing else."""
    engine = Guardian(mode="meta", model_client=client)
    incident = engine.create("readiness")
    try:
        investigated = engine.investigate(incident["id"])
    except GuardianError as exc:
        return {
            "model": client.MODEL,
            "attempts": client.calls,
            "model_validated_and_policy_approved": False,
            "status": "BLOCKED_BY_POLICY_OR_PROVIDER",
            "status_code": exc.status,
            "message": str(exc),
            "usage_tokens": dict(client.last_usage),
            "meta_http_status": client.last_http_status,
            "live_kubernetes_access": False,
        }
    return {
        "model": client.MODEL,
        "attempts": client.calls,
        "model_validated_and_policy_approved": investigated["stage"] == "awaiting_approval",
        "status": "META_RESPONSE_VALIDATED",
        "evidence_ids": investigated["diagnosis"]["evidence_ids"],
        "source": investigated["diagnosis"]["source"],
        "usage_tokens": dict(client.last_usage),
        "action_executed": False,
        "live_kubernetes_access": False,
        "audit_chain_valid": engine.check_ledger(incident["id"]),
    }


def main() -> int:
    print("CloudBuild Guardian / Meta Model API — ONE-CALL LIVE VERIFICATION")
    print("Only synthetic evidence will be sent to the Meta Model API.")
    print("This does not connect to Kubernetes or enable public access.")
    print("This could incur a small API charge; a billing alert is NOT a hard spending limit.")
    if not sys.stdin.isatty():
        print("ERROR: Run interactively in your own SSH terminal; do not pass the key as a command argument.")
        return 2
    key = getpass.getpass("Paste MODEL_API_KEY securely (hidden input): ").strip()
    if not key:
        print("No key supplied. No API call was made.")
        return 2
    # Explicitly inject into this ephemeral client only; never write to a file.
    try:
        client = MetaClient(api_key=key, max_calls=1)
        result = one_live_check(client)
    except Exception:
        print("API attempt failed. No sensitive error details displayed. No automatic retry.")
        return 1
    finally:
        key = None
    print(json.dumps(result, indent=2, sort_keys=True))
    print("The API key was not saved; the local demo server remains in scripted mode.")
    return 0 if result["model_validated_and_policy_approved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
