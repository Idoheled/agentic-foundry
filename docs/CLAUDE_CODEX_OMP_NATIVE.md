# Claude Code, Codex and OMP: native offline skills and hooks

The kit installs **eight curated skills into each selected client's native skill
directory**, native Claude/Codex command hooks, and a native OMP ExtensionAPI
module. These are working installation assets with code, tests, a source archive
and a Git bundle. Suitable existing tools and approved private repository
artifacts take precedence over the kit's fallback executables. The existing
working Claude Code and OMP model routes, credentials and permissions are kept.

Qualified native versions are Claude Code **2.1.329**, Codex **0.171.0**, and OMP
**19.0.1** with the kit's offline catalog patch. The profile project version is
`2026-11-20-r3`. Exact pins and hashes are in the native payload's
`INSTALL_CONTRACT.json`, `PACKAGE_INDEX.json` and `provenance-downloads.json`.

## The installed skills

| Skill | When it is useful |
| --- | --- |
| `agentic-plan-and-deliver` | Plan a substantial change, define acceptance, complete implementation and report evidence |
| `agentic-parallel-worktrees` | Give concurrent writers separate branches/worktrees, bounded ownership and explicit integration handoffs |
| `agentic-debug-systematically` | Reproduce a failure, test competing explanations and fix the demonstrated cause |
| `agentic-review-and-verify` | Review independently and verify actual changed behavior and operational boundaries |
| `agentic-private-dependencies` | Prefer internal OS/OCI/language/Git/artifact sources; use verified kit fallback with a documented reason |
| `agentic-host-tooling` | Inspect ownership, links, consumers and runtime closure before installing, migrating or retiring tools |
| `agentic-offline-acceptance` | Qualify the real host, internal model, native hooks, restart behavior and admitted concurrency |
| `agentic-handoff-and-recovery` | Preserve resumable checkpoints and recover interrupted work without losing changes |

These are original kit skills. They supplement native builtins and existing team
skills. The complete published Anthropic skills/plugins and OpenAI skills source
snapshots are also included for reference. They are not all enabled: an upstream
skill can require an external service, a browser, a converter or a language server
that must first have its own working internal substitute and dependency closure.

## Native paths and profile selection

The receiving agent must identify the **actual daily operator and active profile**
before installation, including named OMP profiles. A provisioning root account
does not identify the daily operator. The plan makes every destination explicit.

| Client | Skills | Hooks |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/agentic-*/SKILL.md`, or the selected `CLAUDE_CONFIG_DIR/skills` | Additive entries in the selected Claude `settings.json` |
| Codex | `~/.agents/skills/agentic-*/SKILL.md` for the operator | Additive entries in `$CODEX_HOME/hooks.json`, normally `~/.codex/hooks.json` |
| OMP | `<active agent directory>/skills/agentic-*/SKILL.md` | `<active agent directory>/hooks/pre/agentic-offline.ts` imports the permanent module |

OMP normally uses `~/.omp/agent`. A named profile uses its own agent directory;
`PI_CODING_AGENT_DIR` overrides the default profile, not a named profile. Codex's
user skill directory is independent of a custom `CODEX_HOME`.

Extract the flat native profile source archive to a permanent versioned host
prefix, for example `/opt/agentic/toolchains/native-profiles/2026-11-20-r3`.
`install_profiles.py --plan /private/native-plan.json --check` inspects the proposed
changes; `--apply` installs them. `plan.example.json` documents all required paths
and hashes. Invoke the installer as the operator, using the verified Python.
Do not render hooks against a temporary tar extraction directory.

Python hooks use absolute executable and script paths. The OMP shim uses an
absolute module path. Python's full runtime and standard library stay together.
No pip or npm installation is needed for these skills and observers. The optional
Claude environment fragment is `claude/offline-env.json` in the installed profile
source; apply it through the host's inspected launcher configuration while
preserving the working gateway environment.

## What the hooks do

Session-start context reminds the agent to prefer internal sources, inspect
existing tool ownership and consumers, preserve rollback and report actual
evidence. Native lifecycle events append small local records containing client,
event, time, profile version, a shortened SHA256 of the session identifier and a
validated tool name when present. They do **not** record prompts, command text,
tool arguments or outputs, paths, transcripts or credentials.

Logs require a private operator-owned directory and regular 0600 files. Daily
files stop growing around 5 MiB per client; no automatic deletion is performed.
The hooks make no model or public-network call, do not approve tools, and do not
change a permission decision. Errors fail open. These observers help operations;
they are not a sandbox or a complete security audit trail.

Claude command hooks cover SessionStart, PostToolUse, PostToolUseFailure,
PreCompact, Stop and SessionEnd. Codex uses SessionStart, PostToolUse, Stop and
SessionEnd. Its SessionEnd deadline is three seconds; the other command hooks use
five seconds. OMP registers the corresponding verified native extension events.

## Native Codex trust activation

Non-managed Codex hooks require exact-definition trust. The installer does not
call a file copy a successful activation. With `activateReviewedHooks: true`, it
verifies the reviewed asset manifest and selected Codex executable hash, renders
its four expected definitions, and invokes the supported native app-server APIs:

1. `hooks/list` identifies the exact user-source file, event, command, matcher and
   timeout and supplies Codex's current definition hashes.
2. `config/batchWrite` records approval for only those reviewed kit definitions,
   using the same operation as the native `/hooks` interface.
3. A second `hooks/list` must report all four definitions trusted.

Unrelated hooks remain in their existing state, and managed policy is preserved.
A disabled, rejected or incompatible definition stays blocked with a private
activation report. The installer exits 2 in that case after retaining the
installed files. It never manufactures hidden approval state. A repeat apply
checks native trust again and does not duplicate hooks. The helper is qualified
for Codex 0.171.0; another private version requires native API requalification or
its own native reviewed hook workflow.

## Preserve gateways and enforce real protocol compatibility

Keep the user's existing working Claude and OMP profiles. Do not overwrite gateway
URLs, authentication mechanisms, model IDs, internal CAs or permission settings
with sample values. The kit contains no real credentials or internal model
weights. Configure site secrets through the existing private mechanism.

Claude Code needs the gateway behavior expected by its Anthropic Messages client;
Anthropic does not document support for arbitrary non-Claude backend models.
Codex's custom provider requires the **Responses API**. A Chat Completions-only
endpoint is not sufficient for Codex, and the kit does not claim an unverified
translator supplies the missing behavior. OMP has native adapters for several
protocols; select and verify the adapter used by the actual internal service.
An incompatible route must remain blocked instead of being reported as ready.

## Preservation and recovery

JSON settings are merged additively. Unrelated hook entries and existing Claude
settings are preserved; OMP's model/settings files and authentication files are
not rewritten. Unknown differing namespaced files require their current hash and
an inspection reason before authorized replacement. Original bytes and modes are
kept in private backups with a transaction receipt.

`--rollback` verifies all affected files before changing any and refuses to
overwrite subsequent user edits. It restores original native definitions and
removes only unchanged new files. Codex's exact-definition approval history is
not rewritten during rollback; unrelated native configuration remains intact.

For executable migration, inspect package ownership and every relevant consumer.
Use the package manager for `/usr/bin` and distro libraries; standalone complete
runtimes normally belong in versioned `/opt` locations with inspected local entry
points. An unusual path alone does not justify deletion. Retire a confirmed old
copy only after its consumers have been migrated or shown unaffected, the new
runtime has passed fresh-shell/service checks, and a usable rollback exists.

## Verification and source/rebuild scope

The packaged evidence records **11 passing Python tests**, a real OMP extension
module test, and real native Claude and OMP loopback runs that discovered all
eight skill names and executed SessionStart, Stop and SessionEnd hooks. The real
Codex installer/API probe approved exactly four hooks, approved zero on repeat,
left an unrelated hook untrusted and restored original definitions on rollback.
Codex handler output also passed its pinned upstream schemas. A complete Codex
model turn and native hook execution still need the target sandbox/provider gate;
the builder's separate turn probe encountered a bwrap NETLINK_ROUTE restriction.

The qualified Claude runtime here is Linux x64 glibc. The additional musl archive
has an upstream-matching checksum and inspected layout but was not executed on a
musl host. Target host, real model, cancellation/resume, restart persistence and
parallel workload acceptance remain explicit receiving-machine checks.

The authored profile project is fully editable and needs no compilation. Its
Git bundle contains its complete local history. Claude's official public
repository and published executables are included, but **Claude's full runtime
implementation is proprietary and cannot be rebuilt from that public snapshot**.
Codex and OMP public source/build materials live in their respective kit payloads;
read each component's recorded rebuild qualification rather than treating a
source snapshot or dependency cache as proof of a completed offline rebuild.

Primary references captured for this integration:

- <https://code.claude.com/docs/en/skills>
- <https://code.claude.com/docs/en/hooks>
- <https://code.claude.com/docs/en/settings>
- <https://code.claude.com/docs/en/llm-gateway>
- The pinned Codex source and official hook/provider documents in its payload.
- The pinned OMP `docs/skills.md`, `docs/hooks.md`, `docs/extensions.md` and
  `docs/extension-loading.md` copied into this payload.
