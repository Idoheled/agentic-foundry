# One installation plan, sequential execution

Use the ordinary operator's existing internal agent to discover the machine, approve source choices through factual inspection, and complete the private component plans. The coordinator executes those plans; it does not guess repository endpoints, credentials, model routes or profile directories.

Start from `config/installation.example.json`, fill its absolute paths and factual evidence, then use:

```bash
./install-all.sh plan --site /private/installation.json
./install-all.sh apply --site /private/installation.json
```

Every wrapper uses `scripts/python.sh`, which honors the existing/internal Python selection and its explicit kit-bootstrap fallback policy. Run as the intended ordinary operator. Host and native-package installers independently use existing noninteractive sudo authority when their selected operations require it. The coordinator does not run all stages as root or switch silently to user-mode installation.

## Component plans

| Installation JSON section | Required completed input |
| --- | --- |
| `native` | Optional explicit native-package plan and separate native state directory. Set `enabled: false` only when its capabilities are already adequate or deliberately outside the requested scope. |
| `host` | Private-source host-tool plan, host state and explicit `mode: system` or `user`. Catalog defaults to this kit's `config/host-catalog.json`; `catalog` may select an inspected alternative. |
| `core` | Existing `site.json` with its completed absolute `artifactPlan`, internal model configuration and explicit core state. An optional `dockerHost` selects an inspected local Unix socket. Credentials stay in their existing private environment/files. |
| `clients` | Selected catalog names to stage as whole trees after the core installation. The example selects `codex`, `claude`, `python` and `native-profiles`. |
| `profiles` | Completed native profile plan with explicit client configuration directories, permanent asset root, selected Python and hashes. Optional selector keys identify the corresponding host catalog tools and Python command. |
| `coordinatorState` | Dedicated operator-owned directory for private logs and run reports. Unrelated populated directories and symlinks are rejected. |

`modelSmoke` is an explicit choice to exercise the existing configured internal route. The example sets it to `true`. `retireOldTools` defaults to `false` and stays false until the receiving agent has completed the old-path consumer inspections in the host plan. Retirement never occurs before all requested stages and verification commands succeed.

Keep coordinator, native-package, host-tool and core state directories separate and non-nested. In particular, putting native state inside an uninitialized core state would make the core's unrelated-directory protection reject installation. The example uses separate sibling directories for the first three and a distinct core directory.

For clients that will be staged into the core runtime, select complete normalized runtime trees in the host plan. An adequate host executable can be reused for host-only operation, but it cannot establish an unknown container dependency closure. Supply the full Python/client/archive tree rather than selecting a bare executable for container staging.

## Execution order

For `install-all.sh apply`, enabled stages run sequentially:

1. Native-package simulation and apply, when explicitly selected.
2. Host-tool plan, apply and verification.
3. Core artifact-source validation, installation and observed service status.
4. Complete selected client-tree staging into the core runtime.
5. Native host-profile check, actual apply, and idempotence check.
6. Final host/core verification, followed by the explicitly selected model smoke.
7. Explicit old-tool retirement, when selected and supported by the host plan's consumer evidence.

The core verification checks packaged commands, health and identities; it does not require agent enrollment. The coordinator never invokes `seed`, `enable-agent`, changes a model route or edits credential values. A model smoke remains narrower than a real coding-task/tool/recovery acceptance test.

The exact receipt returned by `hostctl apply` binds subsequent host verification, client staging, native-profile binding and optional retirement. It does not simply pick whichever receipt happens to be latest after another process runs. Plan output displays `@HOST_RECEIPT@` for that future receipt argument and explains its source; all other command arguments are shown explicitly. Plan mode itself does not run the component validators or certify the site's facts.

## Permanent native profiles and reviewed hooks

Complete the native profile plan from `config/native-profile.example.json` and the delivered `payload/dependencies/native-profiles/INSTALL_CONTRACT.json`. Use the exact final paths from the host receipt; the upstream profile project also includes its generic `plan.example.json`. Its `assetRoot` must equal the selected host receipt's permanent `native-profiles` tree. Its Python path/hash must match the selected verified host Python command. The coordinator checks both identities before each profile operation. The profile installer then validates the actual target files, merges namespaced changes and preserves existing model/authentication settings through its own receipt protections.

You can establish the permanent paths first with the host-only wrapper, fill the profile plan from the resulting receipt, and rerun the complete installation. Host provisioning is idempotent. Do not point hooks at a temporary extracted kit directory.

The coordinator does not fill in an asset-review hash or select Codex hook trust. If the completed profile plan explicitly contains `activateReviewedHooks: true`, it must also contain the reviewed manifest hash and inspected Codex binary/hash; the profile installer performs its supported exact-definition review/activation checks. A hook trust or policy failure stops the sequence before retirement. The example should be completed from actual review evidence, not made runnable by copying a hash without review.

Child installers inherit the existing credential environment without printing it. `PYTHONDONTWRITEBYTECODE=1` prevents profile checks from adding bytecode cache files to pinned user-mode Python/asset trees. The coordinator captures detailed child output into private 0600 logs and prints step names and report paths instead of configuration or credentials.

## Focused entry points and resumption

All wrappers use the same `plan|apply --site /private/installation.json` interface:

| Wrapper | Selected work |
| --- | --- |
| `install-all.sh` | Complete requested sequence. |
| `install-host.sh` | Host plan, apply and verification; no old-tool retirement. |
| `install-native.sh` | Explicit native-package plan and apply only. |
| `install-profiles.sh` | Verify the selected existing host receipt, check/apply/check native host profiles, and verify host tools again. |

For profiles-only use, `hostReceipt` may name the exact completed receipt. Otherwise the coordinator reads and validates the selected host state's `latest.json`. A partial installer failure stops subsequent steps, writes a blocked run report and preserves all underlying receipts/backups. Correct the concrete blocker and rerun the appropriate wrapper; it delegates to the component installers' existing idempotence and preservation checks. There is no invented global rollback for native package transactions. Use each component's documented recovery mechanism and the recorded native host recovery procedure.

Each run creates a private subdirectory under `coordinatorState` with an `installation-report.json` and one log per executed step. A successful report means the requested installer steps completed. It is not a production-readiness claim.

## Container profiles and final acceptance

Client staging produces `reports/client-runtime.json` in the core state, with exact immutable `/opt/agentic/clients/...` paths and profile-plan hints. The coordinator applies the **host** native profiles to the explicitly selected host directories. It does not execute profile installation inside Docker or assume the actual adapter/model environment is qualified.

Use the staged report to prepare and qualify any requested container-specific profile plan inside that actual execution environment. Then complete the real internal-model tool-call, coding-task, independent review, cancellation and recovery acceptance procedures. Agent enrollment and activation remain explicit subsequent actions under the handoff.
