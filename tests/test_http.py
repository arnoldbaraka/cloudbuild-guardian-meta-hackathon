"""HTTP API boundary and auth smoke tests using only localhost, no credentials."""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from guardian.core import Guardian
from guardian.server import handler_factory, serve


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = Guardian()
        cls.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            handler_factory(cls.g, "a-test-token-with-24-characters-minimum"))
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)

    def fetch(self, method, path, data=None, authorized=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer a-test-token-with-24-characters-minimum"
        conn.request(method, path,
                     body=json.dumps(data) if data is not None else None, headers=headers)
        response = conn.getresponse()
        result = json.loads(response.read().decode())
        code = response.status
        conn.close()
        return code, result

    def test_requires_access_token_on_api(self):
        code, result = self.fetch("GET", "/api/status", authorized=False)
        self.assertEqual(code, 401)

    def test_healthz_reports_mode_without_exposing_secrets(self):
        code, result = self.fetch("GET", "/healthz", authorized=False)
        self.assertEqual(code, 200)
        self.assertEqual(result, {"status": "ok", "mode": "demo"})

    def test_create_investigate_approve_verify_http(self):
        code, start = self.fetch("POST", "/api/incidents", {"scenario": "readiness"})
        self.assertEqual(code, 200)
        code, analyzed = self.fetch("POST", "/api/investigate", {"id": start["id"]})
        self.assertEqual(code, 200)
        self.assertEqual(analyzed["stage"], "awaiting_approval")
        code, forbidden = self.fetch("POST", "/api/verify", {"id": start["id"]})
        self.assertEqual(code, 409)
        code, patched = self.fetch("POST", "/api/approve", {
            "id": start["id"], "revision": analyzed["revision"], "approved": True})
        self.assertEqual(code, 200)
        code, verified = self.fetch("POST", "/api/verify", {"id": start["id"]})
        self.assertEqual(code, 200)
        self.assertTrue(verified["validation"]["passed"])
        code, ledger = self.fetch("POST", "/api/ledger", {"id": start["id"]})
        self.assertTrue(ledger["ledger_intact"])

    def test_rejects_invalid_scenario(self):
        code, result = self.fetch("POST", "/api/incidents", {"scenario": "prod"})
        self.assertEqual(code, 400)

    def test_remote_bind_requires_random_access_token(self):
        with patch.dict("os.environ", {
            "GUARDIAN_BIND_HOST": "0.0.0.0",
            "GUARDIAN_ACCESS_TOKEN": "",
        }):
            with self.assertRaisesRegex(RuntimeError, "Refusing non-loopback"):
                serve()

    def test_billable_meta_mode_requires_auth_even_on_loopback(self):
        with patch.dict("os.environ", {
            "GUARDIAN_INFERENCE_MODE": "meta",
            "GUARDIAN_BIND_HOST": "127.0.0.1",
            "GUARDIAN_ACCESS_TOKEN": "",
        }):
            with self.assertRaisesRegex(RuntimeError, "Meta billable mode"):
                serve()


if __name__ == "__main__":
    unittest.main()
