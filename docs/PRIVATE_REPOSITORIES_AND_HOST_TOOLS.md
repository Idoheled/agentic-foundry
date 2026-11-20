# Private repositories and usable host tools

## Required outcome and source order

The receiving agent must leave the Linux machine with the tools and dependencies needed to operate this stack and work on its selected projects. Downloaded archives, source trees, a proposed installation plan and container-only tools do not establish that the host has usable capabilities. Implement the installation and prove the resulting commands work.

Use this order for every executable, image, OS package, language library, native dependency and build tool:

1. Preserve and reuse a suitable installed component or verified local cache. Inspect the version, provenance, required features, dependency closure and actual execution context.
2. If something is missing or insufficient, use the organization's approved private repositories, registries and caches. Prefer existing repository configuration, authentication, trust and package management conventions.
3. Use the verified artifact in this kit only when internal supply is unavailable, incompatible or insufficient. Record the repositories checked, candidate inspected, exact reason and relevant evidence.

There is no public-internet fallback. Do not add a public package index, invoke a network installer, resolve `latest`, disable TLS verification or let an optional plugin fetch public dependencies to get past a missing internal artifact. Approved internal networking is expected and allowed.

The user authorizes routine installation and a necessary replacement after inspection. Continue safe, authorized work without repeated confirmation. Keep satisfactory existing components. If a replacement is needed, record why, preserve a recovery path, validate the candidate and then promote it. A missing privilege or unavailable artifact is an explicit constraint; complete independent work and state the exact remaining requirement.

## Discover internal supply before choosing a fallback

Use repository locations already configured for this machine or documented for the user's projects. Inspect the relevant configuration selectively rather than dumping complete files or environments. Typical sources include internal distro repositories, an OCI registry, Artifactory or another artifact service, Python and npm package repositories, Git mirrors, and compiler/language dependency caches. Include transitive dependencies, native libraries, browser/LSP assets and build-time downloads where the chosen projects require them.

Reuse existing credential helpers, client certificates and approved CA trust. Record repository identities and credential-source types without tokens, passwords, credential-bearing URLs or headers. Never place credentials in this guide, a plan checked into source control, command-line download URLs or task evidence.

Record each search in `privateRepositoriesChecked` and in the detailed decision report: repository identity, artifact/query, time, result and compatibility finding. An empty search, an authentication failure, an unavailable repository and a present but unsuitable package are different observations. An access problem does not prove absence. Check remaining relevant sources and record the actual access constraint before selecting a temporary fallback.

For language packages, make the selected private repository the only network source for that installation. Do not retain a public `extra-index-url` or equivalent fallback. Inspect lockfiles and package build scripts for embedded source URLs and secondary fetches. Use approved mirrors or staged local dependencies while preserving hashes and the dependency lock. For a fully staged install, use the package manager's supported offline/local options; an offline flag does not create missing dependencies.

## Runtime artifact plan used by the controller

Create a private JSON plan from `config/artifact-plan.example.json`, then set the absolute path in the site's `artifactPlan` field. Do this before `install` or `configure`. Keep the completed plan and staged files available for subsequent configuration changes. The controller does not discover the organization's repository topology or credentials for you; the receiving agent performs that work and stages selected files locally.

The exact contract and capability-report checks are in `docs/ARTIFACT_PLAN_FORMAT.md`; validate it with `./install.sh sources --config /private/path/site.json`. The plan uses `schemaVersion: 1`, a nonempty `privateRepositoriesChecked` list, six required `files` selections (`docker`, `compose`, `omp`, `herdr`, `opencode`, `ompAdapter`), and two `images` selections (`paperclip`, `postgres`). Every selection records `source` and factual `evidence`. Use `source: existing`, `source: internal` or `source: kit` according to what was actually selected.

| Selection | Required evidence and identity |
| --- | --- |
| Existing/internal file | Absolute staged `path` and `sha256`; by default the hash must match the shipped tested artifact. A different filename is acceptable. |
| Existing/internal image | Immutable `imageRef` of the form `registry/repository@sha256:…` from an explicitly allowlisted internal registry (or the exact cached config ID for `source: existing`), plus `expectedConfigDigest` matching the shipped image's config digest. A registry manifest digest and a local image/config digest are different identifiers; record both correctly. |
| Kit fallback | `fallbackReason` equal to `unavailable`, `incompatible` or `insufficient`, plus concrete `evidence` and the recorded internal searches. |
| Qualified host Docker/Compose | Follow the template's executable-format and `qualificationReport` contract. Pin the actual executable hash and prove the capabilities used by this stack; a version string alone is not qualification. |

For an existing or internally supplied host Docker client, `files.docker` may use `format: executable` with a qualification report. Compose is already selected as an executable. Read the controller/template for the precise report checks. If the separate daemon bootstrap is required and the Docker client selection is an executable, record a `files.dockerDaemon` archive selection as well. Invoke that optional helper with `--artifact-plan /absolute/private/artifact-plan.json`; it does not authorize replacing the system daemon.

Approved internal images may be explicitly fetched by immutable reference during preparation. Application startup uses the selected locally available images with automatic pulls disabled. The image bytes remain the tested baseline; only the supplying registry/reference changes. Do not overwrite an unrelated local image tag to make the plan pass.

The baseline runtime hook intentionally requires tested artifact identities, except for its explicitly qualified host Docker/Compose path. This is a reproducibility constraint, not a rule that all other internal releases are unsuitable. When a different internal release provides the needed capabilities, inspect and qualify it, adapt the included deployment recipe/controller explicitly, and record the new provenance and tests. Check adapter/API compatibility, native-library closure, offline behavior, model protocols, cancellation and state compatibility. Do not bypass an identity check and reuse the shipped validation claim. If a candidate lacks required behavior, record the specific deficiency before falling back to the kit.

Keep the artifact plan separate from the host-capability inventory. The controller's runtime selections do not install every host development tool, configure all internal package managers, or certify the host report. The receiving agent must perform that work.

## Bootstrap Python and container runtime

Prefer an already suitable Python interpreter. `scripts/python.sh` accepts `AGENTIC_PYTHON` as an explicitly selected interpreter; otherwise it checks the existing `python3` for the supported version. If neither works, inspect internal distro/package sources before using portable Python from this kit. Only then set `AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON` to a factual explanation of the unavailable or insufficient internal option. This permits the checksum-verified bootstrap fallback; it does not install or replace the OS Python.

For the final host Python capability, use the normal package/path policy below. Record which interpreter runs the controller and which interpreter/virtual environment each project uses. A temporary bootstrap runtime is not automatically the machine's supported development runtime.

Reuse a suitable existing local container daemon. If absent, prefer an approved internally supplied native/container-runtime package. Only use the kit's separate static daemon after the documented internal search and host qualification. The daemon helper requires a completed artifact plan and uses its selected archive; it needs existing system privileges and compatible host facilities. Do not silently change privileges, stop another daemon or redirect all Docker commands to an unrelated socket.

## Correct installation destinations

Choose paths by ownership and function. The executable or library must be available where the actual caller expects it, with correct ownership, permissions, interpreter and runtime dependencies.

| Component | Destination and installation rule |
| --- | --- |
| Distro-packaged executable | Install the approved internal package through the machine's package manager. It places files in its declared locations, often `/usr/bin`, and records ownership/dependencies. |
| Distro library or Python distribution package | Install through that package manager into the distribution's declared library/package paths. Do not manually copy files over package-owned paths. |
| Standalone executable/toolchain | Install into a versioned directory such as `/opt/<tool>/<version>`. Expose an inspected `/usr/local/bin/<name>` symlink or a small configuration-aware launcher where needed. |
| Python application or project libraries | Use a dedicated environment such as `/opt/agentic/venvs/<tool>` or the project's designated virtual environment. Install libraries into that interpreter's `site-packages`. |
| Python CLI entry point | Use the environment's real `bin/<command>` and expose a suitable `/usr/local/bin` link/launcher. Keep its interpreter and installed libraries together. |
| Native shared library | Prefer the internal native package. Otherwise keep the versioned library with its application and use its documented loader arrangement. Change system loader configuration only when required, inspected and recoverable. |
| Node application and packages | Keep the application and locked dependencies in an explicit versioned application directory. Use the selected Node runtime and expose its actual CLI entry point. Do not assume a global package installed for one account is visible to a service. |
| Service configuration/state | Use the existing host conventions and dedicated paths; separate mutable data, secrets, logs and immutable binaries. Record ownership and service environment. |

**A Python dependency is not a file to place in `/usr/bin`.** A Python executable supplied as a native OS package may belong there; a Python library belongs in the interpreter's package path or a virtual environment. Do not manually copy a Python tree into `/usr/bin`, use unrestricted system `pip`, or repoint `/usr/bin/python3` to satisfy an application dependency.

Where `/usr/bin/python3` or another OS-owned command truly needs an update, inspect package ownership, distribution support, existing consumers and rollback first. Use the supported internal package transaction or supported alternatives mechanism if that distribution provides one for that command. Do not invent an alternatives entry for an OS interpreter that the distribution expects to remain fixed. A separate versioned interpreter is often sufficient for the application.

Do not install every optional tool merely because the kit contains it. Start with the operational stack and actual project requirements. A practical inventory includes Git; archive, checksum and transfer tools; JSON and source-search tools; Python; the required Node runtime; container tooling; and the project's package managers, compilers, test runners and native libraries. Mark optional or unavailable capabilities explicitly. `config/host-capabilities.example.json` is an editable receiving-agent checklist, not an executable installer or an extra controller input.

## Preserve, replace and repair links deliberately

Before touching an existing destination, inspect its file type, permissions, owner, package owner where applicable, resolved symlink target, version/hash, current consumers and relevant configuration. Check with the existing package database and runtime/service configuration. Preserve a healthy component that already meets the requirements.

For a necessary replacement, write the reason and a concrete rollback before applying it. Preserve the previous version, configuration and link target; use a package-manager transaction or a versioned directory to make restoration practical. Account for reverse dependencies and services using the current tool. A database/application state migration may require the matching database snapshot, not only restoring the executable.

Stage the candidate at its final versioned location, verify identity and dependency closure, run a bounded smoke check, then promote the appropriate entry point. For a locally managed symlink, create a temporary link in the same directory and atomically replace the link only after the destination is verified. Record the old and new targets and exact restoration steps. Do not use a blind force-link command against a real file, package-owned link, unrelated command or an uninspected broken link.

A conflicting adequate command does not need replacement just to expose the new stack. Use an explicit versioned command or a clearly named launcher where coexistence satisfies the requirement. If a global replacement is needed, apply the recorded inspection/validation process. Do not delete the user's only working OMP/Claude Code entry point while using it to perform the setup.

## Host, service and container closure are separate

Check the actual execution environment. A host-installed Python library does not appear in the Paperclip container. A copied host executable may depend on a libc or shared library absent from the image. A container binary at `/opt/agentic/bin` does not become a host command simply because its files exist under the state directory.

Provide dependencies through the selected image, a verified runtime directory or an explicitly qualified mount, as appropriate. Test imports, dynamic loading, native modules, internal CA trust and credentials from the actual worker/service identity. Do not mount broad host directories to mask a missing dependency.

The managed OMP wrapper in this kit has container-oriented `/paperclip` configuration defaults. A host launcher needs host-appropriate configuration/session directories, native-module paths and the user's internal model credential mechanism. Do not create a global symlink to that wrapper and claim success without a real host invocation. Preserve the existing working host OMP/Claude configuration unless a tested migration is needed.

Configure service PATH and environment through the actual service definition. Shell profile edits do not configure systemd services. Verify a fresh login/noninteractive shell and the real service/container context, using `command -v`, `type -a`, resolved paths, version output and a representative operation. Refresh an interactive shell's command cache when necessary, then test again from a new process.

## Reports and completion criteria

Store sanitized evidence under the private state directory or record equivalent explicit locations:

| Report | Required contents |
| --- | --- |
| `reports/host-tool-inventory.json` | Required capability; existing executable/package/interpreter; version; resolved path; owner/package owner; relevant service or project consumers; adequacy finding. |
| `reports/artifact-decisions.json` | Internal repositories and caches inspected; query/results; selected source/version/hash or image identities; dependency closure; fallback/replacement reason; qualification evidence. |
| `reports/host-installation-report.md` | What was actually installed or reused; destination paths; commands/launchers and symlink targets; package transactions; environment/service integration; fresh-shell and actual-runtime test outcomes. |
| `reports/rollback.md` | Previous versions and links; backups; exact restore actions; affected services/state; performed rollback or isolated recovery test; remaining recovery limits. |

For each required capability, finish with one of: **reused and verified**, **installed and verified**, **replaced and verified**, or **blocked with a specific reason**. Do not mark a tool installed because an archive was copied, or mark a dependency complete because its source exists. Document remaining privileged operations or missing artifacts precisely and continue all independent work.

Complete `docs/AIRGAP_ACCEPTANCE.md` after this provisioning. Prove an actual model-backed task, independent review, cancellation, failure behavior and recovery. Keep host-tool results and workflow results distinct so the final report accurately states what works.
