"""Zero-dependency local Guardian web service. Not production-ready.

No Kubernetes client, shell execution, SSH agent or production credential access.
"""
from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .core import Guardian, GuardianError
from .meta import MetaClient

STATIC_DIR = Path(__file__).with_name("static")
MAX_BODY = 12 * 1024
MAX_ID_LENGTH = 64


def new_guardian() -> Guardian:
    mode = os.environ.get("GUARDIAN_INFERENCE_MODE", "demo")
    if mode == "meta":
        client = MetaClient(max_calls=int(os.environ.get("GUARDIAN_META_MAX_CALLS", "12")))
        return Guardian(mode="meta", model_client=client)
    if mode != "demo":
        raise ValueError("GUARDIAN_INFERENCE_MODE must be demo or meta")
    return Guardian(mode="demo")


def handler_factory(guardian: Guardian, access_token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CloudBuildGuardian/0.1"
        sys_version = ""

        def log_message(self, format, *args):
            # Never log request headers, input or query strings.
            return

        def respond(self, status: int, body: dict):
            payload = json.dumps(body, separators=(",", ":"), ensure_ascii=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(payload)

        def authorized(self) -> bool:
            if not access_token:
                return True
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return False
            return hmac.compare_digest(auth[7:], access_token)

        def need_auth(self) -> bool:
            if not self.authorized():
                self.respond(401, {"error": "Access token required"})
                return False
            return True

        def parse_json(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise GuardianError("Invalid content length")
            if length <= 0 or length > MAX_BODY:
                raise GuardianError("Body must be nonempty and <=12KiB", 413)
            if "application/json" not in self.headers.get("Content-Type", ""):
                raise GuardianError("Use application/json", 415)
            try:
                value = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise GuardianError("Malformed JSON")
            if not isinstance(value, dict):
                raise GuardianError("Expected a JSON object")
            return value

        def get_id(self, prefix: str) -> str:
            path = urlsplit(self.path).path
            value = path[len(prefix):]
            if not value or "/" in value or len(value) > MAX_ID_LENGTH:
                raise GuardianError("Invalid incident identifier", 404)
            return value

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/healthz":
                return self.respond(200, {"status": "ok", "mode": guardian.mode})
            if path.startswith("/api/"):
                if not self.need_auth():
                    return
                try:
                    if path == "/api/status":
                        return self.respond(200, guardian.overview())
                    if path.startswith("/api/incidents/"):
                        incident = self.get_id("/api/incidents/")
                        return self.respond(200, guardian.get(incident))
                    return self.respond(404, {"error": "Unknown API route"})
                except GuardianError as e:
                    return self.respond(e.status, {"error": str(e)})
            assets = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "application/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            if path not in assets:
                return self.respond(404, {"error": "Not found"})
            filename, mime = assets[path]
            content = (STATIC_DIR / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'self'; style-src 'self'; "
                             "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
                             "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            path = urlsplit(self.path).path
            if not self.need_auth():
                return
            if path not in {"/api/incidents", "/api/investigate", "/api/approve",
                            "/api/verify", "/api/ledger"}:
                return self.respond(404, {"error": "Unknown API route"})
            try:
                data = self.parse_json()
                if path == "/api/incidents":
                    scenario = data.get("scenario")
                    if not isinstance(scenario, str):
                        raise GuardianError("scenario must be a string")
                    result = guardian.create(scenario)
                else:
                    incident_id = data.get("id")
                    if not isinstance(incident_id, str):
                        raise GuardianError("id must be a string")
                    if path == "/api/investigate":
                        result = guardian.investigate(incident_id)
                    elif path == "/api/approve":
                        result = guardian.approve_and_apply(
                            incident_id, data.get("revision"), data.get("approved"))
                    elif path == "/api/verify":
                        result = guardian.verify(incident_id)
                    else:
                        result = {"ledger_intact": guardian.check_ledger(incident_id),
                                  "id": incident_id}
                self.respond(200, result)
            except GuardianError as exc:
                self.respond(exc.status, {"error": str(exc)})

    return Handler


def serve():
    host = os.environ.get("GUARDIAN_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("GUARDIAN_PORT", "8098"))
    token = os.environ.get("GUARDIAN_ACCESS_TOKEN", "")
    if host not in {"127.0.0.1", "::1", "localhost"} and len(token) < 24:
        raise RuntimeError("Refusing non-loopback bind without GUARDIAN_ACCESS_TOKEN (24+ chars)")
    guardian = new_guardian()
    server = ThreadingHTTPServer((host, port), handler_factory(guardian, token))
    print(f"CloudBuild Guardian [{guardian.mode}] serving on http://{host}:{port}", flush=True)
    print("SANDBOX ONLY — NO LIVE KUBERNETES ACCESS", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
