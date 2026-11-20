# r5: delivery-focused disconnected workspace

This revision adds practical coding capabilities and a Git-ready deployment path. It does not introduce a telemetry, monitoring or backup platform. Existing upgrade receipts, configuration originals and scoped rollback remain part of a correct native upgrade.

## Architecture and ownership

Paperclip remains the authority for projects, tasks, assignments, runs, concurrency and delivery state. OMP is the primary continuation/implementation client; Claude, Codex and OpenCode are installed and qualified for the routes actually supported inside the organization. Herdr remains an optional interactive terminal cockpit. Do not place another scheduler in charge of the same tasks.

Worktrunk improves interactive worktree creation/navigation and per-worktree command execution. Paperclip already creates isolated worktrees for its own tasks: let it own those directories. Use Worktrunk for interactive work and explicit agent lanes; never have both tools independently create, clean or rename the same checkout.

Zoekt and Universal Ctags provide local repository and symbol search. Language servers provide structured code understanding. RTK OSS reduces selected command output while retaining exit status. Inspect AI and the native-agent benchmark help choose effective model/client configurations using actual tasks and independent checks. Playwright supplies executable UI verification. Trivy adds an offline dependency/configuration check with a dated database. The Go SDK makes the supplied Zoekt source/vendor build reproducible offline.

No extra memory/brain service is installed. Existing brain configuration and project instructions remain authoritative. Serena and Beads are not activated by this release: they would add overlapping semantic/state ownership before the existing OMP/LSP/Paperclip workflow has demonstrated a gap.

## New capabilities

| Capability | Included implementation | Target integration |
| --- | --- | --- |
| Parallel interactive worktrees | Worktrunk 0.82.0 | Native `agentic-wt` / `agentic-git-wt`; canonical names only when unoccupied or explicitly reviewed |
| Repository and symbol search | Zoekt pinned source + Universal Ctags | Native index/search tools; optional loopback search service; private indexes outside immutable runtimes |
| Semantic code navigation | Pyright, TypeScript, Bash, YAML, JSON, HTML, CSS services | OMP can discover compatible server commands from its project root; other clients need their supported LSP configuration |
| Compact terminal results | RTK 1.2.1 OSS | Explicit command use; existing hooks are preserved, with no global automatic rewrite |
| Repeated agent comparison | Inspect AI 0.3.291 + `agentic-bench` | Exact internal route adapters, isolated Git worktrees, external acceptance checks, elapsed time and result evidence |
| Browser verification | Playwright 1.65.1 + signed Debian Chromium 156 | Native Debian 13 browser/dependency plan and mandatory real local UI test |
| Offline dependency checks | Trivy 0.76.2 + general DB/checks | Native command, private cache preferred; no registry fallback for image scans |
| Native source development | Go 1.27.4 plus existing Rust/Node/Python/C/C++ tools | Existing private module configuration preserved; absent Go settings default to offline/local toolchain behavior |

Language versions are pinned as a tested group. TypeScript 7.0.2 failed initialization with the selected language server; 6.0.3 passed with typescript-language-server 6.1.0. Do not upgrade one member blindly.

## Fresh-machine installation

Use `config/site-minimal.example.json` as the small site declaration. The agent fills actual operator paths, private supply findings, model protocol/endpoint/model identifiers, the existing credential environment variable name, and any package-manager plan. The file contains no credential values. Then the deployment is one command:

```bash
./setup.sh --config /private/site.json --state /private/states/setup-r5
```

`./setup.sh doctor` is a non-installing inventory. `./setup.sh plan --config ... --state ...` compiles and validates the explicit stages. Repeating apply with unchanged inputs verifies completed receipts and resumes the remaining requested work. A changed selected input is a new reviewed transaction, not permission to silently overwrite old state.

There is no universal zero-configuration model route: setup needs the organization's actual endpoint, protocol, credentials source, CA trust and package supply. OMP/OpenCode core routes are rendered from the selected site. Fresh native Claude/Codex routes require the protocol each client supports; installation does not prove those routes exist. Existing working routes must be preserved.

For a machine without Python, `scripts/python.sh` can use the supplied standalone controller after factual private-source inspection. Set `AGENTIC_PYTHON` to a qualified private/installed interpreter when available; otherwise set `AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON` to the real finding. Bash, tar, coreutils, normal Linux primitives and existing installation authority are bootstrap prerequisites. No kernel, init system, model weights or arbitrary project dependencies are synthesized by this kit.

## Existing-machine upgrade

Start from the existing working Claude:

```bash
./setup.sh agent --config /private/site.json --state /private/states/setup-r5
```

Use `bootstrapMode: existing`. Claude performs OMP-only phase 1 and writes the checked handoff. It stops for the operator's manual switch. The qualified OMP completes phase 2, then applies the selected r5 productivity scope using the exact plans and existing preservation baseline. The OMP runtime executing phase 2 is never upgraded under itself.

`docs/PHASE2_OMP.md` describes the exported `AGENTIC_SETUP_CONFIG` and `AGENTIC_SETUP_STATE` continuation. If using minimal configuration for an existing machine, supply explicitly inspected profile paths, including named profiles, wrapper/environment-selected locations and external brain files. Default home-directory guesses are not a complete preservation inventory.

## Private supply and native placement

The compiler searches declared readable private mirror roots and an optional private supply index. Exact qualified mirror artifacts take precedence over fallback. An index can select a newer/different private artifact with its factual qualification and recipe. A same-name private candidate with a differing hash blocks for inspection; it is not silently dismissed as unavailable.

Exact already-installed command bytes and dependency layouts may be selected without executing a new agent during discovery. Real runtime verification occurs only during protected apply. Container staging requires a complete dependency archive; an adequate bare host executable alone cannot establish that closure. In that case the compiler prefers a private complete archive, then an authorized kit fallback with an explicit insufficiency reason.

OS-owned files are upgraded through the native package manager. Standalone trees use `/opt/agentic-stack/tools/<tool>/<version>-<artifact-hash>/` and inspected `/usr/local/bin` entry points; user mode uses the corresponding `.local` directories. Runtime libraries remain with their proper interpreter/tool layout or native package owner. Do not copy only a Python executable to `/usr/bin`, flatten all libraries into one directory, or unlink a package-owned dependency.

The default minimal recipe creates canonical command names only when absent. Replacing an existing canonical path or normalizing an unusual installation uses the advanced inspected host plan, package ownership checks and consumer verification. The existing two-phase cleanup retires only exact proven obsolete unmanaged files; no recursive removal of unknown runtime directories is allowed.

## Worker exposure and acceptance

When enabled by the site, the productivity installer copies complete qualified Worktrunk, RTK, Zoekt/Ctags and language-service trees into Paperclip's existing read-only runtime mount. It writes tracked wrappers, preserves untracked/edited commands and executes the actual container probes. A host-only version check does not count as worker exposure. Runtime report and receipt hashes remain bound across repeated verification.

The browser and evaluation profiles remain native host capabilities. This release does not pretend that Debian browser libraries are already present inside the pinned Paperclip image. Use a native worker lane or a separately qualified private container image for browser-driven agent tasks.

The generated productivity plan runs Inspect's offline functional test, the native benchmark self-test and the real browser UI gate for selected components. A failed browser gate leaves installation evidence but blocks capability acceptance. The real browser test navigates a local HTTP page, fills a form, clicks, checks the resulting DOM, and retains a screenshot and trace in private target state. It keeps Chromium sandboxing enabled.

Codex trusted-hook activation is explicit. The agent reviews the included native hook code and supplies `profiles.activateReviewedCodexHooks: true` together with its exact `reviewedAssetManifestSha256`. The user's installation authorization allows that code review and configuration work; another generic permission prompt is not required. Without that explicit review binding, setup installs the skill assets but does not invent trusted-hook approval.

## Build qualification and limits

The release retains real functional evidence for worktree operations, Git/symbol/web search, seven LSP protocol flows, offline npm replay, RTK failure-status propagation, Trivy offline fixture scans, Inspect scoring/tokenizers/sandbox-tools, and six native benchmark subprocess tests. Installer/controller regression tests use isolated fixtures; their simulated model and Docker responses are not target-environment acceptance.

Chromium bytes, native packages, library resolution, executable version and runtime relocation were checked. Real browser interaction did not pass in this build environment: the executor denied the browser's required Unix socket operation. The official Playwright browser CDN was also unavailable here, so the included browser is the separately signed Debian Chromium distribution, with an explicit target-machine pairing test. No sandbox bypass is part of setup.

The compiled profile is Linux x86-64/glibc; the default native fallback and the qualified evaluation/browser profile are Debian 13. Internal APT plans can supply appropriate Debian/Ubuntu prerequisites, but a different evaluation/browser build still needs a matching qualified catalog. ARM64, musl, other distributions and their native package graphs need separate payload profiles. Detection is dynamic; binary compatibility is not guessed.

The kit contains actual selected runtime dependency closures, source snapshots, docs, licenses, original release assets and several verified source-build closures. It does not contain every upstream project's entire build/test/website graph, all Git history for every new tool, every Chromium/OS-library source tree, the optional Trivy Java class index, arbitrary project packages, or model weights. Claude Code's public repository is not the proprietary client's complete implementation source. Per-component rebuild limits are recorded in the included source manifests.

The Trivy general database snapshot is dated 2026-11-20. Continue using the organization's private update process as it ages. No new service for monitoring, telemetry or backups is installed or required for r5 completion.

## Git deployment contract

Agentic Foundry v0.1.0 versions the setup code, plans/schemas, docs, tests, package identities and payload lock. Content-addressed objects under `offline/` use Git LFS, with reconstruction recorded in `offline/manifest.json`. `deploy.sh` hydrates those local objects before setup; see [Offline payloads](PAYLOADS.md). A source checkout can also hydrate from a local private mirror or a verified tar:

```bash
python3 scripts/payload.py hydrate --from-dir /mnt/private/extracted-release
python3 scripts/payload.py verify
./setup.sh --config /private/site.json --state /private/states/setup-r5
```

For a tar source, use `hydrate --archive /mnt/agentic-workspace-r5.tar.gz --sha256 EXACT_RELEASE_HASH`. Existing differing payload files are preserved and block hydration. No public downloader is present. The full single tar already includes the payload; it needs no hydration step.

The repository release tag versions the integration source; `2026-11-20-r5` identifies this payload and its build evidence. Keep publication credentials, private site plans and runtime state outside the repository. Source CI and payload integrity checks do not replace receiving-host acceptance: run the actual model, worker and project gates before enabling production dispatch.
