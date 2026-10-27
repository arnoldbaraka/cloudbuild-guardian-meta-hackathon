# Three-minute judged demo — CloudBuild Guardian

**Important:** 2026 Meta hackathon submissions require a publicly accessible repository and a **three-minute demo** highlighting what was *created during this event*. Show the model name and distinguish scripted simulation from live Meta inference.

## Storyboard (3:00)

| Time | Visual / step | Voiceover |
| --- | --- | --- |
| 0:00–0:20 | UI hero → safety label | "Production outages are expensive. Most agents claim they can fix them. But can they prove what they did, and can we trust their boundaries? Meet CloudBuild Guardian." |
| 0:20–0:42 | Start synthetic checkout-api incident | "This is a synthetic Kubernetes incident. Two pods are running, but neither is ready. Four independent pieces of evidence explain why." |
| 0:42–1:12 | Click Analyze evidence; show Meta-enabled attribution when verified | "Guardian passes bounded evidence to Meta Muse Spark. The model proposes a diagnosis and cites observation IDs. It cannot execute commands; a separate deterministic policy validator checks every proposal." |
| 1:12–1:38 | Show the patch preview and explicit Approve / Reject buttons | "No remediation happens without human approval. An unexpected command, unverified evidence, or stale approval is rejected. Here the approved change affects only our isolated in-memory sandbox." |
| 1:38–2:01 | Approve sandbox patch, then Verify outcome | "We change the simulated readiness path from /ready to /healthz. Guardian then independently compares the expected postcondition: two of two simulated pods ready." |
| 2:01–2:22 | Open Evidence Ledger, show SHA256 chain and tamper test | "Every state transition has a hash-linked evidence record. Change an audit entry, and the integrity verification fails." |
| 2:22–2:42 | Switch to OOM/image pull fixture, demonstrate independent gate | "The same engine handles memory exhaustion and unpullable images, but only within three narrowly specified actions." |
| 2:42–3:00 | Architecture + repo + test run | "This is new hackathon code: Meta-model integration, a policy guard, human approval, verification and 25 passing tests. Our next milestone is a secure, separately tested read-only Kubernetes connector—not autonomous production patching." |

**Never claim an AI-powered investigation occurred when using the scripted demo mode.**
If live Meta inference is not available before recording, explicitly say the model connector was coded but not verified, and mark the corresponding stage as scripted or mocked. Do not present generated fixture results as real outages.

## Checklist for a valid entry

- [ ] Public GitHub repository opens in a private browser.
- [ ] Git history shows new changes from 27 October 2026 onward.
- [ ] Exact three-minute video file uploaded and accessible to judges.
- [ ] Working public or invite-accessible live demo under review; no production services or credentials exposed.
- [ ] Screenshot shows the Meta model and a real recorded API response (if enabled), with billing key/usage hidden.
- [ ] Model inference, independent policy validation, approval and postcondition proof shown distinctly.
- [ ] Only new functionality built during hackathon claimed.
- [ ] Submission text identifies real limitations; include all team members.
- [ ] Submit by November 4, 2026, 9:00 PM Eastern.

## Other demo clip ideas

- Trigger a forbidden model response in a mocked test and show it fail with HTTP 409.
- Reject a proposed patch and show evidence hash remains unchanged.
- Approve with an out-of-date revision and show stale approval denied.
- Edit an in-memory audit event during a test, then show hash chain verification fails.
