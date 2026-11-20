#!/usr/bin/env python3
"""Compile a small private site declaration into explicit, inspectable installer plans.

This compiler never installs software or contacts a repository. It checks declared
mirror directories/indexes and existing exact qualified binaries. Private indexes
can select different qualified versions using the ordinary host-plan contract.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"[0-9a-f]{64}\Z")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fact(value, label):
    require(isinstance(value, str) and value.strip() and "REPLACE_" not in value, label + " needs an actual inspection finding")
    return value


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def absolute(value, label):
    require(isinstance(value, str) and value, label + " is required")
    path = Path(value).expanduser()
    require(path.is_absolute() and ".." not in path.parts, label + " must be an absolute normalized path")
    return path


def os_info():
    values = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    return {"id": values.get("ID", "unknown"), "versionID": values.get("VERSION_ID", "unknown"), "architecture": platform.machine()}


def private_supply(config, kit):
    supply = config.get("privateSupply", {})
    evidence = fact(supply.get("inspectionEvidence"), "privateSupply.inspectionEvidence")
    roots = [absolute(value, "privateSupply.roots") for value in supply.get("roots", [])]
    index_path = absolute(supply["index"], "privateSupply.index") if supply.get("index") else None
    require(roots or index_path or supply.get("unavailabilityEvidence"),
            "Declare private mirror roots/index, or factual unavailabilityEvidence after checking private repositories")
    checks = [evidence]
    if supply.get("unavailabilityEvidence"):
        checks.append(fact(supply["unavailabilityEvidence"], "privateSupply.unavailabilityEvidence"))
    candidates = {}
    for root in roots:
        require(root.is_dir() and not root.resolve().is_relative_to(kit), "Private mirror must be a readable directory outside this kit: " + str(root))
        count = 0
        # Never follow symlink directories; indexed files must themselves remain inside the declared root.
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()]
            for name in files:
                path = Path(directory) / name
                if path.is_file() and path.resolve().is_relative_to(root.resolve()):
                    candidates.setdefault(name, []).append(path)
                    count += 1
        checks.append("Inspected private mirror " + str(root) + ": " + str(count) + " readable files (no network fetch)")
    index = read(index_path) if index_path else {"schemaVersion": 1}
    require(index.get("schemaVersion") == 1, "Private supply index schemaVersion must be 1")
    if index_path:
        require(not index_path.resolve().is_relative_to(kit), "Private supply index must be outside the release kit")
        checks.append("Read private supply index " + str(index_path) + "; sha256=" + sha(index_path))
    return supply, checks, index, candidates


def mirrored(artifact, candidates):
    matching_names = candidates.get(Path(artifact["path"]).name, [])
    for path in matching_names:
        if sha(path) == artifact["sha256"]:
            return {"source": "internal", "path": str(path.resolve()), "sha256": artifact["sha256"],
                    "format": artifact["format"], "stripComponents": artifact.get("stripComponents", 0),
                    "evidence": "Private mirror file matches the pinned qualified artifact SHA-256"}
    require(not matching_names, "A private candidate differs from the pinned artifact: " + Path(artifact["path"]).name + "; qualify it in the private index before choosing a replacement or fallback")
    return None


def existing_exact(tool, identities):
    if not tool.get("commands") or not identities:
        return None
    selected = {}
    for command, spec in tool["commands"].items():
        location = shutil.which(command)
        expected = identities.get("commands", {}).get(command)
        if not location or not expected or sha(location) != expected:
            return None
        selected[command] = {"path": str(Path(location).absolute()), "sha256": expected}
    # The complete native dependency layout must be available for composite tools.
    roots = []
    for command, spec in tool["commands"].items():
        path = Path(selected[command]["path"]).resolve()
        rel = Path(spec if isinstance(spec, str) else spec["path"])
        candidate = path
        for unused in rel.parts:
            candidate = candidate.parent
        roots.append(candidate)
    if tool.get("requiredPaths"):
        if len(set(roots)) != 1 or not all((roots[0] / needed).exists() for needed in tool["requiredPaths"]):
            return None
    return {"source": "existing", "adequate": True, "executables": selected,
            "pathEntries": [str(root / entry) for root in sorted(set(roots)) for entry in tool.get("pathEntries", [])],
            "evidence": "Discovered exact pinned command bytes and required runtime paths; execution checks deferred until protected apply"}


def select_tools(catalog, names, supply, index, candidates, identities, mode, config):
    result = {}
    bin_dir = Path("/usr/local/bin") if mode == "system" else Path.home() / ".local/bin"
    for name in names:
        require(name in catalog["tools"], "Unknown selected tool: " + name)
        tool = catalog["tools"][name]
        explicit = index.get("tools", {}).get(name)
        if explicit:
            choice = dict(explicit)
            require(choice.get("source") in ("internal", "existing"), "Private index tools must select internal or qualified existing sources")
            fact(choice.get("evidence"), "private index tool " + name)
        else:
            choice = existing_exact(tool, identities.get(name, {})) if config.get("reuseExisting", True) else None
            choice = choice or mirrored(tool["artifact"], candidates)
            if not choice:
                require(supply.get("allowKitFallback") is True, "No sufficient existing/private selection for " + name + "; kit fallback is disabled")
                choice = {"source": "kit", "fallbackReason": "unavailable",
                          "evidence": "No exact qualified artifact found in the declared private supply or existing command layout; " + supply["inspectionEvidence"]}
        # Missing names may be added; replacements and nonstandard path normalization need a reviewed advanced plan.
        if config.get("canonicalCommands", "when-missing") == "when-missing" and "canonicalLinks" not in choice:
            choice["canonicalLinks"] = [{"path": str(bin_dir / command), "command": command, "expected": {"kind": "missing"}}
                                        for command in tool.get("commands", {})
                                        if not shutil.which(command) and not os.path.lexists(bin_dir / command)]
        result[name] = choice
    return result


def tool_location(name, tool, choice, base, identities, command=None):
    if choice.get("source") == "existing" and not choice.get("normalizePath", False):
        require(command is not None, "Cannot use a bare existing executable as a complete asset tree")
        selected = choice.get("executables", {}).get(command, choice)
        return absolute(selected.get("path"), name + " executable"), selected.get("sha256")
    version = str(choice.get("version", tool["version"]))
    digest = choice.get("sha256", tool["artifact"]["sha256"]) if choice["source"] != "kit" else tool["artifact"]["sha256"]
    require(SHA.fullmatch(digest), "Invalid selected artifact digest for " + name)
    root = base / "tools" / name / (version + "-" + digest[:12])
    metadata = identities.get(name, {}) if digest == tool["artifact"]["sha256"] else choice.get("fileIdentities", {})
    if command:
        spec = tool["commands"][command]
        value = metadata.get("commands", {}).get(command)
        require(value and SHA.fullmatch(value), "Selected " + name + " needs fileIdentities.commands." + command + " for profile binding")
        return root / (spec if isinstance(spec, str) else spec["path"]), value
    return root, metadata


def compile_config(path, output, kit):
    config = read(path)
    require(config.get("schemaVersion") == 1 and config.get("schemaKind") == "minimal", "Expected schemaKind minimal, schemaVersion1")
    evidence = fact(config.get("evidence"), "evidence")
    mode = config.get("mode", "system")
    require(mode in ("system", "user"), "mode must be system or user")
    require(config.get("bootstrapMode") in ("fresh", "existing"), "Choose bootstrapMode fresh or existing")
    require(config.get("canonicalCommands", "when-missing") in ("when-missing", "none"), "Use an advanced host plan for reviewed canonical replacements")
    state = absolute(config.get("stateRoot"), "stateRoot")
    actual = os_info()
    require(platform.system() == "Linux" and actual["architecture"] in ("x86_64", "amd64"), "Bundled runtime profile is Linux x86_64; build a matching payload for other architectures")
    supply, checks, index, candidates = private_supply(config, kit)
    catalog = read(kit / "config/host-catalog.json")
    identities = read(kit / "provenance/r5/host-file-identities.json")
    selected = config.get("tools", list(catalog["tools"]))
    require(isinstance(selected, list) and selected and len(set(selected)) == len(selected), "tools must be a nonempty unique list")
    host_choices = select_tools(catalog, selected, supply, index, candidates, identities, mode, config)
    generated = {"host-plan.json": {"schemaVersion": 1, "privateRepositoriesChecked": checks, "tools": host_choices}}
    core_enabled = config.get("core", {}).get("enabled", True)
    profiles_enabled = config.get("profiles", {}).get("enabled", True)
    base = Path("/opt/agentic-stack") if mode == "system" else Path.home() / ".local/share/agentic-stack"
    install = {"schemaVersion": 1, "evidence": evidence, "coordinatorState": str(state / "installation"),
               "host": {"mode": mode, "plan": str(output / "host-plan.json"), "state": str(state / "host"), "catalog": str(kit / "config/host-catalog.json")},
               "native": {"enabled": False}, "core": {"enabled": core_enabled}, "clients": {"enabled": core_enabled},
               "profiles": {"enabled": profiles_enabled}, "modelSmoke": core_enabled, "retireOldTools": False, "stepTimeoutSeconds": 21600}
    native = config.get("nativePackages", {})
    native_plan = native.get("plan") or index.get("nativePlan")
    if native.get("enabled", True):
        if native_plan:
            native_path = absolute(native_plan, "nativePackages.plan")
            require(native_path.is_file(), "Native repository plan is missing")
        else:
            require(mode == "system", "Native OS package installation requires system mode or an explicitly disabled already-provisioned nativePackages profile")
            require(actual["id"] == "debian" and actual["versionID"].split(".")[0] == "13", "This OS needs an internal nativePackages.plan; bundled DEBs qualify only for Debian13")
            require(supply.get("allowKitFallback") is True, "No private native repository plan and fallback is disabled")
            native_evidence = fact(native.get("privateRepositoryFinding"), "nativePackages.privateRepositoryFinding")
            recovery = fact(native.get("recoveryEvidence"), "nativePackages.recoveryEvidence (existing host recovery procedure)")
            packages = read(kit / "config/native-packages.example.json")["packages"]
            product_settings = config.get("productivity", {})
            if product_settings.get("enabled", True) and "playwright" in product_settings.get("tools", ["playwright"]):
                browser_packages = read(kit / "provenance/r5/browser-native-packages.json")["directPackages"]
                packages = list(dict.fromkeys([*packages, *browser_packages]))
            generated["native-plan.json"] = {"schemaVersion": 1, "expectedOS": actual, "privateRepositoriesChecked": checks + [native_evidence],
                "source": "kit", "fallbackReason": "unavailable", "evidence": native_evidence, "packages": packages, "hostRecoveryEvidence": recovery}
            native_path = output / "native-plan.json"
        install["native"] = {"enabled": True, "plan": str(native_path), "state": str(state / "native")}
    else:
        fact(native.get("evidence"), "nativePackages.evidence for reusing already provisioned OS capabilities")
    setup = {"schemaVersion": 1, "schemaKind": "setup", "evidence": evidence, "bootstrapMode": config["bootstrapMode"],
             "target": {"profile": "debian13-x86_64" if actual["id"] == "debian" and actual["versionID"].split(".")[0] == "13" else "apt-x86_64-internal" if actual["id"] in ("debian", "ubuntu") else "linux-x86_64-internal", "minimumGlibc": "2.28"},
             "installation": str(output / "installation.json"), "productivity": {"enabled": False},
             "enrollment": {"enabled": config.get("enrollProjects", True) and core_enabled}}
    for name in ("preservation", "agent"):
        if name in config:
            setup[name] = config[name]
    if core_enabled:
        import artifact_policy
        model = dict(config.get("model", {}))
        for name in ("baseUrl", "id", "apiKeyEnv"):
            fact(model.get(name), "model." + name)
        url = urllib.parse.urlparse(model["baseUrl"])
        require(url.scheme in ("http", "https") and url.hostname and not url.username and not url.password and not url.query,
                "Model baseUrl must name the internal endpoint without credentials/query strings")
        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", model["apiKeyEnv"]), "model.apiKeyEnv must be an environment variable name")
        model.setdefault("api", "openai-completions")
        require(model["api"] in ("openai-completions", "openai-responses", "anthropic-messages"), "Unsupported model API")
        model.setdefault("providerId", "internal"); model.setdefault("smallModelId", model["id"])
        model.setdefault("contextWindow", 65536); model.setdefault("maxTokens", 8192)
        sums = dict(line.split("  ", 1)[::-1] for line in (kit / "SHA256SUMS").read_text().splitlines())
        artifact_plan = {"schemaVersion": 1, "privateRepositoriesChecked": checks, "approvedInternalRegistries": index.get("approvedInternalRegistries", []), "files": {}, "images": {}}
        for name in artifact_policy.REQUIRED_FILES:
            relative, fmt = artifact_policy.FILES[name]
            choice = index.get("files", {}).get(name)
            if choice:
                require(choice.get("source") in ("existing", "internal"), "Private file index must select existing/internal")
            else:
                choice = mirrored({"path": relative, "sha256": sums[relative], "format": fmt}, candidates)
            if not choice:
                require(supply.get("allowKitFallback") is True, "No private core file selection: " + name)
                choice = {"source": "kit", "fallbackReason": "unavailable", "evidence": "No qualified match in inspected private core file supply; " + supply["inspectionEvidence"]}
            artifact_plan["files"][name] = choice
        daemon_choice = index.get("files", {}).get("dockerDaemon")
        if not daemon_choice:
            relative, fmt = artifact_policy.FILES["dockerDaemon"]
            daemon_choice = mirrored({"path": relative, "sha256": sums[relative], "format": fmt}, candidates)
        if not daemon_choice:
            docker_choice = artifact_plan["files"]["docker"]
            if docker_choice.get("format", "archive") == "archive":
                daemon_choice = dict(docker_choice)
            else:
                require(supply.get("allowKitFallback") is True, "Private daemon bootstrap needs a complete Docker archive")
                daemon_choice = {"source": "kit", "fallbackReason": "insufficient", "evidence": "Selected Docker executable does not provide a daemon runtime archive; " + supply["inspectionEvidence"]}
        artifact_plan["files"]["dockerDaemon"] = daemon_choice
        lock = read(kit / "provenance/image-lock.json")
        for name in artifact_policy.IMAGE_TAGS:
            choice = index.get("images", {}).get(name)
            if choice:
                require(choice.get("source") in ("existing", "internal"), "Private image index must select existing/internal")
            else:
                require(supply.get("allowKitFallback") is True, "No private image selection: " + name)
                image_evidence = fact(supply.get("imageRepositoryFinding"), "privateSupply.imageRepositoryFinding")
                choice = {"source": "kit", "fallbackReason": "unavailable", "evidence": image_evidence}
            artifact_plan["images"][name] = choice
        generated["artifact-plan.json"] = artifact_plan
        core = read(kit / "config/site.example.json")
        core.update(company=config.get("company", "Internal Agent Operations"), model=model, projects=config.get("projects", []), artifactPlan=str(output / "artifact-plan.json"))
        for name in ("paperclipPort", "postgresPort", "resources", "caCertPath"):
            if name in config:
                core[name] = config[name]
        generated["core-site.json"] = core
        core_state = state / "core"
        install["core"].update(config=str(output / "core-site.json"), state=str(core_state))
        require({"codex", "claude", "python", "native-profiles", "node"}.issubset(selected), "Core client staging needs codex, claude, python, native-profiles and node tools")
        install["clients"]["names"] = ["codex", "claude", "python", "native-profiles", "node"]
        for name in install["clients"]["names"]:
            if host_choices[name]["source"] == "existing" and not host_choices[name].get("normalizePath"):
                require(name not in index.get("tools", {}), "Core staging needs a complete " + name + " archive; the explicit private selection is a bare existing executable")
                complete = mirrored(catalog["tools"][name]["artifact"], candidates)
                if not complete:
                    require(supply.get("allowKitFallback") is True, "Core staging requires the complete " + name + " runtime and kit fallback is disabled")
                    complete = {"source": "kit", "fallbackReason": "insufficient", "evidence": "Exact existing command is adequate on host, but container staging requires a complete dependency archive; no qualified private archive found; " + supply["inspectionEvidence"]}
                complete["canonicalLinks"] = host_choices[name].get("canonicalLinks", [])
                host_choices[name] = complete
        setup["docker"] = {"enabled": True, "artifactPlan": str(output / "artifact-plan.json"), "state": str(core_state)}
        if config.get("dockerHost"):
            require(config["dockerHost"].startswith("unix://"), "dockerHost must be an inspected local Unix socket")
            install["core"]["dockerHost"] = config["dockerHost"]
    if profiles_enabled:
        require({"python", "codex", "native-profiles"}.issubset(selected), "Profiles need python, codex and native-profiles selected")
        locations = {name: tool_location(name, catalog["tools"][name], host_choices[name], base, identities, command)
                     for name, command in (("python", "python3"), ("codex", "codex"), ("native-profiles", None))}
        asset, asset_ids = locations["native-profiles"]
        manifest_hash = asset_ids.get("files", {}).get("ASSET_MANIFEST.json")
        require(manifest_hash and SHA.fullmatch(manifest_hash), "Native profile asset manifest identity is missing")
        activate_hooks = config.get("profiles", {}).get("activateReviewedCodexHooks", False)
        require(isinstance(activate_hooks, bool), "profiles.activateReviewedCodexHooks must be boolean")
        if activate_hooks:
            require(config.get("profiles", {}).get("reviewedAssetManifestSha256") == manifest_hash,
                    "Review the packaged native hook source and supply its exact reviewedAssetManifestSha256 before activating Codex hooks")
        home = Path.home()
        profile = {"schemaVersion": 1, "assetRoot": str(asset), "python": str(locations["python"][0]), "pythonSha256": locations["python"][1],
                   "reviewedAssetManifestSha256": manifest_hash, "auditDirectory": str(state / "profile-audit"), "receiptDirectory": str(state / "profile-receipts"),
                   "clients": {"claude": {"configDir": str(home / ".claude")},
                               "codex": {"home": str(home / ".codex"), "skillsDir": str(home / ".agents/skills"), "binary": str(locations["codex"][0]), "binarySha256": locations["codex"][1], "activateReviewedHooks": activate_hooks},
                               "omp": {"agentDir": str(home / ".omp/agent")}}, "inspectedReplacements": []}
        overrides = config.get("profiles", {}).get("clients", {})
        if config["bootstrapMode"] == "existing":
            require(set(overrides) == {"claude", "codex", "omp"}, "Existing profiles require explicit inspected clients paths, including named/environment-selected profiles")
        for client, values in overrides.items():
            allowed = {"claude": {"configDir"}, "codex": {"home", "skillsDir"}, "omp": {"agentDir"}}
            require(client in allowed and isinstance(values, dict) and set(values).issubset(allowed[client]), "Only inspected client profile paths may be overridden")
            for key, value in values.items():
                absolute(value, "profiles.clients." + client + "." + key)
            profile["clients"][client].update(values)
        generated["profile-plan.json"] = profile
        install["profiles"].update(plan=str(output / "profile-plan.json"), assetTool="native-profiles", pythonTool="python", pythonCommand="python3")
    if config.get("productivity", {}).get("enabled", True):
        product_catalog_path = kit / "config/productivity-catalog.json"
        product_catalog = read(product_catalog_path)
        names = config.get("productivity", {}).get("tools", list(product_catalog["tools"]))
        choices = select_tools(product_catalog, names, supply, index, candidates, identities, mode, config)
        generated["productivity-plan.json"] = {"schemaVersion": 1, "mode": mode, "catalog": str(product_catalog_path), "privateRepositoriesChecked": checks, "tools": choices}
        functional = (["inspect", "benchmark"] if "inspect" in choices else []) + (["browser"] if "playwright" in choices else [])
        generated["productivity-plan.json"]["acceptance"] = functional
        if "playwright" in choices:
            generated["productivity-plan.json"]["browserExecutable"] = config.get("productivity", {}).get("browserExecutable", "/usr/lib/chromium/chromium")
        if core_enabled and config.get("productivity", {}).get("exposePortableToolsToWorkers", True):
            portable = [name for name in ("worktrunk", "rtk", "zoekt", "language-servers") if name in choices]
            for name in portable:
                if choices[name]["source"] == "existing" and not choices[name].get("normalizePath"):
                    require(name not in index.get("tools", {}), "Container delivery tools require a complete private archive for " + name)
                    complete = mirrored(product_catalog["tools"][name]["artifact"], candidates)
                    if not complete:
                        require(supply.get("allowKitFallback") is True, "No complete portable runtime archive for " + name)
                        complete = {"source": "kit", "fallbackReason": "insufficient", "evidence": "Bare existing executable does not provide a portable container dependency archive; " + supply["inspectionEvidence"]}
                    complete["canonicalLinks"] = choices[name].get("canonicalLinks", [])
                    choices[name] = complete
            generated["productivity-plan.json"].update(coreState=str(state / "core"), containerTools=portable)
        setup["productivity"] = {"enabled": True, "plan": str(output / "productivity-plan.json"), "state": str(state / "productivity")}
    generated["installation.json"] = install
    generated["setup.json"] = setup
    generated["source-inspection.json"] = {"schemaVersion": 1, "sourceConfigSha256": sha(path), "os": actual, "privateRepositoriesChecked": checks,
                                           "tools": {name: {"source": choice["source"], "evidence": choice["evidence"]} for name, choice in host_choices.items()},
                                           "note": "No host mutation, model credential inspection, public download or tool upgrade was performed by compilation."}
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True, help="Private output directory")
    parser.add_argument("--kit-root", default=str(ROOT))
    parser.add_argument("--check", action="store_true", help="Validate/resolve without writing output")
    args = parser.parse_args()
    output = absolute(args.output, "output")
    kit = absolute(args.kit_root, "kit-root").resolve()
    try:
        generated = compile_config(absolute(args.config, "config"), output, kit)
        require(not any(p.is_symlink() for p in [output, *output.parents]), "Compiled output cannot traverse symlinks")
        if not args.check:
            output.mkdir(parents=True, exist_ok=True, mode=0o700)
            require(output.stat().st_uid == os.getuid() and output.stat().st_mode & 0o077 == 0, "Compiler output must be private and operator-owned")
            require(not any(output.iterdir()), "Compile into a new empty directory; preserve previous plans for resume")
            for name, value in generated.items():
                fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as stream:
                    json.dump(value, stream, indent=2); stream.write("\n")
        print(json.dumps({"setupConfig": str(output / "setup.json"), "blockers": [], "files": sorted(generated), "checkedOnly": args.check}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"setupConfig": None, "blockers": [str(exc)]}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
