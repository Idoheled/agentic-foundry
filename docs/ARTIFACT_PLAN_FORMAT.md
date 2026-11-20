# Sourcing-plan contract

This is the input contract for revision 2026-11-20-r2. Read [PRIVATE_REPOSITORIES_AND_HOST_TOOLS.md](PRIVATE_REPOSITORIES_AND_HOST_TOOLS.md) first. The receiving agent discovers and inspects internal supply, stages selected files, and supplies the evidence. The controller validates the recorded choices and identities; it does not determine whether a repository search or qualification report is truthful.

## Plan and validation

Copy config/artifact-plan.example.json to a private location, replace every placeholder, and set site.json's **artifactPlan** to its absolute path. File sources and qualification-report paths must remain available for subsequent configure operations. Set their directory permissions so only the intended operator can modify them. Do not put tokens or passwords in a source description, path, reference, report or URL.

Run:

~~~bash
./install.sh sources --config /private/path/site.json
~~~

This reads and hashes selected files and validates image decisions without fetching images or starting services. Install/configure record a private snapshot in state/artifact-plan.json and the resolved identities and execution paths in state/reports/artifact-selection.json. The latter participates in the model-smoke fingerprint; reconfiguration invalidates previous model evidence.

The template deliberately cannot pass validation as delivered. Never fill its evidence with invented searches or pre-mark a qualification report as passed.

## Top-level fields

| Field | Meaning |
| --- | --- |
| schemaVersion | Integer 1. |
| privateRepositoriesChecked | Nonempty list of factual, sanitized search/result descriptions. Include repository, artifact, time and compatibility/access finding, or refer to a detailed local report. |
| approvedInternalRegistries | Explicit host[:port] allowlist for internal image references. No scheme, credentials, path or public registry. An internal name is a site assertion that the agent must verify. |
| files | Six required selections: docker, compose, omp, herdr, opencode, ompAdapter. Optional dockerDaemon is used by the separate-daemon bootstrap. |
| images | Required paperclip and postgres selections. |

Every file/image selection has **source**, one of existing, internal or kit, and a nonempty factual **evidence** string. A kit choice also has **fallbackReason**, exactly unavailable, incompatible or insufficient. Record a separate reason for each fallback. An authentication failure is an access constraint, not evidence that a package is absent.

## Files and formats

Existing/internal files require an absolute **path**, lowercase 64-character **sha256**, and optionally **format**. The format defaults are:

| Name | Default format | Selected content |
| --- | --- | --- |
| docker | archive | Docker static distribution containing docker/docker. |
| compose | executable | Standalone Docker Compose executable. |
| omp | executable | Managed OMP build with the required offline adaptation. |
| herdr | executable | Herdr executable. |
| opencode | archive | Baseline archive containing opencode. |
| ompAdapter | archive | Complete patched adapter runtime and its dependency tree. |
| dockerDaemon | archive | Docker static archive for optional private-daemon bootstrap; defaults to the docker entry if omitted. |

Except for the qualified host-tool cases below, archive/executable hashes must match the tested identity listed in SHA256SUMS. A mirrored file may have a different filename. Copying a kit file elsewhere does not make it internally supplied; record its real source. Paths under this kit's payload cannot be relabelled as internal/existing.

OpenCode also supports **format: executable** for an already extracted existing/internal executable. Its digest must match the installed_binary digest in payload/manifests/worker-artifacts.json. The controller copies that verified executable into its managed runtime and leaves the original in place.

The docker entry supports **format: executable** for a suitable host Docker client. A separately installed daemon is reused; choosing a client does not install a daemon. If the optional private daemon is needed, supply a separate dockerDaemon archive entry and run:

~~~bash
./scripts/bootstrap-docker.sh --artifact-plan /private/path/artifact-plan.json
~~~

The optional helper installs its selected static runtime in its dedicated /opt directory; it does not replace another daemon. An existing directory without the helper's service is a conflict to inspect, not an invitation to overwrite it.

## Qualified host Docker and Compose

An existing/internal Docker executable, or a Compose executable whose bytes differ from the packaged baseline, requires **qualificationReport**, an absolute path to JSON. Pin the actual executable's sha256. The controller executes the selected host tool in place and checks that its hash has not changed on later use.

Start from config/host-tool-qualification.example.json. The report must have schemaVersion 1, artifact equal to docker or compose, sha256 equal to the selected executable, passed equal to true, and checks containing observed passing entries with nonempty evidence:

| Artifact | Required check names |
| --- | --- |
| docker | version-executes; local-engine-compatible; selected-socket-access |
| compose | version-executes; local-engine-compatible; compose-config-with-raw-env |

For Compose, parse a representative configuration containing the raw env_file format, host networking, resource settings and pull_policy used by this kit; then validate the actual generated configuration. The controller also runs Compose config --quiet during install/configure. For Docker, exercise the intended local Unix socket and the commands needed by this deployment without modifying another stack. Record the actual client/engine versions, target socket and observed results. A completed JSON field alone is not proof.

The chosen executable must have executable permissions, its shared libraries must be available on the host, and its path must be stable. Do not copy a package-owned binary out of its installation merely to avoid its associated dependencies or configuration.

## Images and identity

An internal image selection requires:

~~~json
{
  "source": "internal",
  "imageRef": "registry.internal.example/team/image@sha256:MANIFEST_DIGEST",
  "expectedConfigDigest": "sha256:CONFIG_DIGEST",
  "evidence": "Observed internal mirror, exact tested build and platform"
}
~~~

Substitute actual lowercase hexadecimal digests. The registry host must be in approvedInternalRegistries. The reference digest pins the image manifest or index; expectedConfigDigest must equal the tested platform-specific config digest from provenance/image-lock.json. These two digests are normally different.

The controller first inspects the selected reference locally. If absent and source is internal, it explicitly pulls only that reference from the declared internal registry, selecting linux/amd64. An identity mismatch or failed pull stops that component; it does not switch to kit bytes automatically. Investigate, then revise the plan with an evidenced choice if needed.

With source existing, use an already cached immutable internal reference, or use the tested local image ID itself as imageRef, in the form sha256:CONFIG_DIGEST. A local image-ID choice does not require a registry allowlist entry. It must already exist; the controller never pulls an existing selection. This permits reusing a suitable cached image without retagging an unrelated name.

For source kit, the controller imports the corresponding verified archive only if the managed image is not already available. A conflicting managed tag fails rather than being overwritten. Compose startup always uses pull_policy never and --pull never.

## Different internal application builds

Prefer an internally maintained build when it meets the required behavior. The supplied application/worker recipe is pinned to the tested baseline and will stop on different identities; it does not automatically approve other releases or silently fall back to the kit. Inspect and qualify the internal candidate, adjust the source/deployment recipe explicitly where appropriate, and produce new provenance and acceptance evidence. A different hash or newer version is not, by itself, proof of incompatibility.

The baseline includes a Paperclip API/commit check and explicit OMP offline adaptations. Do not remove those checks merely to get a green startup. Prove equivalent behavior, dependency closure, internal model routing, tool execution, cancellation, data/session compatibility and offline operation when changing a component.

## Scope of this mechanism

The sourcing plan covers the runtime artifacts that the controller stages. It does not install arbitrary OS packages or project libraries. The host-capability checklist and receiving-agent handoff separately require installing and testing those capabilities from approved internal sources, with correct paths, ownership, link handling and rollback.

The worker environment has an offline npm default. If a project needs a package available in an approved internal registry, use a narrowly scoped package-manager invocation configured solely for that registry (or a fully staged local install). Adjust the offline flag only for that authorized internal operation; preserve lockfile/hash checks and prevent public fallback or lifecycle-script downloads.
