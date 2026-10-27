"""Offline deterministic safety tests; no production K8s, network or API calls."""
import json
import unittest

from guardian.core import Guardian, GuardianError
from guardian.fixtures import SCENARIOS


class BadModel:
    def __init__(self, action):
        self.action = action

    def diagnose(self, **kwargs):
        return {
            "root_cause": "Synthetic incident mismatch.",
            "reasoning": "I want an unsafe action",
            "proposed_action": self.action,
            "evidence_ids": ["OBS-01"],
        }


class GoodModel:
    def diagnose(self, **kwargs):
        return {
            "root_cause": "Readiness path does not match actual health endpoint.",
            "reasoning": "Probe returns 404 although application is live.",
            "proposed_action": "correct_readiness_probe",
            "evidence_ids": ["OBS-02", "OBS-03"],
        }


class CoreSafetyTests(unittest.TestCase):
    def setUp(self):
        self.g = Guardian()

    def test_all_three_incidents_can_be_recovered_in_sandbox(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                start = self.g.create(scenario)
                self.assertEqual(start["stage"], "detected")
                self.assertTrue(self.g.check_ledger(start["id"]))
                analyzed = self.g.investigate(start["id"])
                self.assertIn("NOT_AI", analyzed["diagnosis"]["source"])
                self.assertTrue(analyzed["proposal"]["requires_approval"])
                self.assertEqual(analyzed["stage"], "awaiting_approval")
                patched = self.g.approve_and_apply(start["id"], analyzed["revision"], True)
                self.assertEqual(patched["stage"], "applied_simulation")
                verified = self.g.verify(start["id"])
                self.assertTrue(verified["validation"]["passed"])
                self.assertEqual(verified["stage"], "verified")
                self.assertTrue(self.g.check_ledger(start["id"]))

    def test_approval_without_investigation_denied(self):
        start = self.g.create("readiness")
        with self.assertRaises(GuardianError):
            self.g.approve_and_apply(start["id"], start["revision"], True)

    def test_approval_must_be_boolean(self):
        start = self.g.investigate(self.g.create("oom")["id"])
        with self.assertRaises(GuardianError):
            self.g.approve_and_apply(start["id"], start["revision"], "true")

    def test_stale_revision_is_rejected(self):
        start = self.g.investigate(self.g.create("oom")["id"])
        with self.assertRaises(GuardianError) as ctx:
            self.g.approve_and_apply(start["id"], start["revision"] - 1, True)
        self.assertEqual(ctx.exception.status, 409)

    def test_rejected_proposal_never_changes_evidence(self):
        start = self.g.investigate(self.g.create("imagepull")["id"])
        before = start["evidence_hash"]
        rejected = self.g.approve_and_apply(start["id"], start["revision"], False)
        self.assertEqual(rejected["stage"], "rejected")
        self.assertEqual(rejected["evidence_hash"], before)
        with self.assertRaises(GuardianError):
            self.g.verify(start["id"])

    def test_tampered_ledger_detected(self):
        incident = self.g.create("readiness")
        self.assertTrue(self.g.check_ledger(incident["id"]))
        self.g.sessions[incident["id"]]["events"][0]["detail"]["scenario"] = "altered"
        self.assertFalse(self.g.check_ledger(incident["id"]))

    def test_model_command_cannot_pass_policy(self):
        g = Guardian(mode="meta", model_client=BadModel("kubectl delete namespace production"))
        incident = g.create("readiness")
        with self.assertRaises(GuardianError) as ctx:
            g.investigate(incident["id"])
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(g.get(incident["id"])["stage"], "detected")
        self.assertTrue(g.check_ledger(incident["id"]))

    def test_model_bad_evidence_cannot_pass_policy(self):
        class Fake:
            def diagnose(self, **kwargs):
                return {"root_cause": "Wrong probe", "reasoning": "Evidence",
                        "proposed_action": "correct_readiness_probe",
                        "evidence_ids": ["OBS-FAKE"]}
        g = Guardian(mode="meta", model_client=Fake())
        incident = g.create("readiness")
        with self.assertRaises(GuardianError):
            g.investigate(incident["id"])
        self.assertEqual(g.get(incident["id"])["stage"], "detected")

    def test_model_cannot_cite_only_irrelevant_evidence(self):
        class MissingCorroboration:
            def diagnose(self, **kwargs):
                return {"root_cause": "Wrong path", "reasoning": "Only one event",
                        "proposed_action": "correct_readiness_probe",
                        "evidence_ids": ["OBS-01"]}
        g = Guardian(mode="meta", model_client=MissingCorroboration())
        incident = g.create("readiness")
        with self.assertRaises(GuardianError) as ctx:
            g.investigate(incident["id"])
        self.assertEqual(ctx.exception.status, 409)
        self.assertTrue(g.check_ledger(incident["id"]))

    def test_valid_meta_proposal_still_requires_approval(self):
        g = Guardian(mode="meta", model_client=GoodModel())
        start = g.create("readiness")
        analyzed = g.investigate(start["id"])
        self.assertEqual(analyzed["diagnosis"]["source"], "meta:muse-spark-1.3")
        self.assertEqual(analyzed["stage"], "awaiting_approval")
        self.assertEqual(analyzed["observations"], start["observations"])
        self.assertTrue(g.check_ledger(start["id"]))

    def test_meta_failure_not_misrepresented_as_scripted(self):
        class Down:
            def diagnose(self, **kwargs):
                raise ConnectionError("provider secret=should-not-appear")
        g = Guardian(mode="meta", model_client=Down())
        incident = g.create("readiness")
        with self.assertRaises(GuardianError) as ctx:
            g.investigate(incident["id"])
        self.assertEqual(ctx.exception.status, 502)
        self.assertNotIn("secret=", str(ctx.exception))
        self.assertEqual(g.get(incident["id"])["stage"], "detected")

    def test_synthetic_only_and_invalid_scenario(self):
        self.assertFalse(self.g.overview()["live_cluster_access"])
        with self.assertRaises(GuardianError):
            self.g.create("production")

    def test_sessions_are_bounded(self):
        for i in range(Guardian.MAX_SESSIONS + 8):
            self.g.create("readiness")
        self.assertEqual(len(self.g.sessions), Guardian.MAX_SESSIONS)

    def test_incident_public_api_does_not_leak_fake_sensitive_fields(self):
        start = self.g.create("readiness")
        out = json.dumps(start)
        self.assertNotIn("api_key", out)
        self.assertEqual(start["namespace"], "guardian-lab")


if __name__ == "__main__":
    unittest.main()
