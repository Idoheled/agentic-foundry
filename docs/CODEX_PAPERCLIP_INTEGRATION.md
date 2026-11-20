# Qualify optional native Codex and Claude workers in Paperclip

The core controller still seeds **OpenCode and OMP**. `install-all.sh` installs
selected tools and host profiles, and stages complete client trees; it does not
enroll Codex or Claude workers or configure their model routes. The receiving
internal agent is authorized to complete the requested optional worker integration
through Paperclip's supported API after testing the actual execution environment.
Keep company hiring/managed approval requirements intact.

This recipe follows Paperclip source commit
`c0f132898d2a2677312d8c72096187b27a3d9a38`, Codex **0.171.0**, and Claude Code
**2.1.329**. A different adequate internal version may be used after its native
configuration, argument and hook contracts are requalified. There is no bundled,
already-qualified bridge for an unknown internal model service.

## 1. Bind commands to the actual staged runtime

Finish the host/core installation and client staging described in
`STAGED_CLIENT_RUNTIMES.md`. Read the **actual core state's**
`reports/client-runtime.json`. These are the fields to use:

| Required value | Staging report field |
| --- | --- |
| Codex executable inside the worker container | `clients.codex.containerCommands.codex` |
| Claude executable inside the worker container | `clients.claude.containerCommands.claude` |
| Python for the native profile installer/hooks | `clients.python.containerCommands.python3` |
| Permanent native profile assets inside the container | `profilePlanHints.nativeProfilesRoot` |
| Complete source/staged tree identities | Each client's `sourceTreeSha256` and identity result |

Use the exact immutable paths from that report. A host `/usr/local/bin` entry
point does not identify the executable inside Paperclip. The staged native client
and Python paths point to complete trees, including their libraries/resources.
Staging is a copy/identity check; `containerExecutionQualified: false` is an honest
initial result, not a field to change manually.

Enter the intended container as the normal operator with
`./install.sh shell --state /ABSOLUTE/CORE-STATE`, or use the equivalent inspected
noninteractive execution interface for that same selected Docker socket/container.
Run version/help/import checks using the report's exact paths. Inspect the dynamic
library/runtime requirements there. Do not solve a missing library by mounting an
unrelated host root or changing the existing controller image without qualification.

The core mounts its `home` at `/paperclip`, its `runtime` read-only at
`/opt/agentic`, and selected projects at `/workspaces`. Mutable client configuration,
receipts and launch preparation belong under an explicitly selected operator-owned
location in `/paperclip`, not inside the immutable client trees. Preserve these
mount conventions when selecting the example paths.

## 2. Render the native profiles and routing

Read `NATIVE_OFFLINE_SETTINGS.md` before changing any route. Preserve the existing
working Claude/OMP gateway, model IDs, credential mechanism and CA trust. The
native profile installer merges skills/hooks; **it does not configure routing**.

For Codex, render and merge the two supplied templates:

- `payload/dependencies/codex/templates/internal-responses.config.toml.template`
  into the selected operator/agent `$CODEX_HOME/config.toml`;
- `payload/dependencies/codex/templates/internal-models.json.template` into a
  persistent catalog file visible in the actual execution environment.

Set the real Responses endpoint, exact internal model ID, actual context/tool
output limits and supported capabilities. Set `model_catalog_json` to the catalog's
**absolute container path**, for example a site-selected file under
`/paperclip/agentic-config/native/codex-catalogs/`. Do not put a host filesystem path,
an unexpanded environment-variable expression, or a temporary extraction path in
this setting. The provider configuration must be user-level; project configuration
does not carry these provider/authentication/telemetry routing keys in this version.

Codex requires a **Responses-compatible service**. A Chat Completions-only route
does not satisfy that requirement. Keep Codex's model integration blocked if this
protocol is unavailable, while completing independent host/Claude/OMP work.

For a credential-bearing internal provider used through Paperclip, the Codex
example binds the **real internal credential** through a Paperclip per-agent
`OPENAI_API_KEY` secret. Set the native custom provider's `env_key="OPENAI_API_KEY"`,
its explicit internal `base_url`, and `requires_openai_auth=false`. This environment
variable name does not choose the destination; the selected native provider does.
Paperclip's managed-home readiness check recognizes `OPENAI_API_KEY`/`auth.json`
and does not infer readiness from an arbitrary custom env-key name. Its private
managed auth file may therefore contain the actual internal key. Never substitute
a dummy credential to silence this check. A service that genuinely requires no
authentication needs a qualified adapter solution if this guard blocks it.

For Claude, use its existing qualified Anthropic Messages/gateway contract.
`ANTHROPIC_AUTH_TOKEN` sends Bearer authentication; `ANTHROPIC_API_KEY` uses the
API-key header. The example chooses the Bearer shape only as a template: use the
actual existing mechanism, and do not configure both by accident. Anthropic's
gateway documentation does not establish support for arbitrary non-Claude models.

## 3. Use the native CLI adapter fields explicitly

Render `config/native-codex-agent.example.json` or
`config/native-claude-agent.example.json` into a separate private site file. Replace
every `REPLACE_WITH...` value, including the executable command from the staging
report and the real secret UUID. Placeholder secret IDs are deliberately unusable.
The files contain no credentials and cause no enrollment by themselves.

Both examples set request-level `runner: "legacy"` and
`adapterConfig.engine: "cli"`. These are separate choices. The current adapter
engine defaults to ACP; an automatic runner request can select Paperclip Runner.
This recipe qualifies the native CLI lane represented by the installed packages.

| Client | Explicit unattended policy in the example |
| --- | --- |
| Codex | `dangerouslyBypassApprovalsAndSandbox: false`; `approval_policy="never"`; `--sandbox workspace-write` |
| Claude | `dangerouslySkipPermissions: false`; `--permission-mode acceptEdits`; `--permission-prompts none` |

These false values are necessary. Paperclip's pinned executable policy defaults
Codex's bypass flag to true, despite a conflicting prose paragraph, and Claude's
adapter defaults permission skipping to true. The examples select the intended
policy explicitly. Codex's pinned help does not list the older `--full-auto` flag.

Claude's `acceptEdits` mode handles ordinary permitted editing; with permission
prompts set to `none`, an operation that still requires approval is denied rather
than left waiting for an absent human. Inspect the task and existing native policy,
then qualify the required scoped shell/test permissions before admitting production
work. This example does not claim that all tools are already allowed. Preserve a
managed policy's decision and report a concrete block when it prevents the task.

The Codex example permits sandboxed tool networking so the worker can reach its
internal Paperclip API and approved repositories. Keep actual network controls in
force. If selecting Paperclip's optional network allowlist, include the real model,
Paperclip and private-repository origins and test its additional namespace/proxy
requirements. Do not disable the sandbox to hide a runtime or kernel failure.

The adapters supply their own print/JSON arguments, prompt transport and resume
arguments. Do not duplicate `exec --json` or `--print --output-format stream-json`
inside `extraArgs`. Keep an explicit internal model selection; omitted models can
resolve to an upstream public model default.

## 4. Qualify the effective profile, including generated Codex homes

A configured Codex home is not always the launched home. Normal Paperclip heartbeat
preparation supplies a runtime skill inventory. The Codex adapter hashes that
inventory and can create a new managed skill-runtime home even when an external
home was configured. This preserves its selected skill inventory and session state.

Its current copied files are `config.json`, `config.toml`, `instructions.md` and
`auth.json`; remote synchronization additionally includes `skills`. **`hooks.json`
and `models.json` are not on those allowlists.** An installed hook in the original
profile therefore does not prove worker activation. A persistent absolute catalog
path solves the local catalog-location issue only when that path is visible and
readable in the actual worker environment.

Complete this procedure as the worker's ordinary operator:

1. Observe the effective `CODEX_HOME` from an actual adapter probe/invocation
   record without dumping credentials or the full environment. Check its owner,
   filesystem type, configured scope and actual model configuration. Do not select
   a home merely by finding the newest directory.
2. Read the staged native profile project's `plan.example.json` and create a
   **Codex-only** plan. Set `assetRoot` and `python` from the staging report, compute
   the actual Python/Codex binary hashes, and review the installed asset manifest.
   Set `clients.codex.home` to this effective home and `clients.codex.skillsDir` to
   the operator's actual native user-skill root. In this container the normal HOME
   is `/paperclip`, so inspect `/paperclip/.agents/skills` instead of assuming that
   changing CODEX_HOME also changes the user-skill root. Use private audit/receipt
   directories and preserve unrelated skills/hooks.
3. Select `activateReviewedHooks: true` only after that exact review, and set the
   required reviewed manifest hash and Codex executable/hash. With
   `PYTHONDONTWRITEBYTECODE=1`, run the staged Python and staged
   `install_profiles.py --plan /ABSOLUTE/PRIVATE-PLAN.json --check`, then `--apply`.
   The supported helper must report all four exact kit hooks trusted. Keep blocked
   managed definitions blocked; do not write trust hashes manually.
4. Start a fresh actual Codex turn with the intended internal provider. Verify a
   benign file/tool action, skill discovery, hook context and the expected private
   event records. Exercise resume, cancellation and a representative task before
   recording that worker as operational.
5. Repeat the effective-home check after a skill assignment or profile change;
   those changes can produce a new managed home.

To automate step 2/3 for generated homes, the receiving agent may implement and
qualify a narrow launch preparer under its own versioned local integration project.
It must preserve the **provided** CODEX_HOME, validate that it is the expected
operator-owned profile, verify the approved staged binaries/assets, serialize
updates to the same home, apply only the namespaced native profile, record the
actual trust result, then exec the exact staged Codex command with the original
arguments/environment. Version/help probes should avoid unnecessary profile
mutation. Test first launch, a repeated launch, a newly generated home, an unrelated
existing hook, a policy rejection and rollback. Change `adapterConfig.command` to
that preparer only after those tests. The kit does not ship or claim an already
qualified dynamic-home bridge. **Never reset CODEX_HOME to the initial profile**
in such a wrapper; that defeats Paperclip's skill selection and state isolation.

For Claude, inspect the effective `CLAUDE_CONFIG_DIR` too. Local explicit profiles
can use the native installer directly. The current remote managed seed sanitizes
settings and removes hooks; install and qualify the native profile in the actual
execution destination instead of assuming the host profile was copied. Additional
filesystem confinement can also change the selected configuration directory.

For remote execution, explicitly provide the catalog, hook handler, native profile
assets and their full runtime dependencies at destination-local paths. A local
absolute path or a host trust result does not qualify a remote host.

## 5. Test, register and admit optional workers

The user has authorized the internal receiving agent to complete this setup.
Perform the concrete checks and use existing supported API/approval flows; there
is no need to ask again merely because these workers are optional in the default
controller seed.

First run the actual native client against its internal service in the intended
container/service identity, including a benign tool operation and native hooks.
Use Paperclip's supported environment test route:

`POST /api/companies/<companyId>/adapters/<codex_local-or-claude_local>/test-environment`

The body contains `runner: "legacy"` and the rendered `adapterConfig`; include the
actual `environmentId` when the agent runs in a non-local Paperclip environment.
Use the existing authenticated API client and secret bindings. Keep real keys out
of command arguments, example JSON and logs. This route may make a real model call.
An environment/hello result alone is narrower than the task/hook/recovery checks.

After the actual client test passes, register the optional worker through
`POST /api/companies/<companyId>/agents` using the rendered example. The examples
disable periodic/task-triggered wakes and limit the initial worker to one run.
Paperclip may still perform its lifecycle/hello probes; disabled wakes do not mean
that registration is free of model calls. Preserve an existing company's hiring
approval workflow. Inspect an existing matching worker before updating it; avoid
duplicate enrollment or changing another agent's route.

Run the actual Paperclip worker canary and inspect its effective profile, tools,
hooks, accounting, cancellation and resume. Finish `AIRGAP_ACCEPTANCE.md`, record
the evidence and admitted concurrency, and only then enable the intended wakes
through the supported agent API/controller admission flow. The ordinary controller
`seed` command remains scoped to OpenCode/OMP; adding these example files does not
extend that command's worker enum or auto-enroll native workers.

## Evidence and limits

The builder verified native Codex CLI/helper startup, source dependency resolution,
hook output schemas and actual hook catalog/trust API behavior. Its full Codex
turn stopped before any model request because bwrap's NETLINK_ROUTE operation was
denied by the builder environment. Claude/OMP native loopback probes verified
skills and lifecycle hook execution, but cannot qualify an unknown internal
service. The receiving host's observed results determine completion.

Offline source evidence is in the shipped Paperclip snapshot at the commit above:
`packages/adapters/codex-local/src/{index.ts,server/acp.ts,server/codex-args.ts,server/execute.ts,server/codex-home.ts}`,
`packages/adapters/claude-local/src/{index.ts,server/execute.ts,server/permissions.ts,server/claude-config.ts}`,
`packages/shared/src/validators/{agent.ts,secret.ts}`, and
`server/src/services/{heartbeat/execution-configuration.ts,connector-runtime.ts}`.
Native documentation and CLI help are included in the Codex and native-profile
payloads; the receiving agent does not need public web access to read these contracts.
