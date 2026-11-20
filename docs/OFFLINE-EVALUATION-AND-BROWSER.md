# Offline evaluations and browser work

This profile adds two delivery capabilities: a controlled comparison of coding agents against independent checks, and native browser automation for project acceptance. It does not add monitoring, backup services, or a telemetry collector.

## Included software and concrete limits

| Capability | Included fallback | Native command | Qualification |
| --- | --- | --- | --- |
| Evaluation framework | Inspect AI 0.3.291, standalone CPython 3.12.16, exact 86-package wheel closure, OpenAI 3.57.0 and Anthropic 2.12.0 SDKs | `agentic-inspect` | CLI, package consistency, correct and incorrect mock outputs, all bundled tokenizers verified |
| Native coding comparison | `agentic-bench` source and independent fixture tests | `agentic-bench plan` / `agentic-bench run` | Real candidate/check subprocesses, correct/incorrect changes, checker tampering, timeouts and preservation tested |
| Browser automation | Playwright / @playwright/test / playwright-core 1.65.1 | `agentic-playwright` | CLI and exact npm integrity verified |
| Browser engine | Debian Chromium 156.0.8078.79-1~deb13u1, exact signed native packages | explicit `executablePath` | Binary version and shared-library resolution verified on Debian 13; real UI acceptance must pass on target |
| Browser native dependencies | 215 Debian 13 amd64 `.deb` artifacts, including browser dependencies and Latin/emoji fonts | native package manager through kit plan | Complete download-only dependency resolution from an empty dpkg status, signed metadata and per-package hashes verified |

The included Chromium is an explicitly selected Debian browser. Playwright's own default revision is Chromium 159.0.8154.6 / revision 1255; that distribution is not in this kit because its official CDN returned an environment policy 403 during acquisition. The Debian pairing has not been certified by Playwright upstream. Target acceptance is mandatory before enabling browser jobs.

The build environment also blocks the Unix sockets Chromium requires. A real `chromiumSandbox: true` browser smoke test was attempted and stopped before navigation with `socket() failed: Operation not permitted`. That failure is retained as qualification evidence. It is not a successful browser interaction test. The supplied target test fails closed; it does not disable Chromium's sandbox to obtain a pass.

Binary fallback qualification is **GNU/Linux x86_64, Debian 13** for the browser profile. Inspect's selected wheels include a glibc 2.34 wheel and therefore require glibc 2.34 or newer on x86_64; the supplied standalone Python must also pass the kit's platform checks. Neither a complete ARM profile nor a musl profile is claimed. The Inspect wheel happens to include an arm64 sandbox-tools asset; that does not make its complete Python runtime arm64-capable.

## Private repositories and native placement

Use the parent kit's private-first resolution and approved native package plan. An existing compatible internal Inspect, Node, Playwright or Chromium may satisfy the capability after inspection and real qualification. Record the selected provenance and the exact executable used. Use the retained artifacts when the internal selection is absent or insufficient. Do not overwrite an existing command merely because this kit has a different version.

The versioned application runtimes belong in the parent installer's managed application prefix, normally `/opt/agentic-workspace/<tool>/<version>/`. Public managed launchers belong in `/usr/local/bin`. Debian packages own their standard `/usr/bin`, `/usr/lib`, `/usr/share/fonts` and package-manager paths. Never manually move a package-managed library, overwrite `/usr/bin/python3`, or delete an executable that another package or agent may still use. An application-specific Python runtime is intentionally private to Inspect; the launcher points to it directly, so changing this tool does not change the operating system's Python ABI.

The browser runtime contains the Chromium/common files extracted from the official Debian packages so the profile can address the exact engine by an explicit path. Its shared libraries and fonts are installed or reused natively by the Debian package phase. The profile does not publish a `chromium` alias or modify desktop/browser defaults. The sandbox helper is supplied as a native Debian package; let the package manager establish its ownership and modes.

The direct native package requirements are `chromium`, `chromium-common`, `chromium-sandbox`, `fonts-liberation` and `fonts-noto-color-emoji`. The fallback browser package version is `156.0.8078.79-1~deb13u1`. Their transitive dependencies are listed in `browser-native-packages.json`; the complete fallback closure is in `browser-debian13-amd64/`. Repositories and InRelease signatures are retained in `browser-debian-metadata/`. Do not feed Debian 13 packages into another distribution. Build and qualify an appropriate internal package profile there.

Node 20 or newer is required. The common kit provides a qualified Node runtime. For an approved alternate path, set `AGENTIC_NODE=/absolute/path/to/node` for this process. `agentic-playwright` resolves its adjacent npm installation and does not use `npx`; no runtime package download is needed.

The wrappers set `PYTHONDONTWRITEBYTECODE=1`; the installed prefix remains immutable under probes. All seven tiktoken vocabularies are preloaded in the Inspect prefix. They are read as immutable runtime data. Operational caches, logs and browser profiles use separate writable state, never the installed prefix. No hooks, brain configuration, API credentials or model-route files are edited by these launchers.

## Mandatory post-install qualification

First run the normal kit host checks. Then run these with new absolute output directories owned by the operator:

```sh
agentic-inspect --version
agentic-inspect-smoke --state /absolute/operator-state/inspect-qualification-001
agentic-bench-selftest
agentic-playwright --version
agentic-browser-smoke --state /absolute/operator-state/browser-qualification-001
```

The Inspect smoke test contacts no model. It blocks IPv4/IPv6 `socket.connect` inside its process, verifies sandbox-tools hashes against the upstream checksum list, loads all tokenizers and evaluates fixed correct and incorrect responses. It checks the result scores, not just process exit.

The browser smoke test launches the actual selected browser with Chromium sandboxing enabled, serves a fixed local HTTP page, fills a labeled input, clicks a button, checks the changed DOM, records a PNG and Playwright trace, and writes `qualification.json`. Requests from the fixture to other origins are blocked. A failed launch, missing library, incompatible protocol, wrong result or unexpected request means failed acceptance. Its `--browser /absolute/approved/chromium` argument can qualify an internal browser instead. `AGENTIC_CHROMIUM_EXECUTABLE` is also honored by both the project config and the smoke test.

Run as an ordinary operator under the site's supported browser sandbox policy. If the site's kernel or executor forbids required browser sockets/namespaces, the agent must report the actual blocker and leave the browser capability unqualified. Do not report success from `--version`, disable isolation, remove endpoint policy, or rewrite machine security settings to force a successful result. Select an already approved browser execution environment through the site's process.

## Comparing OMP, OpenCode, Claude, Codex and custom agents

`agentic-bench` accepts explicit command arrays. It does not guess an installed CLI's current flags, rewrite its native configuration, or translate one provider's route into another. Use the already qualified CLI invocation from the site's installation and preserve its existing hooks, skills, brain and disconnected model routes.

Create a fixed test repository snapshot and an external acceptance program. Choose tasks that represent the work you actually deliver: a small bug fix, an API change with tests, a frontend correction verified in the real browser, or a cross-file refactor with type checks. Use the same full commit and prompt for each candidate, the same independent checks, bounded time, and more than one representative task. A single toy task does not establish which agent is best.

The included `benchmark-plan.example.json` is a template. Replace its paths and commit hash. An agent may read `{prompt_file}`, operate in the provided working directory, and write supporting artifacts to `{evidence_dir}`. Commands are literal argv arrays: the runner does not interpolate shell syntax. If an agent needs prompt text on a command-line flag, use a small site-owned adapter that reads the file and invokes the already qualified CLI. Keep tokens out of argv; inherited site credential mechanisms remain in effect.

```sh
agentic-bench plan --plan /absolute/controlled/benchmark-plan.json
agentic-bench run --plan /absolute/controlled/benchmark-plan.json \
  --state /absolute/operator-state/coding-benchmarks
```

`plan` performs read-only validation and reports run counts. `run` uses one detached Git worktree per candidate/task/repetition. It does not change the original checkout or commit. Git hook execution is disabled only for the runner's worktree-management commands; global and repository hook settings remain unchanged. The candidate agent's own site configuration and commands still operate normally within the chosen execution profile.

Every candidate run receives the same immutable prompt bytes and pinned commit. Runs are sequential to avoid accidentally comparing different inference contention. A candidate exit code of zero is insufficient: independent acceptance commands must also succeed. The runner records timeouts, command file identities, fixed baseline, resulting diff, untracked-file inventory, return codes, private stdout/stderr and a summary. Worktrees and evidence remain available for inspection; they are not automatically merged or deleted.

Acceptance programs must live outside the candidate checkout and be protected from candidate write access by the site's execution boundary. The runner binds their hashes before the suite and checks for changes before and after execution. An agent that edits an acceptance file is recorded as a failed result. Keep checker inputs and supporting fixture files in the same protected area, and pass their absolute paths in argv so their identities are bound too. Checks that import additional files should use a protected immutable checker tree. The supplied test suite exercises an attempted checker modification.

**Git worktrees are not an operating-system sandbox.** A process with the same uid can still access other readable or writable files, and a malicious process could attempt to change and restore a checker between observations. The runner does not claim to prevent that. Use the kit's approved task execution profile to give the candidate only its project and required internal endpoints, with acceptance programs mounted read-only and executed separately by the supervisor. The `isolationAcknowledgment` field makes this boundary explicit. It is not a permission bypass.

Record `routingEvidence` as a factual, sanitized description of the selected internal route qualification. The runner does not infer which endpoint a CLI actually used. Enforce allowed internal endpoints with the site's existing network controls and verify a real small model request during the site's route qualification. These offline tests provide no evidence of an untested internal model's quality or compatibility.

If a task needs model-based judging, configure that judge separately as an explicitly approved internal model; the shipped coding runner uses deterministic acceptance commands and needs no judge credentials. The Inspect SDK profile provides OpenAI-compatible and Anthropic-compatible clients for supported internal routes. Other provider extras, external datasets, container images and model weights are not implicitly downloaded or bundled.

## Real project browser tests

Copy `playwright.offline.config.cjs` into the project, or merge its explicit `launchOptions` into the existing project's config. Preserve existing project scripts and assertions. Set `testDir` for the project and run through the managed command:

```sh
agentic-playwright test --config /absolute/project/playwright.offline.config.cjs
```

The config imports the bundled test library from `AGENTIC_PLAYWRIGHT_ROOT`. For new test files that are outside this runtime, import the same exact library via `require(require('node:path').join(process.env.AGENTIC_PLAYWRIGHT_ROOT, 'node_modules/@playwright/test'))`, or use the project's already qualified matching internal dependency. Do not assume global Node module resolution will discover this private runtime automatically.

Browser installation commands are rejected by the managed offline wrapper. Browser packages, libraries and fonts are selected by the native package plan; Playwright-managed downloads are not an offline fallback. Use explicit executable paths in every project config. The wrapper's exported variable does not automatically override a project that omits `launchOptions.executablePath`.

## Sources, packages and rebuilding

The kit retains exact Inspect 0.3.291 source distribution, the complete tracked Inspect repository snapshot at `c3b14699e2748e41fc0af0fffd48ed1a4f9acff1`, and the complete tracked Playwright v1.65.1 repository at `bbd948344ea9a60bf1e6f125c02ca99b2b51593b`. Tracked snapshots contain upstream documentation and licenses; they do not contain Git history. The Inspect repository snapshot was captured from upstream main and is separately identified from the exact published source distribution. Do not assume they are the same revision.

All 86 selected Python wheels are pinned and verified against PyPI's published SHA-256 values. Their matching published source distributions are retained where upstream provides them. `python-provenance.json` records each available source archive and any limitation. `inspect-requirements.lock` contains the exact hash-locked wheel closure. The installed runtime and its wheelhouse are sufficient for the selected profile without building native extensions on the target. Full compiler/build-system closure for rebuilding every third-party source package is a separate task.

The three exact npm package tarballs, package-lock, upstream SHA-512 integrity and SHA-256 transfer hashes are retained. Playwright is installed without postinstall downloads. The native Chromium packages include Debian's licenses and copyright files. Chromium's entire upstream engine source tree and the source trees of all Debian libraries are not in this kit; their Debian source identities are recorded. Do not advertise this as an offline Chromium or operating-system source-build distribution.

`source-provenance.json`, `python-provenance.json`, `playwright-npm-provenance.json`, tokenizer provenance and the signed Debian records supply the retained provenance. A manifest hash is an integrity record, not a substitute for the site's approval of internal repositories or signing keys.

The build-only scripts are source for reproducing acquisition in an approved connected environment. They are not invoked during disconnected installation. Keep the full kit on the disconnected machine; do not delete package archives, accepted source snapshots or the original machine's working tools as a side effect of a successful smoke test.
