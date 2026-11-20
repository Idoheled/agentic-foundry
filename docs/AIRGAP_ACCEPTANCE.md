# Air-gap acceptance: evidence before enabling ordinary work

## Purpose

This procedure verifies the delivered installation on the receiving Linux host. It tests the complete path from a tracked task to a worker, an internal model, a real code change, verification and an accurate final state.

Run the tests in a dedicated smoke project and private installation state. Do not use production repositories, production cluster permissions, external messaging or hardware-management targets. Do not change the host's global firewall or DNS as a test; use the existing disconnected boundary or an isolated runtime/network with the operator's established controls.

For each test, record timestamp, version/configuration identity, task/run IDs, command or operation, expected result, observed result, sanitized evidence path and outcome. Outcomes are **pass**, **fail** or **not tested**. A skipped test is not a pass.

## Required test matrix

| ID | Test | Pass condition |
| --- | --- | --- |
| A01 | Payload integrity | Every required payload file matches the manifest/checksums. |
| A02 | Runtime compatibility | Selected images/binaries run on this architecture/libc/runtime without fetching components. |
| A03 | Offline start | Fresh application/worker start succeeds with external egress unavailable. |
| A04 | Local model route | The actual worker reaches only the configured internal inference route. |
| A05 | Model/tool round trip | Structured tool call, tool result and continuation succeed using the required protocol. |
| A06 | Authentication and secret hygiene | UI/API access behaves as configured; evidence contains no credential values. |
| A07 | Real task delivery | Paperclip dispatches a worker that edits the smoke repository and runs meaningful checks. |
| A08 | Independent review | A separate reviewer/verifier evaluates the actual diff and test outcome. |
| A09 | Multiple projects | Two isolated projects complete without writing into each other's workspaces. |
| A10 | Run visibility | Top-level run status matches the worker; child visibility limits are accurately reported. |
| A11 | Model outage | Failure/blocked state is visible, retries are bounded and no public fallback occurs. |
| A12 | Cancellation | Cancellation stops the actual run and owned child work, or a documented limitation blocks qualification. |
| A13 | Worker recovery | Worker interruption preserves evidence and leads to one deliberate recovery, not duplicate execution. |
| A14 | Control-plane restart | Tasks/history persist and active work is reconciled without uncontrolled redispatch. |
| A15 | Data restore | An isolated restore recovers the required state without automatically dispatching work. |
| A16 | Concurrency limits | Chosen global/project limits are observed and backlog remains visible. |
| A17 | OMP adapter qualification | If enabled, the pinned adapter completes its own real task and reports correctly. |
| A18 | Existing-tool preservation | Existing OMP/Claude Code and registered source repositories remain usable and unchanged by setup. |

A17 may be **not tested** only when OMP integration remains disabled and is explicitly excluded from the qualified scope. Optional Herdr tests are likewise separate from core qualification.

## A01–A03: payload and a genuinely offline launch

Run `./install.sh checksums` and verify the archive and source revisions. `preflight` checks host architecture/Python/space/configured port values; it is not a payload, daemon or end-to-end verification. Compare the actual manifest to every executable, container image, npm/native dependency and optional adapter required by the selected path. Do not assume a cached package on the receiving machine is part of the deliverable; record any dependency supplied by the user's environment.

Use a clean installation-state directory for the smoke instance. Launch from the delivered/imported artifacts with public egress unavailable. Observe application, adapter and child-process logs for lazy fetches. Watch for npm/npx/uv/pip downloads, Chromium/Playwright browser downloads, model metadata refreshes, public plugins, telemetry, update checks, remote assets and external authentication.

The pass criterion is successful required behavior without any required external dependency. Report blocked optional outbound attempts separately and disable them where supported. If a required payload is missing, name the exact artifact/version/platform and stop qualification of that path; a source repository is not a substitute for the missing offline runtime.

## A04–A05: prove the actual model path

Probe through the same environment, network namespace, certificate trust, authentication source and model configuration that the dispatched worker will use. A successful host-side `curl` is not enough if workers run elsewhere.

Run a harmless tool task: create a text file in the smoke workspace, read it back, compute a known checksum or deterministic result with the shell tool, and return that observed result. Capture evidence of both model/tool messages and the resulting file. The model must not merely describe what it would do.

Confirm `model.api` is the real endpoint protocol: `openai-completions`, `openai-responses` or `anthropic-messages`. Only Chat Completions with a synthetic mock was tested during assembly. Qualify whichever protocol is actually selected, including any configured `caCertPath`. Test streaming and continuation if the adapter uses them. Confirm the model ID reported by the service/harness. If the internal gateway cannot expose the actual downstream model, record that limitation.

Use internal gateway or runtime connection evidence where available to confirm routing. Do not log authorization headers or raw credentials. Assert that failure of the configured endpoint cannot select an external provider.

## A06: access and secret hygiene

Test the actual supported access mode from the intended client path. If authentication is enabled, verify an unauthenticated API request is refused and an authorized one succeeds. Localhost-only mode must remain bound to the intended local interface; it must not accidentally expose an unauthenticated service on the LAN.

Use a synthetic sentinel secret in a dedicated test configuration, not a real production credential, to check whether logs, errors, task prompts and generated reports leak configuration values. Remove the sentinel after the test. Also review actual evidence files for common secret labels without printing any matching values.

## A07–A08: meaningful code delivery

Create a tiny new repository owned by this test. Use a language and test runner already available in the payload/runtime so the test does not introduce a public package dependency.

Suggested task:

> Implement a small library function that accepts a list of integer values and returns distinct values in stable first-seen order. Preserve the input. Include tests for an empty list, repeated values, negative values and an already unique list. Run the tests and report the actual command and exit result.

Write deterministic acceptance checks independently of the implementer. The helper/reviewer should check the real diff and run the test command rather than relying on the implementation agent's summary. A deliberate incorrect implementation must fail at least one check; this prevents a vacuous smoke test that passes any output.

First let the smoke agent finish lifecycle verification. Preserve its current runtime configuration, temporarily set `runtimeConfig.heartbeat.wakeOnDemand:true` through `PATCH /api/agents/{id}`, and keep interval wakes disabled with `maxConcurrentRuns:1`. Create the task through the actual supported Paperclip API/UI path and let the configured adapter dispatch it. Restore `wakeOnDemand:false` after the bounded test, including if the test fails. Once acceptance evidence is complete, final admission may use `enable-agent --agent-id UUID --acceptance-report PATH`; this helper checks report existence, not evidence quality. Record its top-level task/run identity, worker process/container identity, model, diff and verification result. Confirm that a failing test produces a visible failure or unresolved state instead of an accepted completion.

## A09–A10: project isolation and visibility

Create a second smoke repository with different marker files and a separate task. Allow the configured concurrency limit to schedule work in both. Verify files only change in the assigned workspaces. A shared inference endpoint is expected; shared writable checkouts are not.

Compare Paperclip's status to the actual worker: idle/queued, running, completed, failed and cancelled states should have an observable mapping. Use the statuses actually supported by the pinned version.

If the harness can spawn subagents, run one bounded independent subtask. Determine whether the adapter exports distinct child IDs, tool events, logs and lifecycle. Record exactly what the UI exposes. Do not claim that every subagent is managed merely because the parent run is visible.

Registration itself may call the model through Paperclip lifecycle verification. Confirm lifecycle state `ready` and distinguish a failed hello probe from a running task; heartbeat settings do not suppress configuration probes.

## A11: model unavailability

For the smoke worker only, select a known unavailable internal test endpoint or use an isolated network rule. Do not stop the shared production model service.

Expected behavior: timeout/failure is visible, retry attempts are bounded, no task is accepted, and no request is redirected externally. Restore the known-good endpoint and demonstrate one intentional retry or new attempt. Preserve the failed attempt's evidence.

## A12: cancellation

Run a bounded smoke task with a clearly owned child process long enough to observe cancellation. Cancel using the product's actual supported interface. Verify that both the top-level worker and its owned child process stop within the configured termination window.

If cancellation only changes the database/UI while the process continues, the test fails. Record whether the adapter/runtime supports process-group or container termination. Do not solve this by killing unrelated processes or restarting a shared runtime.

## A13–A14: interruption and reconciliation

Interrupt only the smoke worker while a task has made a visible intermediate change. Restart the worker using the supported mechanism. Verify that the system either resumes a supported session or records a failed/interrupted attempt and schedules one deliberate replacement. Check the workspace before retries so existing edits are not overwritten or repeated blindly.

Then restart the smoke control-plane service while preserving its state. Confirm that task history and configuration remain intact, running work is reconciled, and no two workers own the same task/check-out after recovery. Check actual processes as well as UI records.

Do not require an implementation to pretend to resume an in-memory LLM turn if the harness cannot do so. A documented, bounded recovery from persisted task/workspace state can pass if the task is not duplicated and the final result is verified. Record the exact recovery semantics.

## A15–A16: existing protection and concurrency limits

The organization already supplies backup and recovery services. Reference that existing procedure where a native package/database change needs it; do not install a new backup platform or require a separate restore project as part of this delivery. The interrupted-task/session recovery checks above remain required.

Queue more smoke tasks than the configured active-run ceiling. Verify the active count never exceeds the enforced limit and pending tasks remain visible. Check that one project does not starve another indefinitely under the chosen scheduling policy. If the product does not provide a requested fairness policy, state where it is implemented or mark it unresolved.

## A17–A18: preserve the existing workflow

OMP integration is a separate qualification. Test the delivered downstream OMP `19.0.1-offline.1` and adapter `0.7.0-offline.1`, preserving their upstream source and patch provenance. Verify its executable/version, native module compatibility, adapter schema, local-provider config, cancellation, output parsing and one real task through Paperclip. Its standalone success is not proof of adapter success; successful native Pi integration is not proof of OMP support.

Verify the original OMP/Claude Code launch method still works. Compare registered source repositories to their pre-install metadata/status. The smoke checkout may change; registration alone must not alter the user's working repositories or their instruction files.

## Optional Herdr acceptance

Launch using only local artifacts. Open a dedicated smoke session, verify the intended harness and internal model, then close it and inspect process cleanup. Check persistence/reconnect behavior documented by the pinned version.

If a Paperclip-to-Herdr mapping is not implemented, label Herdr sessions as separate interactive work. Do not add a second scheduler or report automatic cross-product visibility.

## Final qualification report

State which tests passed, failed or were not tested. Include the installed revisions, runtime mode, enabled adapters, model protocols, workspace isolation mechanism, maximum tested concurrency and actual recovery semantics.

Use **qualified for the tested workflow** only if all required core tests pass. Otherwise use **installed with explicit blockers** or **installation incomplete**. Explain the smallest concrete action needed to resolve each blocker. Do not infer performance at higher concurrency, other Linux distributions, OpenShift or different models from this single-host result.
