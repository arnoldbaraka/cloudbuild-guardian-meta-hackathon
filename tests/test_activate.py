"""One-shot Meta activation tests. These use only fake responses, never real credits."""
import io
import json
import unittest
from unittest.mock import patch

from guardian.activate import one_live_check, main
from guardian.meta import MetaClient


class ActivateTests(unittest.TestCase):
    @staticmethod
    def fake_client(*, bad=False):
        def transport(body):
            request = json.loads(body)
            assert request["max_completion_tokens"] <= 1024
            action = "kubectl delete -A" if bad else "correct_readiness_probe"
            return {
                "choices": [{"message": {"content": json.dumps({
                    "root_cause": "The endpoint is incorrect",
                    "reasoning": "OBS-02 and OBS-03 show the mismatch",
                    "proposed_action": action,
                    "evidence_ids": ["OBS-02", "OBS-03"],
                })}}],
                "usage": {"prompt_tokens": 222, "completion_tokens": 88, "total_tokens": 310},
            }
        return MetaClient(api_key="FAKE-TEST-ONLY", transport=transport, max_calls=1)

    def test_one_call_uses_real_meta_adapter_and_does_not_apply_patch(self):
        client = self.fake_client()
        result = one_live_check(client)
        self.assertEqual(result["status"], "META_RESPONSE_VALIDATED")
        self.assertEqual(result["source"], "meta:muse-spark-1.3")
        self.assertEqual(result["attempts"], 1)
        self.assertTrue(result["audit_chain_valid"])
        self.assertFalse(result["action_executed"])
        self.assertFalse(result["live_kubernetes_access"])
        self.assertEqual(result["usage_tokens"]["total_tokens"], 310)
        self.assertNotIn("FAKE-TEST-ONLY", json.dumps(result))

    def test_unsafe_model_action_blocked_after_single_call(self):
        result = one_live_check(self.fake_client(bad=True))
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["status_code"], 409)
        self.assertFalse(result["model_validated_and_policy_approved"])
        self.assertFalse(result["live_kubernetes_access"])

    def test_no_tty_no_key_read_or_network_call(self):
        with patch("guardian.activate.sys.stdin.isatty", return_value=False):
            with patch("guardian.activate.getpass.getpass") as getpass:
                with patch("sys.stdout", new_callable=io.StringIO) as output:
                    rc = main()
        self.assertEqual(rc, 2)
        getpass.assert_not_called()
        self.assertIn("Run interactively", output.getvalue())


if __name__ == "__main__":
    unittest.main()
