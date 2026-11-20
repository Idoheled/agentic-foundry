# Operating Agentic Foundry

Use Paperclip to coordinate work, Git to preserve code changes, and the selected harness to execute each task. Keep the site's existing internal model, identity, artifact, monitoring, and backup services under their established ownership.

## Establish the installation record

Maintain a private record of the actual deployment. Reference credential sources without recording their values.

| Record | Required detail |
| --- | --- |
| Release | Repository tag, payload revision, archive/manifest identities, verification results. |
| Host | OS, architecture, libc, selected native profile, installation account. |
| Sources | Inspected private repositories, selected artifacts, qualification evidence, fallback reasons. |
| Commands | Installed or reused versions, package ownership, runtime paths, resolved entry points. |
| Preserved configuration | Original baseline, effective profile locations, reviewed additions and migrations. |
| Core runtime | Paperclip/adapter identities, Docker selection, state and workspace locations. |
| Models | Actual protocol, internal route, model IDs, credential-source reference, limits. |
| Projects | Repository identity, task worktree root, build/test commands, acceptance criteria. |
| Acceptance | Actual native, worker, model/tool/session, browser, and project results. |
| Changes | Promoted and retired paths, retained originals, applicable recovery procedure. |

Keep site files, state, logs, acceptance evidence, and runtime credentials outside the source repository. The installation record is not an invitation to collect unrelated private configuration.

## Daily delivery workflow

1. Review running, blocked, failed, and waiting-for-input work before adding more tasks.
2. Define a concrete result, allowed scope, repository, and acceptance criteria.
3. Split independent work into explicit tasks. Give each edit-producing task one owner and its own worktree.
4. Require the implementer to return a diff or commit, checks run, observed results, and remaining limitations.
5. Review substantive changes in a separate context. Use deterministic tests and CI wherever they can establish the result directly.
6. Accept work when the artifact satisfies the criteria. Retain unresolved findings as explicit follow-up tasks.

Start with bounded concurrency and reserve capacity for interactive use. Increase parallel runs only while accepted delivery improves. More agents can compete for inference capacity, disk, shared files, and reviewer attention.

Paperclip owns managed task worktrees. Use Worktrunk for interactive work and explicitly assigned worktrees without letting both systems independently clean or rename the same checkout. Herdr sessions should remain distinguishable from Paperclip-dispatched tasks.

## Use the delivery tools deliberately

| Tool group | Routine use |
| --- | --- |
| Zoekt/Ctags | Index the approved repositories and use content/symbol search before broad repeated file scans. Keep indexes in writable private state, not immutable runtime trees. |
| Language services | Use supported per-client integration for definitions, references, diagnostics, and code understanding. Preserve the tested server/runtime group. |
| RTK OSS | Compact selected command output while preserving exit status. Existing hooks are not replaced with a blanket rewrite. |
| Inspect AI / native benchmark | Compare one major configuration change at a time on the same tasks with independent acceptance checks. |
| Playwright / Chromium | Run the real UI test and project-specific browser assertions in the qualified host or worker environment. |
| Trivy | Use the included dated database or a qualified newer private database. Keep private update procedures responsible for refreshing it. |

Measure accepted changes, elapsed delivery time, and correction effort when comparing configurations. A lower token count or a larger number of running agents is not sufficient evidence of better results.

## Core lifecycle

Run commands from the complete installation root and consistently select the site's actual state and Docker socket when those differ from defaults. Inspect `./install.sh --help` for supported options.

```bash
./install.sh status
./install.sh verify
./install.sh start
./install.sh stop
```

The default core state is `$HOME/.local/share/agentic-stack`. Managed workspaces appear at `/workspaces` in the controller container, and the managed runtime is mounted read-only at `/opt/agentic`. A separate static Docker daemon, when selected, has its own socket; routine lifecycle commands must not accidentally target another daemon.

A deliberate core configuration change uses the actual completed private core configuration:

```bash
./install.sh configure --config /private/core-site.json
./install.sh start
./install.sh model-smoke
```

A successful model text smoke is tied to that configuration. It does not establish real tool calling or task acceptance. Registration may itself trigger a client lifecycle probe even while task-triggered wakes are disabled.

## Admit a worker after real acceptance

Keep a newly registered worker inactive for ordinary task dispatch until its selected configuration passes the relevant tests. Complete [Air-gap acceptance](AIRGAP_ACCEPTANCE.md), the native client/profile checks, and selected browser/worker checks.

After reviewing the actual evidence:

```bash
./install.sh enable-agent \
  --agent-id UUID \
  --acceptance-report /private/reports/accepted-worker.json
```

The admission command checks that the report exists; the receiving agent/operator must judge its evidence. It does not independently prove the report's claims. Use only real agent IDs and the site's actual report path.

Set concurrency through supported interfaces and record where each limit is enforced. Per-agent limits are not a global capacity ceiling. Avoid nested retry loops across the task coordinator, harness, adapter, and model gateway.

## Maintain native tools and private sources

Keep suitable installed tools, prefer approved internal supply, and record the factual reason for a bundled fallback. The selected artifact plan and locally staged files must remain accessible for operations that consume them. A new upstream version requires an explicitly qualified recipe; do not weaken digest checks to admit an untested substitution.

Update package-owned executables and libraries through the native package manager. Stage complete standalone runtimes under their managed versioned paths. Verify the actual shell, service, and worker environments before promoting command entry points. A binary inside a container does not make it a native host command, and a native host command does not prove worker availability.

Use [Final cleanup](FINAL_CLEANUP.md) for exact obsolete unmanaged paths after their replacement and consumers pass. Preserve unrelated files, shared runtimes, package ownership, and the original profile baseline.

## Resume a failed setup

Read the structured blocker and its private stage log. Resolve the actual issue, then rerun the same setup command with unchanged inputs and the same setup state. Completed stages are verified before reuse.

If the site configuration, selected catalog, artifact, or review input changes, start a new reviewed setup transaction while retaining the original profile-preservation baseline. Do not delete state, reset a baseline, or exclude a failing profile path merely to obtain a passing result.

`productivity_completed` covers the requested productivity scope. `requested_setup_steps_completed` covers the selected installation stages. Real model/project acceptance and worker activation remain separate recorded gates.

## Troubleshooting

| Observation | Inspect first | Resolution principle |
| --- | --- | --- |
| LFS pointer text appears where an archive is expected | Payload retrieval and verification in [Offline payloads](PAYLOADS.md). | Retrieve the actual locked objects before disconnected deployment. |
| Setup reports an unsupported target | OS, architecture, libc, selected catalog/native profile. | Supply a matching qualified private profile; do not force Debian 13 binaries or packages onto another target. |
| Input identity changed | Original site JSON, compiled plans, catalogs, reviewed specifications. | Review the change and create a new transaction using the original preservation baseline. |
| Private artifact has unexpected bytes | Repository finding, artifact digest, qualification recipe. | Inspect and qualify the candidate rather than treating it as automatically absent. |
| UI opens but tasks do not execute | Worker admission, adapter, executable path, permissions, model route. | Repair the actual execution path and rerun a bounded task. |
| Text generation works but tool calls fail | Endpoint protocol, model support, streaming and tool-result continuation. | Verify a minimal real tool round trip before coding tasks. |
| Authentication or TLS fails | Credential visibility to the actual worker, internal CA, endpoint scheme, clock. | Repair the selected trust/authentication path without disabling TLS verification. |
| Tool works in a shell but fails in a worker | Worker runtime tree, PATH, libraries, ownership, trust, staged receipt. | Verify the exact worker context rather than substituting a host-only check. |
| Client attempts an unexpected public download | Launch command, lazy dependencies, plugins, model metadata, update controls. | Supply missing qualified dependencies through private sources and repeat disconnected acceptance. |
| Browser version works but UI test fails | Actual browser path, sandbox prerequisites, selected native/worker environment. | Keep capability acceptance blocked until the real interaction test passes. |
| Existing command conflicts with a new entry point | Package ownership, target, consumers, required features. | Reuse an adequate command or perform an inspected, verified replacement. |
| Task remains running or edits repeat | Process ownership, active child processes, retries, worktree reuse. | Reconcile the existing action before redispatching it. |
| A spawned child is absent from the dashboard | Harness event export and adapter support. | Record the visibility limit; do not invent child-run records. |

A partially completed mutation must be reconciled before retrying. Check whether a commit, task update, promotion, or service change already happened.

## Updating the workspace

Prepare a pinned next release using the existing private supply and connected-side release process. Preserve upstream licenses, patches, and artifact identities. Test the supported target and compare real delivery before adopting changed models, skills, clients, or adapters.

Existing-machine OMP changes stay in the Claude phase-1 workflow. Phase 2 must preserve the exact qualified OMP runtime and launch context. Other component updates still require compatibility and preservation checks; an application update does not automatically justify replacing a working host tool.

Use the organization's existing recovery, monitoring, and backup arrangements. Agentic Foundry retains configuration originals and transaction recovery required for its upgrades; it does not install or requalify a replacement platform for those services.

## Durable project knowledge

Keep verified project knowledge in versioned project documentation: architecture decisions, conventions, build/test commands, integration contracts, and lessons with a defined scope. Keep task state in Paperclip and working session state in the harness's supported persistent storage.

Evaluate proposed changes to baseline prompts, permissions, skills, or evaluation tasks in a separate candidate profile. Promote them only after observed improvement and preservation checks. Routine coding tasks do not authorize unrelated infrastructure changes, production deployment, or external communication.
