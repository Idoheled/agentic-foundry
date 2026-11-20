# Instructions for agents working on this repository

Read `README.md`, `HANDOFF.md`, `docs/BOOTSTRAP_AND_LIFECYCLE.md` and the applicable phase document before changing a deployed machine. The user's actual site instructions and existing authorization take precedence over a generic template. Continue authorized reversible work autonomously; report concrete missing facts instead of inventing repository checks, routes or credentials.

## Discover before changing

Use `./setup.sh doctor` and inspect the actual operating system, architecture, libc, package ownership, command wrappers, working directory, named profiles, environment sources, project roots and custom brain/hook targets. Default directories are candidates, not proof of active configuration. Never invoke the newly selected OMP before taking the original preservation baseline; initialization can migrate a profile.

The included compiled payload is Linux x86-64/glibc. Debian 13 fallback packages are not universal Linux packages. A different target needs matching internal packages or a newly built and qualified payload. Do not claim that source availability alone closes binary dependencies.

## Private-first, native ownership and preservation

Reuse an adequate inspected existing tool, then prefer a suitable approved internal artifact, then use the included fallback with factual evidence. Preserve source and hash decisions. Do not access public registries during runtime setup.

Use native package management for package-owned executables and libraries. Install complete independent runtimes through their declared catalog/installer and update only inspected canonical paths. Do not place standalone replacements over an owned system Python, libc, OpenSSL or other OS file. Do not delete an old path merely because it looks unusual.

Preserve credentials, internal CA trust, model/protocol routes, existing hooks, skills, brain/memory files, project instructions, session/profile settings and supported launch arguments. Use the original `profile-preservation.py` baseline throughout an upgrade. Record only exact reviewed additions or evidenced native migrations. Never reset or weaken a baseline to obtain a passing result.

## Existing-machine sequence

Claude performs phase 1 only: upgrade and qualify OMP, write the bound handoff, then stop for the operator's manual switch. The qualified OMP performs phase 2. Do not replace the OMP runtime executing phase 2.

If `AGENTIC_SETUP_CONFIG` and `AGENTIC_SETUP_STATE` are present, read the referenced r5 configuration and lifecycle documentation. After the existing phase-2 native/core work, run the requested productivity-only scope and verification. Keep the full existing acceptance gates. Do not mistake `productivity_completed` for whole-stack completion.

## Evidence and finishing

Use `setup plan` before apply. Keep exact private state and input hashes on resume. If an input changes, review it and use a new setup transaction while retaining the original profile baseline. Read private failed-step diagnostics, fix the actual blocker, and resume through the guarded installer.

Version output and a reachable dashboard do not establish model/tool/session/project acceptance. Report only the scope actually verified. Enrollment leaves new task wakes disabled until the existing real acceptance gates pass. Retire old tool trees only through the ownership- and receipt-bound final cleanup step.

No new telemetry, monitoring or backup system is requested. Preserve the existing transaction rollback and configuration originals needed by this upgrade. Do not print secrets or commit site configuration, state, receipts, private logs or credentials. Do not push to a remote repository until the user provides and authorizes that repository integration.
