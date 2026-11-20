# Apply and preserve native offline settings

Installing a binary or a native skills/hooks profile does not select its model
route. Complete routing and trust configuration in the actual host, service or
container profile before claiming the client works. Preserve the user's existing
working Claude Code/OMP connections; inspect and merge the minimum changes needed
for this disconnected deployment. Use the approved internal credential mechanism.

The native profile installer preserves routing, credentials, unrelated settings
and permissions. It does not automatically apply the Codex provider template, the
Claude offline environment fragment, an internal CA bundle or package indexes.
Those are explicit receiving-agent responsibilities. The host catalog adds selected
fixed launcher environment values for tools such as Claude, OpenCode and Python;
it does not invent a Codex model route.

## Before changing a profile

Identify the ordinary operator, service identity, executable and effective native
profile. Record current file hashes/permissions and a recoverable backup without
printing secrets. Check managed settings and project-local overrides. A service
does not inherit a login shell's environment, and a staged container executable
does not automatically receive the environment set by a host launcher.

Use host receipt commands for host work. For staged clients inside Paperclip,
read `reports/client-runtime.json` and use its exact `containerCommands` and
`profilePlanHints`. Keep immutable runtime trees intact and put mutable profiles,
secrets and receipts in their intended operator-owned state directories.

Merge configuration structurally, preserve unrelated keys and reject duplicate
TOML tables or conflicting JSON entries. Validate syntax and the selected native
schema, review the effective diff, run the client with the actual internal endpoint,
then record the changed paths and rollback. Do not replace a working configuration
with an example or treat an offline switch as evidence of network isolation.

## Codex 0.171.0

The complete native provider/catalog templates are in
`payload/dependencies/codex/templates/`; native schemas and the full official
manual are in that module's `schemas/` and `docs/`. Render and merge into the
selected user-level `$CODEX_HOME/config.toml`, normally `~/.codex/config.toml`.

The routing fields have to describe the actual internal service:

```toml
model = "REPLACE_WITH_ACTUAL_INTERNAL_MODEL_ID"
model_provider = "internal"
model_catalog_json = "/REPLACE_WITH_PERSISTENT_ABSOLUTE_MODEL_CATALOG.json"

[model_providers.internal]
name = "Internal Responses endpoint"
base_url = "https://REPLACE_WITH_APPROVED_RESPONSES_ENDPOINT/v1"
env_key = "REPLACE_WITH_EXISTING_CREDENTIAL_ENV_NAME"
requires_openai_auth = false
wire_api = "responses"
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0

[model_providers.internal.capabilities]
external_web_access = false
remote_compaction = "unsupported"
```

The example `internal` key may be replaced by an existing qualified provider name;
keep `model_provider` consistent. Inspect the service's expected base path rather
than blindly appending another `/v1`. The service must implement Responses; a
Chat Completions-only endpoint is insufficient. Preserve a proven gateway's extra
headers, query parameters, authentication and capability settings where required.
Use credentials through environment/secret references, not literal TOML values.
For the Paperclip legacy CLI lane, read `CODEX_PAPERCLIP_INTEGRATION.md`: its managed
credential gate expects the real internal credential under `OPENAI_API_KEY`, and
the corresponding native provider should name that same env key.

The following selected offline fields are also present in the supplied template.
Place root keys before table headers and merge existing tables rather than
appending a second copy:

```toml
check_for_update_on_startup = false
web_search = "disabled"

[analytics]
enabled = false

[feedback]
enabled = false

[otel]
exporter = "none"
trace_exporter = "none"
metrics_exporter = "none"

[features]
apps = false
remote_models = false
api_key_model_discovery = false
remote_plugin = false
plugin_discovery_prefetch = false
recommended_plugins = false
realtime_conversation = false
```

The static catalog's slug must equal the actual model ID. Fill the actual context
window, tool-output limit and supported modality/reasoning/tool capabilities;
placeholder strings are intentionally not a usable catalog. Preserve a legitimate
existing catalog entry if it accurately describes the selected service. Do not
advertise untested OpenAI-model capabilities for an internal model.

Permissions are a separate choice. The supplied profile example uses a workspace
write sandbox with `approval_policy="never"` for unattended work; operations needing
unavailable approval fail. A managed human checkpoint remains authoritative. Merge
these fields only for the selected authorized worker/profile, and test the actual
sandbox on the receiving host. `--strict-config` helps detect unsupported fields
for the pinned client; version/help success is not a model or tool-call pass.

For TLS, the pinned Codex HTTP client supports the scoped
`CODEX_CA_CERTIFICATE=/absolute/approved-bundle.pem`, with `SSL_CERT_FILE` as its
fallback. Use the native-specific variable when only Codex needs the additional
trust. Check file readability in the effective worker namespace. Keep existing
approved proxy settings and TLS verification enabled.

Paperclip can generate another CODEX_HOME after skill selection. A catalog should
therefore use a persistent absolute execution-environment path. Its current home
copy/sync allowlist omits `hooks.json` and `models.json`; complete the effective-home
profile procedure in `CODEX_PAPERCLIP_INTEGRATION.md` instead of resetting the home
or assuming initial-profile hook trust transfers automatically.

## Claude Code 2.1.329

The installed native profile asset root contains `claude/offline-env.json`:

```json
{
  "DISABLE_AUTOUPDATER": "1",
  "DISABLE_TELEMETRY": "1",
  "DISABLE_ERROR_REPORTING": "1",
  "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
}
```

Apply the fragment to the selected Claude launch environment after inspecting the
existing route. Hostctl's Claude launcher carries these selected catalog values.
When calling a raw staged client path inside Paperclip, supply the same intended
fragment in that worker's environment; the example native Claude agent does so.
Do not export these values globally for unrelated applications.

Preserve the existing `CLAUDE_CONFIG_DIR`, gateway URL, actual model IDs and credential
provider. `ANTHROPIC_BASE_URL` selects the compatible gateway;
`ANTHROPIC_AUTH_TOKEN` produces Bearer authentication, while `ANTHROPIC_API_KEY`
uses the API-key header. Preserve an established OAuth/key helper or other supported
mechanism when that is the working route. Never copy real credentials into examples,
source control, command arguments or broad runtime logs.

Use the existing qualified Anthropic Messages/gateway behavior. The official
documentation does not establish support for arbitrary non-Claude backends, and
these offline switches do not add a translator. Model and tool-call acceptance
must use the actual service.

Claude's settings/hook profile is merged separately. Keep unrelated local,
synchronized and managed skills/plugins intact. Do not disable `syncClaudeAiSkills`
as an offline shortcut: the captured documentation describes moving synchronized
skills to trash when that setting is disabled. Inspect optional plugins and their
dependencies individually, and enable only locally available, approved capabilities.

For unattended Paperclip workers, explicitly set `dangerouslySkipPermissions:false`.
The example selects `acceptEdits` and `--permission-prompts none`; an operation
that still requires approval is denied. Qualify the necessary scoped test/shell
permissions against the task and managed policy. Remote managed profile seeding
currently strips hooks, so verify the actual destination profile before claiming
native hook activation.

## OMP 19.0.1 offline package

Preserve the actual active OMP profile, including named profiles. Its normal agent
directory is `~/.omp/agent`; `PI_CODING_AGENT_DIR` overrides the default profile,
and a named profile uses its own directory. Confirm which profile a command uses
before installing skills/hooks or changing model files.

Use the kit's selected **wrapper**, not its adjacent `omp-real` executable. The
host wrapper carries `PI_NATIVE_VARIANT=baseline`, `OMP_OFFLINE_CATALOG=1` and the
`--offline` argument while preserving the existing host profile/native defaults.
The core container wrapper has container-specific defaults for
`PI_CODING_AGENT_DIR=/paperclip/agentic-config/omp` and
`PI_NATIVES_DIR=/paperclip/agentic-config/omp-natives`. Use each in its qualified
context; do not globally point a host `omp` entry at the container wrapper.

The controller's managed OMP profile is generated from the site's actual model
configuration. It selects that provider's protocol/base URL/model roles, disables
model fallback chains, update/setup-wizard traffic, marketplace updates and OTel
export, and supplies the offline model catalog. This generated container profile
does not migrate or overwrite the user's independent daily OMP profile. Apply
equivalent selected changes to an existing host profile only after inspection and
with a rollback. Keep actual role/model mappings valid for that internal endpoint.

The native ExtensionAPI hook lives in the active agent directory's
`hooks/pre/agentic-offline.ts` and imports the permanent reviewed asset module.
The profile installer does not rewrite OMP `config.yml`, `models.yml` or auth files.
The offline catalog patch removes one public catalog dependency; it does not prove
that every optional web, image, speech, plugin or model fallback has an internal
service. Qualify enabled features individually.

## CA trust, proxies and package repositories: scope them to each tool

Prefer existing suitable configuration, then the organization's approved private
repositories, then the verified kit fallback with recorded evidence. Use the
selected service/project environment or dedicated native package transaction.
Avoid machine-wide exports, blanket trust-store replacement or changes to unrelated
projects. A private root CA is configuration data; an auth token is a secret and
belongs in the existing credential mechanism.

| Tool or capability | Scoped setting/operation to inspect and qualify |
| --- | --- |
| Codex HTTP | `CODEX_CA_CERTIFICATE` or its documented `SSL_CERT_FILE` fallback in the Codex worker environment |
| Claude/Node-compatible client path | Existing `NODE_EXTRA_CA_CERTS` and approved proxy configuration for that client; verify the actual packaged client against the internal TLS endpoint |
| Python SSL, requests and pip | Interpreter SSL trust, `REQUESTS_CA_BUNDLE` when requests is used, and `PIP_CERT` for pip; use the existing private index/credential configuration in a dedicated venv or scoped pip config |
| npm/pnpm | Project/service `.npmrc` or scoped `NPM_CONFIG_REGISTRY`/`NPM_CONFIG_CAFILE`; preserve approved per-scope registries and token references |
| Cargo | Project or dedicated Cargo-home source/index replacement and `CARGO_HTTP_CAINFO`; preserve registry credentials separately. Use the supplied fully local source-preparation flow only for an explicitly selected kit source-build fallback |
| Git | Repository/command-scoped internal mirror configuration, existing credential helpers, and `GIT_SSL_CAINFO` or an endpoint-specific CA setting |
| curl/download verification | Per-command/worker `CURL_CA_BUNDLE` or `--cacert` with the approved CA; retain certificate verification and artifact hashes |
| Go or another language package manager | Its approved internal proxy/index and checksum policy, using the shipped version's help/source. Eliminate unapproved public fallback without globally disabling integrity checks |
| OCI images | Approved internal immutable image references and the selected daemon's existing registry trust; inspect a daemon-specific CA installation before changing system configuration |
| OS packages/native libraries | The distribution's approved internal package repositories and keyring, transaction simulation, dependency closure and package-owned paths |

Choose the private repository as the network source for the relevant installation.
Do not leave a public extra-index, public mirror fallback or build-script fetch
unexamined. Use each package manager's real offline/local mode when consuming the
kit, and verify all transitive/native inputs required by the chosen project. An
offline flag does not create missing packages.

Keep language libraries with their owning runtime/venv/application. Do not put a
Python library, Node package or shared runtime tree into `/usr/bin`. Keep complete
standalone tools under their versioned installation prefixes; use package-managed
system locations for OS-owned commands/libraries. Follow
`PRIVATE_REPOSITORIES_AND_HOST_TOOLS.md` for inspection, promotion and retirement.

The Python host launcher adds `PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`,
`PIP_DISABLE_PIP_VERSION_CHECK=1` and `PIP_REQUIRE_VIRTUALENV=1`. Preserve that intended
behavior when invoking staged Python directly; in particular run native profile
checks with bytecode writes disabled so immutable staged assets remain unchanged.
Create project venvs instead of removing the virtual-environment requirement to
install into an OS or shared interpreter.

The OpenCode host launcher adds its selected update/model-fetch/plugin/LSP-download
disables. Its core managed route remains controlled by the site configuration and
existing generated OpenCode profile. Adding native Codex/Claude workers does not
change that route or extend the controller's OpenCode/OMP `seed` choices.

## Completion record

For each context, record the actual executable identity, effective profile,
sanitized provider/model identity, CA source and credential-source type, private
repository choices, changed files, backup/receipt, and test outcomes. Demonstrate
an actual internal model response, one benign tool/file operation, native skills
and hook events, and the required restart/cancellation/resume behavior. Preserve
blocked managed policy or missing-service results and complete independent work.

Offline references: the complete Codex manual, pinned config/schema and
`codex-rs/http-client/src/custom_ca.rs` in its source snapshot; native-profile
`docs/claude/NATIVE_CONTRACT.md` and `docs/claude/cli-help-2.1.329.txt`; pinned OMP
docs/source and the offline patch; the host catalog/receipts; and
`scripts/agenticctl.py` for the exact managed OpenCode/OMP settings. No public web
access is needed to read these included contracts.
