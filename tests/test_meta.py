"""Meta integration tests with fake provider. Does not spend API credits."""
import json
import unittest
from guardian.meta import MetaClient, MetaInferenceError


class MetaClientTests(unittest.TestCase):
    def inputs(self):
        return {
            "title": "readiness failed",
            "service": "checkout-api",
            "evidence": [{"id": "OBS-01", "source": "test", "text": "Probe returned 404"}],
            "allowed_actions": ["correct_readiness_probe"],
        }

    def test_official_endpoint_and_model(self):
        self.assertEqual(MetaClient.ENDPOINT, "https://api.meta.ai/v1/chat/completions")
        self.assertEqual(MetaClient.MODEL, "muse-spark-1.3")

    def test_model_contract_and_token_usage(self):
        recorded = []
        def transport(body):
            recorded.append(json.loads(body))
            return {"choices": [{"message": {"content": json.dumps({
                "root_cause": "Wrong readiness endpoint",
                "reasoning": "HTTP 404 recorded",
                "proposed_action": "correct_readiness_probe",
                "evidence_ids": ["OBS-01"],
            })}}], "usage": {"total_tokens": 91, "prompt_tokens": 71, "completion_tokens": 20}}
        client = MetaClient(api_key="test-not-a-real-key", transport=transport)
        parsed = client.diagnose(**self.inputs())
        self.assertEqual(parsed["proposed_action"], "correct_readiness_probe")
        self.assertEqual(recorded[0]["model"], "muse-spark-1.3")
        self.assertEqual(recorded[0]["messages"][0]["role"], "developer")
        self.assertEqual(client.last_usage["total_tokens"], 91)

    def test_hard_call_count_cap(self):
        def transport(body):
            return {"choices": [{"message": {"content": "{}"}}]}
        client = MetaClient(api_key="fake", transport=transport, max_calls=1)
        client.diagnose(**self.inputs())
        with self.assertRaises(MetaInferenceError):
            client.diagnose(**self.inputs())
        self.assertEqual(client.calls, 1)

    def test_invalid_response_fails_without_fallback(self):
        client = MetaClient(api_key="fake", transport=lambda body: {
            "choices": [{"message": {"content": "not a json response"}}]})
        with self.assertRaises(MetaInferenceError):
            client.diagnose(**self.inputs())

    def test_missing_key_does_not_start_meta_client(self):
        with self.assertRaises(ValueError):
            MetaClient(api_key="", transport=lambda body: {})


if __name__ == "__main__":
    unittest.main()
