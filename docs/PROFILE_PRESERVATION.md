# Preserving existing agents across the Claude → OMP upgrade

`scripts/profile-preservation.py` supplies a private baseline and verification gates for both phases. It uses Python 3.9+ and the standard library. Additive TOML verification requires Python 3.11+; use the bundled Python 3.12 runtime for that operation.

This helper does not install, delete, reset or rewrite any active agent configuration. Its writes are private plans, original-file backups, review receipts and verification reports. The installation agents remain responsible for discovering the complete effective configuration and testing the real engines, hooks, skills and internal model routes.

## Before invoking the replacement OMP

Inventory the current executable, aliases/functions/wrappers, launch flags, working directory, selected named profile, environment sources and referenced files. Discover all current hooks, skills, managed skills, agents, rules, extensions, memory/brain paths, project instructions, credentials, model routes and internal CA configuration.

The pinned OMP supports named profiles and configuration overlays. `OMP_PROFILE` takes precedence over `PI_PROFILE`, including an explicitly empty value. A named profile ignores `PI_CODING_AGENT_DIR`. `PI_CONFIG_DIR`, `PI_CONFIG_FILES`, command-line overrides and the exact working directory matter. Project settings are discovered from the current project's `.omp` directory. Do not assume a profile merely because its directory exists.

**Take the original filesystem snapshot before running any new OMP command that initializes settings.** Even the new binary's `config path` command initializes settings. Its native migration can convert `settings.json` into `config.yml`, rename the original to `settings.json.bak`, and merge/clear legacy settings in `agent.db`. Rehearse migrations on a copied profile and preserve the original database through a supported consistent backup. Never let the first migration happen against an unprotected live profile.

The discovery command proposes candidates and explicit exclusions, but deliberately leaves `discoveryComplete` false:

```bash
umask 077
mkdir -p /absolute/private/agentic-upgrade
chmod 700 /absolute/private/agentic-upgrade

python3 scripts/profile-preservation.py discover \
  --home /absolute/operator/home \
  --output /absolute/private/agentic-upgrade/preservation-plan.json
```

Inspect and complete the plan. Add every effective root, including project `AGENTS.md`, `CLAUDE.md`, `SYSTEM.md`, `SYSTEM_TEMPLATE.md`, `APPEND_SYSTEM.md`, `RULES.md`, custom brain directories, hook code and agent-specific directories. Add referenced internal CA and credential-source files when needed. The helper follows configuration symlinks and preserves their targets; a linked directory can substantially expand the scope.

Do not write credentials into free-text discovery evidence, terminal output, handoff instructions or public reports. Record private paths and credential-source names. Environment values are represented only by salted HMAC fingerprints; those values are not backed up by this helper. Preserve the existing environment/secret-manager source for the manual switch into OMP.

## Plan contract

```json
{
  "schemaVersion": 1,
  "operatorHome": "/home/operator",
  "discoveryComplete": true,
  "discoveryEvidence": "Actual launch flags, active profiles, project instruction roots and credential sources inspected; see private discovery record.",
  "roots": [
    {
      "path": "/home/operator/.omp/agent",
      "role": "Verified active OMP profile",
      "exclude": ["sessions/**", "logs/**", "*.sock", "*.lock"],
      "exclusionReason": "Mutable runtime/session state remains in place and is backed up with the application's supported procedure."
    },
    {"path": "/home/operator/.claude/settings.json"},
    {"path": "/home/operator/.claude/skills"},
    {"path": "/home/operator/.claude/hooks"},
    {"path": "/work/project/AGENTS.md"}
  ],
  "envNames": ["ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "PI_CODING_AGENT_DIR", "OMP_PROFILE"],
  "additiveJson": [
    {
      "path": "/home/operator/.claude/settings.json",
      "allowedPointers": ["/hooks"],
      "reason": "Exact delivered lifecycle hook definitions reviewed before installation; retain every existing hook and all existing routing/authentication values."
    }
  ],
  "additiveToml": [],
  "mutableJson": [],
  "semanticEvidence": [],
  "maxFileBytes": 67108864,
  "maxTotalBytes": 536870912,
  "maxFiles": 50000
}
```

Use actual paths and actual environment names. The example is not a complete machine inventory.

Existing items are byte-identical by default, with owner/group/mode and symlink-target checks. Directory timestamps are not treated as immutable; installing a child naturally changes them. Existing-file deletions, changed symlinks, changed permissions or changed environment values block verification.

`additiveJson` and `additiveToml` permit only additions under specifically reviewed JSON-pointer scopes. Existing keys and values remain equal; existing array entries retain their order and multiplicity. A hook addition does not authorize changing an existing hook, model, API base URL, token, default provider or permission setting. New keys outside the declared scope block verification. An empty/root-wide additive scope is rejected. The agent must review the actual added content and test the combined behavior; a structural merge cannot prove that two hook implementations cooperate correctly.

Known mutable logs, cache files and session transcripts can be explicitly excluded with a reason. Exclusion does not delete them, move them, or certify a consistent backup of a running SQLite database. Include important memories even when located under a normally transient-looking directory. Do not broaden exclusions to hide failed preservation checks.

## Snapshot once; verify repeatedly

```bash
python3 scripts/profile-preservation.py snapshot \
  --plan /absolute/private/agentic-upgrade/preservation-plan.json \
  --state /absolute/private/agentic-upgrade/preservation

python3 scripts/profile-preservation.py verify \
  --state /absolute/private/agentic-upgrade/preservation \
  --phase claude-omp-upgrade \
  --report /absolute/private/agentic-upgrade/phase1-preservation.json
```

The state must be outside all protected roots and symlink targets. Its directories are operator-owned mode `0700`; original backups and immutable baseline/review receipts are mode `0400`. Original bytes can contain credentials and must remain onsite in this private directory. Neither the handoff nor the portable kit should contain those originals.

`snapshot` refuses to replace an existing nonempty state. Both phases use the original baseline. Do not delete the state, overwrite its receipt or take a new baseline to conceal drift. A failed/incomplete initial snapshot is retained for inspection and must not be mistaken for a completed baseline.

`verify` returns exit `0` and status `preserved` only when declared existing state remains preserved and all new items have been reviewed. It returns exit `2` and status `blocked` for drift or unreviewed additions. Malformed input, missing evidence or unsupported scope returns exit `1`. With `--report`, the detailed report is private and stdout includes only status, counts, changed environment names and the report path. The report never prints configuration contents or environment values.

Every verification includes a deterministic `configurationIdentity`: SHA256 of the current protected entry identities plus the declared environment fingerprints. Timestamps, phase labels and review receipts do not affect it. An allowed configuration addition still changes this identity. The phase coordinator binds successful onsite checks to it, so changed configuration requires fresh checks. `protectedRoots` includes the original declared roots and both original/current followed symlink targets; cleanup must protect all of them.

## Narrow live-client metadata updates

A running client can update existing usage/timestamp leaves in a configuration JSON file during exit or the manual handoff. Do not exclude the whole file: it may also contain model routes, project permissions and authentication state. The optional `mutableJson` plan list starts empty and requires the receiving agent to inspect the actual current schema before selecting individual existing metadata leaves:

```json
{
  "mutableJson": [
    {
      "path": "/home/operator/.claude.json",
      "pointers": [
        "/lastSessionAt",
        "/projects/~1work~1project/lastTotalInputTokens",
        "/projects/~1work~1project/lastSessionId"
      ],
      "reason": "Inspected these exact existing fields in the installed client: they describe completed-session usage/timing only; routing, permissions and agent instructions are separate protected fields."
    }
  ]
}
```

These paths are illustrative, not a recommended list to copy. Unknown/missing fields cannot be exempted. The pointers are literal JSON pointers: `~1` means a slash in one key and `~0` means a tilde. Root scopes, wildcards, array traversal, empty fields and invalid escapes are rejected.

Only existing scalar fields with narrow recognized metadata names are eligible: timestamps; historical `lastSessionId`/`lastCompletedSessionId`; and specific numeric usage/cost/duration counters such as `lastTotalInputTokens`, `lastTotalOutputTokens`, `lastCost`, `lastAPIDuration`, `lastDuration`, or `usageCount`. Merely being numeric does not make a field eligible. Model/context/output limits, credentials, routes, provider settings, permissions, hooks, skills, brain/instruction settings and other security/control names are rejected. String-valued token counters are rejected. Ancestor field names are checked too.

The selected leaf must retain its presence and scalar type. Every other JSON value, the file's ownership and permissions, and all other protected files still have to pass verification. The original complete file bytes remain in the immutable backup. These specifically selected scalar values are normalized in `configurationIdentity`, so a natural metadata update does not invalidate otherwise unchanged probes. Changes to an actual route, brain setting, hook, skill or added configuration still change identity and/or block verification. The report lists reviewed metadata-file changes without exposing field values.

For a JSON file with both mutable leaves and declared additive hook scopes, both rules apply independently: only approved metadata values may vary, and existing values outside those leaves remain preserved. The helper does not automatically mark any client file or metadata field as mutable.

## New files require concrete review

Installing a native skill or hook can legitimately create new files/directories. The helper reports their exact identities in `unreviewedAdditions`. The receiving agent must inspect their content, source and effect. An added provider/default or project instruction can change behavior even if every old file remains intact.

After that review, create a private spec with the selected exact identities copied from the report:

```json
{
  "schemaVersion": 1,
  "reason": "Reviewed these exact new kit skill/hook files and verified their intended active profile destinations.",
  "entries": [
    {
      "path": "/absolute/profile/skills/new-directory",
      "identity": {"type": "directory", "mode": 493, "uid": 1000, "gid": 1000}
    },
    {
      "path": "/absolute/profile/skills/new-directory/SKILL.md",
      "identity": {"type": "file", "mode": 420, "uid": 1000, "gid": 1000, "sha256": "REPLACE_WITH_ACTUAL_SHA256", "size": 1234}
    }
  ]
}
```

The numbers and paths above are illustrative. Do not synthesize them. Record the actual inspected identity and then reverify:

```bash
python3 scripts/profile-preservation.py record-additions \
  --state /absolute/private/agentic-upgrade/preservation \
  --spec /absolute/private/agentic-upgrade/reviewed-additions.json
```

This is the already-authorized receiving agent's factual review, not an additional user permission prompt. Subsequent edits/removal of an approved item block verification. A review cannot authorize rewriting an existing baseline item.

## Explicit native format migration

Some genuine upgrades must change the file format while retaining configuration semantics. They require an individual, immutable migration receipt. There is no blanket ignore/rebaseline mechanism.

Before the initial snapshot, capture the real current effective settings as private JSON and list it in the plan:

```json
{
  "semanticEvidence": [
    {
      "id": "omp-active-settings",
      "path": "/absolute/private/agentic-upgrade/effective-before.json",
      "coveredPaths": ["/absolute/omp/agent/settings.json"],
      "coverage": "Complete migrated configuration, including model/provider/routes, instructions references, hooks, permissions and privately compared authentication values."
    }
  ]
}
```

The helper copies and hashes this evidence into the original baseline, binding every `coveredPaths` entry to its exact captured source digest. A migration cannot reuse an export declared for another source. The receiving agent must ensure the export is complete and actually corresponds to the inspected profile. For OMP, `config list --json` can include defaults/environment; `--scope global --json` limits the layer. Credential output can be redacted. **Two redacted exports are not evidence that secret values were preserved.** Compare the actual private credential sources and effective sensitive values without printing them. Keep the complete private evidence out of the handoff. If equivalent before/after exports cannot be obtained, do not manufacture them or mark the migration verified; leave the relevant phase blocked and describe the exact gap.

After a copied-profile rehearsal and the controlled real migration, create:

```json
{
  "schemaVersion": 1,
  "sourcePath": "/absolute/omp/agent/settings.json",
  "sourceSha256": "ACTUAL_ORIGINAL_SHA256",
  "destinationPath": "/absolute/omp/agent/config.yml",
  "destinationSha256": "ACTUAL_MIGRATED_SHA256",
  "retainedOriginalPath": "/absolute/omp/agent/settings.json.bak",
  "baselineSemanticEvidence": "omp-active-settings",
  "afterSemanticEvidence": {
    "path": "/absolute/private/agentic-upgrade/effective-after.json",
    "sha256": "ACTUAL_AFTER_EXPORT_SHA256"
  },
  "explanation": "Describe the actual native migration, copied-profile rehearsal, complete semantic comparison and private credential verification."
}
```

```bash
python3 scripts/profile-preservation.py record-migration \
  --state /absolute/private/agentic-upgrade/preservation \
  --spec /absolute/private/agentic-upgrade/omp-settings-migration.json
```

The helper requires the exact baseline source, exact migrated output inside the protected roots, retained original bytes, original semantic evidence, and JSON-equivalent before/after effective configuration. It records immutable output identities and checks them on later verification. It does not permit a migration to overwrite another protected baseline file. The retained original may be the helper's original backup if the application does not retain a native `.bak` file.

The semantic comparison proves equality of the supplied exports, not that an operator produced those exports correctly or that a client interpreted them correctly. The receiving agent must verify the provenance and completeness of those exports and exercise the real model/tool/hook behavior. A model API call, durable session resume and existing hook/skill/brain checks remain separate phase acceptance gates.

## Recovery and limitations

- Original file bytes are addressed by SHA256 under `originals/`; `baseline.json` maps each protected path to its original identity and metadata. The normal native-profile installer and host installer also retain their own transaction receipts/rollback operations.
- Before restoring configuration, stop only the relevant agent processes, inspect current edits and use exact receipt-bound originals. Do not overwrite newly authored user content or restore a live database by copying one file over an active process.
- Restore the corresponding compatible configuration and runtime together when a native format migration makes the old client unable to read the new format.
- The helper preserves symlink text, ancestry links and followed target contents. A cycle, unexpected socket/device, unreadable file, changing file, or configured size limit fails explicitly. It does not silently truncate or skip those inputs.
- State paths must have no symlink ancestors. Run as the real operator, not root pretending to be that operator; ownership checks bind receipts to the initiating UID.
- Environment fingerprints detect missing/changed configured variables; they do not save secret values or reconstruct shell startup files. Preserve approved secret sources and use the same route/profile environment for both phases.
- File xattrs/ACLs and coherent live-database/session backups are outside this byte/owner/group/mode helper's scope. If the current setup relies on those, capture and validate them with native host tools and application-aware backups as additional phase evidence.
- The plan is a declared scope. No helper can infer every external custom brain store or an undisclosed launcher. The completeness acknowledgment must reflect actual discovery, not an automatic template substitution.

The final handoff should include the private state/report locations, original baseline hash, approved migration receipts, current verified OMP command, exact launch context and remaining work. It should contain no credential values or copied private configuration bodies.
