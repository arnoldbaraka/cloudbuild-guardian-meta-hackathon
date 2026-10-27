# CloudBuild Guardian

**A verifiable AI incident-response engineer — built for the 2026 Meta Global AI Developer Hackathon.**

![CI](https://img.shields.io/badge/tests-23%20passing-40dbc5)
![Scope](https://img.shields.io/badge/execution-synthetic%20sandbox%20only-8056e7)
![Model](https://img.shields.io/badge/model-Meta%20Muse%20Spark%201.3-168dde)
![License](https://img.shields.io/badge/license-MIT-94a2bc)

CloudBuild Guardian investigates synthetic Kubernetes incidents, gathers traceable evidence, requests explicit operator approval for a bounded remediation, and verifies the simulated outcome. A hash-chained event log makes later modification of audit entries detectable.

**This is a sandboxed proof of concept, not a production Kubernetes controller or a fully autonomous SRE agent.** It never connects to Kubernetes, shell, Docker or the production server. Nothing can trade, deploy or mutate CloudBuild infrastructure.

## What is new for this hackathon

This repository was created **27 October 2026** during the Meta hackathon's build period. The following components were written for this submission:

- A new deterministic incident-state engine with explicit approval and revision/freshness gates.
- Independent allowlisted action verification and evidence-ID checks; model output cannot run commands.
- New hash-chained audit event ledger with tampering detection.
- A Meta Muse Spark 1.3 Model API adapter with bounded inference calls.
- Three original synthetic incident fixtures and reproducible recovery checks.
- A responsive, accessible incident-investigation command center with Meta-vs-scripted attribution.
- HTTP API, non-loopback bind restrictions, and an offline unit/integration suite.

Our existing CloudBuild hosting platform, previous AIOps research, and production Kubernetes infrastructure are NOT claimed as newly created hackathon work. No pre-existing proprietary source code, credentials or operational customer logs are in this repository.

**Theme:** Push the Frontier. **Intended track:** Startup.
**Potential bonus award:** Best Agentic Use-Case.

## Run locally: free scripted mode

Only Python 3.10+ is needed (tested on Python 3.12); no pip installation or cloud API required.

    git clone https://github.com/arnoldbaraka/cloudbuild-guardian-meta-hackathon.git
    cd cloudbuild-guardian-meta-hackathon
    python3 -m guardian.server

Open http://127.0.0.1:8098. Default mode clearly displays **Scripted demo · no API spend**. Choose an incident and click Launch → Analyze evidence → Approve simulation → Verify outcome. Or reject and confirm the fixture stays unchanged.

Run automated tests:

    python3 -m unittest discover -s tests -v

## Enable real Meta Muse Spark inference

Meta documentation: https://dev.meta.ai/docs/protocols/chat-completions

- Endpoint: POST https://api.meta.ai/v1/chat/completions
- Model: muse-spark-1.3
- Authentication: bearer token from your Meta Model API dashboard, used **server-side only**.
- Mode: GUARDIAN_INFERENCE_MODE=meta
- Call cap: GUARDIAN_META_MAX_CALLS=12 by default, count reserved before each attempt, no automatic retries.

Example (run in a private shell, do not commit the key):

    export GUARDIAN_INFERENCE_MODE=meta
    export GUARDIAN_META_MAX_CALLS=8
    read -rs -p 'Meta Model API key: ' MODEL_API_KEY; echo
    export MODEL_API_KEY
    python3 -m guardian.server

Never type API keys in GitHub issues, screenshots, ChatGPT messages, deployment YAML, screenshots of terminal output or web-client code. For shared deployment use a proper secret manager. Meta credits are tied to billing; the process call cap limits the number of attempts **not spend in dollars**. Monitor the API dashboard.

**No-pretend AI guarantee:** if meta mode is enabled but the API is unavailable, Guardian returns an error and refuses to fall back silently to its canned scripted response. The UI identifies each analysis source.

## Key safety design

1. **No production connectivity.** No import of kubectl, subprocess, SSH clients or live K8s credentials in the application.
2. **No model-executed tools.** Muse Spark analyzes a finite evidence set, returns a JSON diagnosis and proposes one of three explicitly allowed action labels; an independent deterministic policy gate checks action and evidence IDs.
3. **Human approval required.** Approval is rejected when missing, false, not boolean, or based on an outdated incident revision.
4. **In-memory execution only.** Approved actions replace a synthetic fixture's data. No Kubernetes patch or external action occurs.
5. **Independent synthetic proof.** The expected post-remediation snapshot is compared by SHA-256; audit records are hash-chained to reveal accidental or intentional changes to in-memory events.
6. **Separate private credentials.** Web server listens on localhost by default and refuses non-loopback binding unless GUARDIAN_ACCESS_TOKEN has 24+ characters. For Internet deployment, additional authentication, TLS, CSRF/abuse controls, hardened proxying, persistence, isolated runtime and human security review are necessary.

## Demonstrated incident scenarios

| Synthetic failure | Grounded diagnosis | Allowlisted sandbox patch | Synthetic verification |
| --- | --- | --- | --- |
| checkout-api 0/2 Ready | /ready 404 vs /healthz 200 | correct_readiness_probe | 2/2 simulated pods Ready |
| image-worker OOMKilled | 128Mi limit under observed 188Mi need | set_memory_limit_256mi | 10/10 synthetic jobs complete |
| notification-service ImagePullBackOff | nonexistent container tag | restore_pinned_image | 1/1 synthetic deployment healthy |

The scenarios and results are invented for demonstration and should never be represented as actual customer outages or real Kubernetes repairs.

## Architecture

    Browser UI
      │  HTTPS/HTTP (same-origin JSON API)
      ▼
    Guardian Server (Python stdlib)
      ├── Incident Engine (bounded state machine)
      ├── Evidence & policy guard (deterministic allowlist)
      ├── Muse Spark Model API  ─────► Meta cloud (meta mode ONLY)
      ├── Human approval gate
      ├── Synthetic patch engine (in-memory, no shell)
      ├── SHA256 postcondition verification
      └── Chain-linked audit ledger (in-memory, non-durable)

## HTTP endpoints

| Method | Route | Behavior |
| --- | --- | --- |
| GET | /healthz | minimal health/mode |
| GET | /api/status | mode, scenario catalog and isolated scope |
| POST | /api/incidents | create a synthetic incident |
| POST | /api/investigate | scripted or Meta reasoning; gated proposal |
| POST | /api/approve | explicit boolean approval or rejection with revision |
| POST | /api/verify | independent synthetic postcondition check |
| POST | /api/ledger | integrity-check hash-linked events |
| GET | /api/incidents/{id} | read incident details |

## Judge demonstration and honest limitations

See [docs/DEMO.md](docs/DEMO.md) for the three-minute video script, shot list and exact scene workflow, and [docs/ORIGINALITY.md](docs/ORIGINALITY.md) for pre-existing/new-work separation.

- Present scripted runs as **scripted test fixtures**; show a separately authenticated live Meta-model run to demonstrate real inference once the model key is configured.
- The ledger is tamper-evident **in process** but not durable, signed, globally append-only or resistant to a malicious process owner. A server restart clears state.
- The synthetic result validator checks a known-good fixture postcondition, not a real deployment's health.
- The simple access-token gate is suitable for a protected local hackathon preview, not a multi-tenant public SaaS.
- Meta API availability/credits and real inference have **not been verified** without a configured key.

## Deployment safety

Docker image runs as a non-root user. Keep preview ports bound to loopback and tunnel through an authenticated administrative connection. **Do not connect to live Kubernetes in this hackathon MVP.**

    docker build -t cloudbuild-guardian:hackathon .
    docker run --rm --read-only --cap-drop=ALL --security-opt=no-new-privileges \
      -p 127.0.0.1:8098:8098 \
      -e GUARDIAN_BIND_HOST=0.0.0.0 \
      -e GUARDIAN_ACCESS_TOKEN="REPLACE_WITH_A_RANDOM_24_CHAR_OR_LONGER_TOKEN" \
      cloudbuild-guardian:hackathon

The above is a **synthetic-only preview**. For Meta inference, configure the API key securely outside the container image. Container environment variables can be visible to host/container administrators.

## Cost and licensing

Source is MIT licensed; no external runtime Python dependencies. Model calls may incur Meta charges, even with promotional credits. The exact dollar balance must be checked on Meta's Billing page.

Site: https://cloudbuild.co.ke · Project created for Meta Global AI Developer Hackathon 2026.
