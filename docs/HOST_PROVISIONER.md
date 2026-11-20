# Host tools provisioner

`hostctl.py` installs actual, source-selected Linux tools and complete runtime trees. It uses Python 3.9+ and the standard library. It is independent of the Paperclip/runtime controller: the host receiving agent supplies a tool catalog and an inspected private-source plan.

The required order is **adequate existing tool → approved internal staged artifact → documented kit fallback**. The program never fetches public artifacts. It verifies the exact selected files before staging. Repository discovery, authenticated internal downloads and compatibility judgment belong to the receiving agent; the plan records its findings.

## Scope

Supported payloads are executable files, tar archives understood by Python's `tarfile`, and ZIP archives. Entire trees are retained, including Python libraries, npm packages, compiler libraries, licenses and relative symlinks. `requiredPaths` and executable probes check declared closure. A source tree that needs compiling must first be built into a qualified runtime archive. Native `.deb`/RPM groups remain explicit handoffs to the target-distro package helper; this program does not install arbitrary files into package-owned `/usr/bin` or replace OS Python.

System mode installs versioned trees under `/opt/agentic-stack/tools/<name>/<version>-<artifact-hash-prefix>`. Every command gets `/usr/local/bin/agentic-<command>`. These are small launchers that prepend the matching runtime's `bin` paths before executing the real tool. This keeps npm/npx with their selected Node and preserves Python/compiler library trees. Canonical names such as `/usr/local/bin/node` are optional inspected symlinks; they are not changed merely because a payload is present.

Explicit `--mode user` uses `$HOME/.local/share/agentic-stack/tools` and `$HOME/.local/bin`. It does not claim to provide a system-wide installation. System mode starts as the ordinary operator and uses existing `sudo -n` authority for the mutating command. If that authority is unavailable, it reports the constraint; it never silently changes to user mode. The elevated invocation records the operator UID/GID and returns private receipt ownership to that operator. Versioned trees and system entry points are created by root. The source is plain, reviewable Python; privilege applies only while performing the requested staged install, entry-point, receipt and recovery operations.

## CLI

Run from the extracted kit using its selected Python interpreter. All paths below are examples to fill with actual site paths.

```bash
python3 hostctl.py inventory --catalog /kit/host-tool-catalog.json --payload-root /kit
python3 hostctl.py validate --catalog /kit/host-tool-catalog.json --payload-root /kit --plan /private/host-tool-plan.json
python3 hostctl.py plan --catalog /kit/host-tool-catalog.json --payload-root /kit --plan /private/host-tool-plan.json
python3 hostctl.py apply --catalog /kit/host-tool-catalog.json --payload-root /kit --plan /private/host-tool-plan.json
python3 hostctl.py verify --catalog /kit/host-tool-catalog.json --payload-root /kit
python3 hostctl.py retire --catalog /kit/host-tool-catalog.json --payload-root /kit
python3 hostctl.py rollback --catalog /kit/host-tool-catalog.json --payload-root /kit
```

Use the same `--state`, `--mode` and operator for subsequent commands. State defaults to `$HOME/.local/state/agentic-stack/hostctl`; `--receipt` selects an earlier receipt explicitly. `--output` saves JSON inside the selected state directory. `validate` and `plan` resolve sources, verify hashes, check platform constraints and inspect command occupants without installing. `inventory` checks conventional locations and the actual PATH and records executable identities/package ownership.

Mutating CLI commands take an exclusive state lock. An interrupted or failed installation leaves a receipt naming completed operations and blockers. Read it before continuing. `rollback` handles recorded entry-point changes and quarantine moves; installed versioned trees remain available for inspection. It will not overwrite an occupant changed independently since the receipt. If failure occurred before the `latest.json` pointer was set, pass the printed or discovered failed receipt path explicitly.

## Catalog schema

The catalog is JSON:

```json
{
  "schemaVersion": 1,
  "tools": {
    "node": {
      "version": "QUALIFIED_VERSION",
      "platform": {"architectures": ["x86_64"], "glibcMin": "2.28"},
      "commands": {
        "node": {"path": "bin/node", "verifyArgs": ["--version"]},
        "npm": {"path": "bin/npm", "verifyArgs": ["--version"]},
        "npx": {"path": "bin/npx", "verifyArgs": ["--version"]}
      },
      "pathEntries": ["bin"],
      "requiredPaths": ["lib/node_modules/npm"],
      "artifact": {
        "path": "payload/host-tools/node-runtime.tar.xz",
        "sha256": "REPLACE_WITH_EXACT_ARTIFACT_SHA256",
        "format": "tar",
        "stripComponents": 1
      }
    }
  }
}
```

`artifact.path` is relative to `--payload-root`. `format` is `file`, `tar` or `zip`. `stripComponents` applies to archives and their hardlink targets. For a raw file with several command definitions, set `artifact.destination` to its relative installation path. A single-command raw file defaults to that command's path.

`commands` values may be a relative path string, or an object containing `path`, `verifyArgs`, optional `verifyPattern` and optional `verifyTimeoutSeconds`. Tool-level `verifyArgs` defaults to `["--version"]`. A meaningful bounded Python probe can import `ssl`, `sqlite3`, `venv` and other required modules. Version output alone is not proof that every optional package works. Use `requiredPaths` for the declared library/package layout and run project tests after provisioning.

`pathEntries` contains relative directories to prepend to PATH in installed launchers. Whole runtime archives should preserve their upstream relocatable layout. Absolute/escaping links, traversal, duplicate archive destinations, special device files and links resolving outside the tree are rejected. Files are streamed while extracting; archives are not loaded wholly into RAM. Directories use mode 0755; executable files use 0755 and other regular files 0644. Special permission bits are discarded.

Optional tool-level `environment` maps valid environment-variable names to literal string values. These settings apply to initial checks, existing-tool checks, verification and generated launchers; shell launchers quote values literally. Other inherited variables remain intact. Use this only for reviewed **nonsecret runtime controls**, such as `PYTHONDONTWRITEBYTECODE: "1"` for an immutable Python tree or verified offline/update flags for a specific client version. Do not put tokens, passwords or model/auth routing overrides in the catalog. Existing credential and routing configuration belongs to the site's separate approved configuration. Invalid names, non-string values and NUL bytes are rejected before installation.

`platform.architectures` and `platform.glibcMin` are optional actual compatibility constraints, not decorative metadata. Populate them from verified release evidence. Other platform facts should be kept as provenance rather than assumed executable checks. Actual command execution remains required.

For a native package group use `kind: "native-package-group"` with its target-distro metadata. `apply` records an explicit blocker for that group; the separate qualified package helper must perform it. The receiving agent must report the native helper's result separately and cannot treat this handoff as installed capability.

For a versioned non-executable asset bundle, use `kind: "asset-tree"`, `commands: {}`, a tar artifact and a nonempty `requiredPaths` list. This installs the complete tree under its normal versioned tool path and verifies its full-tree identity. It creates no command shim and claims no executable/runtime qualification. For example, native-profile installer scripts and skill assets can live permanently under the `native-profiles` tool directory; invoke their real installer separately using the already selected and verified Python as the ordinary operator. Existing asset archives may be normalized with `source: "existing"` and `normalizePath: true`; executable-only reuse is not an asset-tree installation.

## Private-source plan

```json
{
  "schemaVersion": 1,
  "privateRepositoriesChecked": [
    "Internal approved runtime repository inspected; exact selected Node archive staged locally"
  ],
  "tools": {
    "node": {
      "source": "internal",
      "path": "/private/staging/node-runtime.tar.xz",
      "sha256": "REPLACE_WITH_VERIFIED_INTERNAL_ARTIFACT_SHA256",
      "version": "QUALIFIED_VERSION",
      "evidence": "Actual compatibility and provenance findings; no credentials",
      "canonicalLinks": [
        {"path": "/usr/local/bin/node", "command": "node", "expected": {"kind": "missing"}}
      ]
    }
  }
}
```

Select only the tools needed for this installation and its projects. Internal artifacts must be staged outside the kit payload root so the record accurately distinguishes them from kit files. Internal choices may override `format`, `stripComponents`, `destination`, `sha256` and `version`; qualify a divergent internal runtime and its layout before selecting it. There are no arbitrary shell command fields.

A kit choice uses `source: "kit"`, factual `evidence`, and `fallbackReason` equal to `unavailable`, `incompatible` or `insufficient`. The catalog fixes its artifact path/hash. A different internal version is not inherently insufficient: inspect its actual compatibility and offline behavior first.

For suitable existing commands use `source: "existing"`, `adequate: true`, and `executables: {"command": {"path": "/actual/command", "sha256": "…"}}`. A single-command tool may use top-level `path` and `sha256`. Existing tools are reused in place and verified; the launcher does not copy an isolated system executable and pretend it includes its libraries. Optional existing-tool `pathEntries` are absolute supporting directories needed by that existing installation.

For an existing unmanaged artifact in the wrong place, use `source: "existing"` with `normalizePath: true`, an inspected `path`/`sha256`, and a suitable artifact format/layout. This installs a verified file or complete archive into the standard versioned tree. A complete interpreter/toolchain must retain its complete dependencies; do not normalize it by copying only its executable. After replacement verification and consumer inspection, the separate retirement request can remove the old active location into quarantine.

### Inspected entry points

`canonicalLinks` entries select the exact local-bin path, `command`, inspected `expected` snapshot and `replaceReason` when an occupant exists. The local bin is `/usr/local/bin` in system mode or the explicit user's `$HOME/.local/bin` in user mode. `/usr/bin` changes require native package management and are rejected here.

An expected absent path is `{"kind":"missing"}`. An expected regular file needs `kind: "file"`, its `sha256` and numeric `uid`; an expected symlink needs `kind: "symlink"`, its literal `target` and numeric `uid`. Inventory provides full snapshots including mode/GID/size; all supplied fields must still match. Package-owned occupants, directories, special files and uninspected occupants block replacement. Symlink parents also require separate inspection rather than being silently followed.

Namespaced `agentic-*` destinations must initially be absent or match an explicit `namespaceExpected` snapshot keyed by command, with `replaceReason`. After successful provisioning, the private managed-launcher index permits later verified updates and idempotent reapplication. A changed managed occupant blocks the operation. Canonical entries still must be listed explicitly in each source plan.

## Retirement of the old active artifact

An example `retire` item within a tool choice is:

```json
{
  "path": "/old/location/tool",
  "expected": {"kind": "file", "sha256": "EXACT_OLD_HASH", "uid": 1000},
  "unreferencedWithinInspectedScope": true,
  "consumersChecked": [
    "Actual PATH/launcher references inspected and migrated",
    "Actual service and project configuration references inspected",
    "Applicable running processes/scheduled tasks inspected"
  ],
  "evidence": "Actual findings explaining why this exact unmanaged artifact is now safe to retire"
}
```

The agent must perform these inspections; example statements are not evidence. `retire` first verifies the replacement commands and their receipt identities, then allows only the exact inspected unmanaged file or symlink. It refuses package-owned files, directories/shared installations, changed occupants, active promoted paths, managed installation/state content and any executable still reused by the replacement. Missing reference evidence leaves the old path in place with an explicit blocker.

The old artifact moves to `/opt/agentic-stack/quarantine/<receipt-id>/…` (or the explicit user-mode equivalent), outside its active location. No unknown directory is recursively deleted. This is scoped reference evidence, not proof that no conceivable external consumer exists. If the receiving agent cannot establish the required scope, it must report that retirement remains blocked instead of claiming perfect cleanup.

Backups of replaced command entry points remain under `hostctl-backups/<receipt-id>`. `rollback` restores quarantined originals and earlier entry points after checking that current occupants still match the receipt. It preserves versioned runtime trees and restored ownership. It cannot roll back unrelated native package transactions; the native helper must record those separately.

## Tests and actual verification scope

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Tests use `--prefix`/the equivalent API to map host paths into an isolated fake filesystem. They cover a misplaced artifact migration, canonical link rewiring, real fixture command execution from fresh shell processes, quarantine retirement and rollback; preservation of unknown/package-owned paths; dependency trees and relative links; traversal rejection; existing reuse; idempotent updates; missing fallback/reference evidence; and rollback conflicts. They do not mutate the real host or demonstrate target-machine sudo, real internal repositories, actual production interpreters or project compatibility.

The receiving agent must still run the real catalog probes on the target machine, test the actual service account/environment, and execute representative project imports/builds/tests. Host-tool verification and model/agent acceptance are separate evidence.
