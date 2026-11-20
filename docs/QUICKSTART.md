# Quick start

Start from the Agentic Foundry repository with its verified LFS payload, or a complete extracted release. Choose the existing-machine workflow when any active Claude/OMP profiles, model routes, hooks, skills, brain files, or sessions must be preserved.

## 1. Prepare the release

Use [Offline payloads](PAYLOADS.md) to retrieve and verify the LFS-backed artifacts. The repository entry point `deploy.sh` hydrates local payload objects before installation and delegates to `setup.sh`. `doctor` and help do not hydrate the entire payload. A source-only checkout can run controller tests but cannot install missing payload files.

For a disconnected machine, complete retrieval before transfer. Carry the complete release and its independently retained checksum, not a Git checkout whose large files are only LFS pointer text.

## 2. Check prerequisites

Run as the ordinary operator who owns the existing agent configuration. System changes use the machine's existing authorized installation mechanism; do not run the entire agent workflow as root.

The included complete native fallback targets Debian 13 on x86-64/glibc. Other Linux hosts need compatible existing capabilities or a matching qualified private profile. The shell bootstrap requires Bash, archive/checksum utilities, and normal Linux primitives. Review [platform requirements](BOOTSTRAP_AND_LIFECYCLE.md#target-support) before selecting a fallback.

From the repository root:

```bash
./deploy.sh doctor
```

The report lists actual platform and command candidates without invoking newly selected agent clients. Inspect named profiles, wrappers, environment-selected paths, and external brain/skill/hook locations; defaults alone are not a complete preservation inventory.

If no suitable Python 3.9 or later is installed, inspect the private package and artifact sources first. Prefer a qualified private interpreter through `AGENTIC_PYTHON`. If it is unavailable or insufficient, record the actual finding in `AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON` and rerun; the deployment shell can stage the fixed, hash-verified CPython payload object and the existing bootstrap can use it. See [Python bootstrap](BOOTSTRAP_AND_LIFECYCLE.md#no-python-preinstallation-requirement).

The commands below use `deploy.sh` for a Git checkout. In an already hydrated or extracted complete release, the equivalent `setup.sh` commands use the same configuration, state, and phase contract.

## 3. Create a private site declaration

Copy `config/site-minimal.example.json` to an operator-owned location outside the checkout, for example `/private/site.json`. Replace every placeholder with inspected values.

| Site input | What to supply |
| --- | --- |
| `bootstrapMode` | `fresh` for a new host, or `existing` for a workspace that must retain configuration. |
| `privateSupply` | Actual readable mirror roots or an inspected private supply index, qualification evidence, and the selected fallback policy. |
| `model` | Actual API protocol, internal base URL, model IDs, and the name of an existing credential environment variable. |
| Native packages | The matching target/native package procedure and factual private repository findings. |
| Profiles | Explicitly inspected active profile locations and preservation inputs for an existing workspace. |
| Capabilities | Selected productivity tools, worker exposure, project registration, and canonical-command policy. |

Credential values remain in the site's existing environment or supported private credential mechanism. The JSON contains references to them, not their values. Preserve existing internal CA trust and model routes.

Sites already maintaining detailed installation plans can use `config/setup.example.json` instead. The [lifecycle guide](BOOTSTRAP_AND_LIFECYCLE.md) explains the minimal compiler and detailed-plan route.

## Provision a fresh machine

After completing the private site file, inspect the plan:

```bash
./deploy.sh plan --config /private/site.json \
  --state "$HOME/.local/state/agentic-foundry/setup-v0.1.0"
```

Then perform the selected setup with one command:

```bash
./deploy.sh --config /private/site.json \
  --state "$HOME/.local/state/agentic-foundry/setup-v0.1.0"
```

This compiles or validates the explicit installation stages, selects the qualified sources, applies requested native/host/core/profile work, verifies preservation where applicable, installs selected productivity capabilities, and performs configured project/agent enrollment.

Registration leaves new task wakes disabled until real acceptance is complete. Installation does not create an internal model service or prove that every client protocol is supported by an existing endpoint.

## Upgrade an existing workspace

Start from the existing working Claude environment:

```bash
./deploy.sh agent --config /private/site.json \
  --state "$HOME/.local/state/agentic-foundry/setup-v0.1.0"
```

The agent can begin discovery without a site file by omitting `--config`; it must establish the factual private configuration before applying the corresponding setup stages.

The workflow has a mandatory manual boundary:

1. **Claude performs phase 1.** Inventory and preserve actual configuration, select and upgrade OMP with its proven prerequisites, verify its model/tool/session behavior, and write the bound handoff.
2. **Claude stops.** It reports the phase result and the exact continuation command.
3. **You launch the qualified OMP.** Use the command recorded in `OMP_HANDOFF.md` under private upgrade state. Do not substitute a new command or override the recorded launch arguments.
4. **OMP performs phase 2.** Complete the remaining native tools, clients, profiles, Paperclip integration, and requested productivity capabilities while preserving the OMP runtime executing the continuation.
5. **Complete real acceptance.** Verify internal model/tool behavior, worker execution, project delivery, preservation, and selected browser capabilities before enabling ordinary task dispatch.

Read [phase 1](PHASE1_CLAUDE.md), [phase 2](PHASE2_OMP.md), and [the receiving-agent handoff](../HANDOFF.md) for the exact gates.

## Resume or add selected capabilities

Repeat the same setup command with unchanged inputs and the same private state after resolving a transient blocker. Completed stages are verified before they are reused. Do not delete transaction state or reset a preservation baseline to make a failed check pass.

If a selected input changes, inspect it and use a new setup transaction while retaining the original profile-preservation baseline. For productivity additions after the qualified phase-2 core installation:

```bash
./deploy.sh apply --only productivity \
  --config /private/setup.json \
  --state "$HOME/.local/state/agentic-foundry/productivity-v0.1.0"
```

The referenced file must be the actual completed site/setup configuration, not an unedited example. This scope reports productivity completion only and does not replace the OMP runtime.

## Know when the deployment is ready

| Evidence | Meaning |
| --- | --- |
| `plan_validated` | Declarations and source identities passed available planning checks. |
| `requested_setup_steps_completed` | Requested installation stages completed and their required checks passed. |
| `productivity_completed` | Only the selected productivity scope completed and passed. |
| Real acceptance report | Actual model/tool/session/project behavior was checked for the selected worker and host. |
| Explicit worker admission | The accepted worker is enabled through the supported controller/API path. |

The browser gate must run on the receiving machine. The builder verified Chromium bytes, dependencies, version, and relocation, but its environment blocked real UI interaction. A browser version check cannot replace the supplied form-input, click, DOM, screenshot, and trace test.

Continue with [Operations](OPERATIONS.md) for project workflow and failed-step handling.
