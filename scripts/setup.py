#!/usr/bin/env python3
"""Offline, private-first bootstrap around the receipt-bound r4 installers.

This controller has no downloader and never edits a model route, shell startup file,
credential source, package database, or native client profile itself.
"""
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("debian13-x86_64", "apt-x86_64-internal", "linux-x86_64-internal")
COMMANDS = ("claude", "omp", "codex", "opencode", "git", "python3", "node", "bun",
            "docker", "podman", "tmux", "uv", "rg", "fd", "jq", "just", "direnv", "ast-grep")


class Blocked(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise Blocked(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def absolute(value, label, exists=False):
    need(isinstance(value, str) and value.startswith("/") and "REPLACE_" not in value,
         label + " must be an explicit absolute path")
    path = Path(value)
    need(".." not in path.parts and "\x00" not in value, label + " must be normalized")
    if exists:
        need(path.is_file() and not path.is_symlink(), label + " must be an existing regular non-symlink file")
    return path


def fact(value, label):
    need(isinstance(value, str) and value.strip() and "REPLACE_" not in value, label + " needs factual inspection evidence")


def module(name):
    path = ROOT / "scripts" / (name + ".py")
    need(path.is_file(), "Incomplete kit: missing scripts/" + name + ".py")
    spec = importlib.util.spec_from_file_location("setup_" + name.replace("-", "_"), path)
    value = importlib.util.module_from_spec(spec)
    # Helpers import their colocated artifact-policy module when loaded directly.
    source_dir = str(ROOT / "scripts")
    inserted = source_dir not in sys.path
    if inserted:
        sys.path.insert(0, source_dir)
    try:
        spec.loader.exec_module(value)
    finally:
        if inserted:
            sys.path.remove(source_dir)
    return value


def boot(name, *args):
    return [str(ROOT / "scripts/python.sh"), str(ROOT / "scripts" / name), *map(str, args)]


def no_symlinks(path):
    for item in (path, *path.parents):
        need(not item.is_symlink(), "Private state and its parent directories must not be symlinks: " + str(item))


def write(path, value):
    path = Path(path)
    need(not path.is_symlink(), "Refusing an output symlink: " + str(path))
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".writing-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def state_check(state, create=False):
    no_symlinks(state)
    marker = state / "setup-state.json"
    if state.exists():
        need(state.is_dir() and state.stat().st_uid == os.getuid(), "Setup state must belong to the ordinary operator")
        need(not marker.is_symlink(), "Setup marker cannot be a symlink")
        if marker.exists():
            found = read(marker)
            need(found.get("schemaVersion") == 1 and found.get("uid") == os.getuid(), "Unrecognized setup state")
        else:
            need(not any(state.iterdir()), "Preserving unrelated nonempty setup state; choose a separate directory")
    if create:
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        state.chmod(0o700)
        if not marker.exists():
            write(marker, {"schemaVersion": 1, "uid": os.getuid(), "createdAt": now()})


def inventory():
    release = {}
    release_path = Path("/etc/os-release")
    if release_path.is_file():
        for line in release_path.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                release[key] = value.strip('"')
    preservation = module("profile-preservation")
    discovery = preservation.discover(str(Path.home()))
    candidates = [{"path": item["path"], "role": item["role"],
                   "exists": os.path.lexists(item["path"])} for item in discovery["roots"]]
    commands = {}
    for name in COMMANDS:
        path = shutil.which(name)
        commands[name] = {"path": path, "resolved": str(Path(path).resolve()) if path else None}
    libc, version = platform.libc_ver()
    return {"schemaVersion": 1, "system": platform.system(), "architecture": platform.machine(),
            "os": {"id": release.get("ID"), "versionID": release.get("VERSION_ID")},
            "libc": {"name": libc, "version": version}, "uid": os.getuid(),
            "commands": commands, "candidateProfiles": candidates,
            "existingProfiles": [item["path"] for item in candidates if item["exists"]],
            "discoveryComplete": False,
            "discoveryNote": "Paths only; no client was invoked. Inspect aliases, wrappers, project roots, named profiles, brain directories and inherited environment before confirming completeness.",
            "supportedTargetProfiles": list(PROFILES),
            "missingSiteRequest": {"schemaKind": "minimal", "required": ["bootstrapMode", "evidence", "stateRoot", "privateSupply", "model"],
                                   "template": str(ROOT / "config/site-minimal.example.json"),
                                   "credentials": "Supply the model apiKeyEnv through the existing private environment; never put credentials into this request or Git."}}


def target_check(config, actual):
    target = config.get("target", {})
    profile = target.get("profile")
    need(profile in PROFILES, "Select a supported target.profile: " + ", ".join(PROFILES))
    need(actual["system"] == "Linux" and actual["architecture"] in ("x86_64", "amd64"),
         "This payload supports Linux x86-64; another architecture requires a separately built and qualified payload")
    minimum = target.get("minimumGlibc", "2.28")
    need(isinstance(minimum, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", minimum), "Invalid target.minimumGlibc")
    need(actual["libc"]["name"] == "glibc" and actual["libc"]["version"], "This payload requires glibc; musl targets need separate artifacts")
    need(tuple(map(int, actual["libc"]["version"].split("."))) >= tuple(map(int, minimum.split("."))), "Target glibc is too old")
    if profile == "debian13-x86_64":
        need(actual["os"]["id"] == "debian" and (actual["os"]["versionID"] or "").split(".")[0] == "13", "The Debian13 fallback profile requires Debian 13")
    if profile == "apt-x86_64-internal":
        need(actual["os"]["id"] in ("debian", "ubuntu"), "The internal APT profile requires Debian or Ubuntu")


def selected_inputs(config_path, config, site):
    paths = [config_path, Path(config["installation"]), Path(site["host"]["plan"]), Path(site["host"]["catalog"])]
    for key in ("native", "profiles"):
        if isinstance(site.get(key), dict) and site[key].get("enabled", True):
            paths.append(Path(site[key]["plan"]))
    if isinstance(site.get("core"), dict) and site["core"].get("enabled", True):
        core = Path(site["core"]["config"])
        paths += [core, Path(read(core)["artifactPlan"])]
    if config.get("productivity", {}).get("enabled"):
        product_plan = Path(config["productivity"]["plan"])
        paths += [product_plan, Path(read(product_plan).get("catalog", str(ROOT / "config/productivity-catalog.json")))]
    if config.get("docker", {}).get("enabled"):
        paths.append(Path(config["docker"]["artifactPlan"]))
    if config.get("preservation"):
        protection = config["preservation"]
        paths.append(Path(protection["plan"]))
        paths += [Path(path) for key in ("additionReviews", "migrationReviews") for path in protection.get(key, [])]
    for path in (ROOT / "SHA256SUMS", ROOT / "scripts/setup.py", ROOT / "scripts/install-stack.py"):
        if path.is_file():
            paths.append(path)
    return {str(path): sha(path) for path in dict.fromkeys(paths)}


def inputs_unchanged(inputs):
    for name, expected in inputs.items():
        path = Path(name)
        need(path.is_file() and not path.is_symlink() and sha(path) == expected,
             "A selected input changed: " + name + ". Review the change and use a new setup transaction; do not reset an existing preservation baseline.")


def validate(config_path, state, scope="all", actual=None, resumed=False):
    config_path = absolute(str(config_path), "setup config", True)
    config = read(config_path)
    need(config.get("schemaVersion") == 1 and config.get("schemaKind", "setup") == "setup", "Use a setup schemaVersion 1 or a minimal site configuration")
    fact(config.get("evidence"), "setup.evidence")
    need(config.get("bootstrapMode") in ("fresh", "existing"), "Choose bootstrapMode fresh or existing")
    actual = actual or inventory()
    target_check(config, actual)
    state_check(state)
    coordinator = module("install-stack")
    installation = absolute(config.get("installation"), "installation", True)
    site = coordinator.load_site(str(installation), "all")
    need(site.get("retireOldTools", False) is False, "Defer old-runtime retirement until the full onsite acceptance gates pass; setup does not accept retireOldTools=true")
    if scope == "all" and config["bootstrapMode"] == "existing":
        omp = read(site["host"]["plan"]).get("tools", {}).get("omp")
        need(omp is None or (omp.get("source") == "existing" and omp.get("adequate") is True and not omp.get("normalizePath")),
             "Existing OMP replacement belongs in the Claude -> OMP phase-1 workflow. Use setup agent; phase 2 must omit OMP or reuse the already qualified runtime.")
    protection = config.get("preservation")
    if config["bootstrapMode"] == "existing" or (actual["existingProfiles"] and not resumed):
        need(isinstance(protection, dict), "Existing client profiles require an explicit reviewed preservation plan and the original baseline. Use setup agent for discovery.")
    if protection:
        plan_path = absolute(protection.get("plan"), "preservation.plan", True)
        absolute(protection.get("state"), "preservation.state")
        helper = module("profile-preservation")
        plan = helper.validate_plan(read(plan_path))
        roots = [Path(item["path"]) for item in plan["roots"]]
        for discovered in actual["existingProfiles"]:
            need(any(Path(discovered).is_relative_to(root) for root in roots), "Preservation plan does not cover discovered profile: " + discovered)
        for key in ("additionReviews", "migrationReviews"):
            reviews = protection.get(key, [])
            need(isinstance(reviews, list), "preservation." + key + " must be an array")
            for review in reviews:
                absolute(review, "preservation review", True)
    products = config.get("productivity", {"enabled": False})
    need(isinstance(products, dict) and isinstance(products.get("enabled", False), bool), "productivity.enabled must be a boolean")
    if products.get("enabled"):
        absolute(products.get("plan"), "productivity.plan", True)
        absolute(products.get("state"), "productivity.state")
        need((ROOT / "scripts/productivity.py").is_file(), "Productivity installer is absent from this kit")
    need(scope != "productivity" or products.get("enabled"), "Productivity-only scope requires productivity.enabled=true")
    enrollment = config.get("enrollment", {"enabled": False})
    need(isinstance(enrollment, dict) and isinstance(enrollment.get("enabled", False), bool), "enrollment.enabled must be a boolean")
    if enrollment.get("enabled"):
        need(coordinator.enabled(site, "core") and site.get("modelSmoke") is True, "Agent enrollment requires core and a passing configured model smoke step")
    if coordinator.enabled(site, "core"):
        core = read(site["core"]["config"])
        module("agenticctl").validate_config(core, True)
        if scope == "all" and site.get("modelSmoke"):
            need(bool(os.environ.get(core["model"]["apiKeyEnv"])), "Required private model credential environment variable is not available: " + core["model"]["apiKeyEnv"])
    docker = config.get("docker", {"enabled": False})
    need(isinstance(docker, dict) and isinstance(docker.get("enabled", False), bool), "docker.enabled must be a boolean")
    if docker.get("enabled"):
        need(coordinator.enabled(site, "core"), "Docker bootstrap requires an enabled core installation")
        absolute(docker.get("artifactPlan"), "docker.artifactPlan", True)
        need(str(absolute(docker.get("state"), "docker.state")) == site["core"]["state"], "Docker state must be the exact selected core state")
        need(docker["artifactPlan"] == read(site["core"]["config"])["artifactPlan"], "Docker bootstrap must use the same private-first artifact plan as core")
    directories = {"setup": state, "coordinator": Path(site["coordinatorState"]), "host": Path(site["host"]["state"])}
    directories.update({key: Path(site[key]["state"]) for key in ("native", "core") if coordinator.enabled(site, key)})
    if products.get("enabled"):
        directories["productivity"] = Path(products["state"])
    if protection:
        directories["preservation"] = Path(protection["state"])
    for left, first in directories.items():
        no_symlinks(first)
        for right, second in directories.items():
            if left < right:
                need(not first.is_relative_to(second) and not second.is_relative_to(first), "Use separate non-nested state directories for " + left + " and " + right)
    if coordinator.enabled(site, "native"):
        native = module("native-packages")
        native_plan = read(site["native"]["plan"])
        native.validate(native_plan, native.system_info())
        fact(native_plan.get("hostRecoveryEvidence"), "native.hostRecoveryEvidence")
        need(shutil.which("apt-get"), "Configured native package helper requires APT")
    return config, site, actual, selected_inputs(config_path, config, site)


def run_readonly(argv):
    # These commands validate files and declarations, not model routes or agents.
    result = subprocess.run(argv, text=True, capture_output=True, timeout=300, check=False,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    need(result.returncode == 0, "Plan validation failed for " + Path(argv[1] if argv[0].endswith("python.sh") else argv[0]).name + ". Run its plan command directly for the detailed private diagnostic.")
    return {"argv": argv, "passed": True}


def plan(config_path, state, scope="all", actual=None, resumed=False):
    config, site, detected, inputs = validate(config_path, state, scope, actual, resumed)
    coordinator = module("install-stack")
    checks = []
    if scope == "all":
        checks.append(run_readonly(coordinator.host_argv(site, "plan")))
        if coordinator.enabled(site, "core"):
            checks.append(run_readonly(coordinator.core_argv(site, "sources")))
    if config.get("productivity", {}).get("enabled"):
        product = config["productivity"]
        checks.append(run_readonly(boot("productivity.py", "plan", "--plan", product["plan"], "--state", product["state"])))
    steps = []
    if config.get("preservation"):
        steps.append("preservation.snapshot-or-verify-original-baseline")
    if scope == "all":
        if config.get("docker", {}).get("enabled"):
            steps.append("docker.reuse-or-bootstrap-private-daemon")
        steps += [step["name"] for step in coordinator.steps_for(site, "all")]
    if config.get("productivity", {}).get("enabled"):
        steps += ["productivity.apply", "productivity.verify"]
    if scope == "all" and config.get("enrollment", {}).get("enabled"):
        steps.append("core.seed-with-task-wakes-disabled")
    if config.get("preservation"):
        steps.append("preservation.verify-original-baseline")
    return {"schemaVersion": 1, "passed": True, "status": "plan_validated", "scope": scope,
            "bootstrapMode": config["bootstrapMode"], "setupState": str(state), "steps": steps,
            "checks": checks, "inputSha256": inputs,
            "modelConnectionChecked": False, "machineChanged": False,
            "note": "A plan confirms current file identities and declarations; installation, internal-model connectivity and real task acceptance are separate gates."}


def run_private(state, name, argv, timeout=7200):
    logs = state / "logs"
    no_symlinks(logs)
    logs.mkdir(mode=0o700, exist_ok=True)
    log = logs / (name + "-" + secrets.token_hex(6) + ".log")
    print("Running " + name + "; detailed output stays in the private setup log", file=sys.stderr, flush=True)
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        process = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT,
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
            code = 124
    need(code == 0, name + " failed (exit " + str(code) + "); inspect " + str(log) + ". Later stages were not executed.")
    return {"name": name, "passed": True, "log": str(log), "logSha256": sha(log), "at": now()}


def preserve(config, state, label, allow_reviews=False):
    protection = config.get("preservation")
    if not protection:
        return {"status": "not-required-fresh-profile", "passed": True}
    helper = module("profile-preservation")
    baseline = Path(protection["state"])
    if not (baseline / "baseline.json").exists():
        helper.snapshot(protection["plan"], baseline)
    original = read(baseline / "baseline.json")
    need(original["planSha256"] == helper.digest(helper.canonical(read(protection["plan"]))), "Selected preservation plan differs from the original baseline; do not rebaseline")
    if allow_reviews:
        # These are explicit exact-identity approvals. Never synthesize blanket approvals.
        for filename in protection.get("additionReviews", []):
            spec = read(filename)
            entries = {item["path"]: item["identity"] for item in spec.get("entries", [])}
            if not any(receipt.get("entries") == entries for receipt in helper.approvals(baseline, "addition-reviews")):
                helper.record_additions(baseline, filename)
        for filename in protection.get("migrationReviews", []):
            spec = read(filename)
            recorded = [receipt for receipt in helper.approvals(baseline, "migration-reviews") if receipt.get("sourcePath") == spec.get("sourcePath")]
            if not recorded:
                helper.record_migration(baseline, filename)
            else:
                need(len(recorded) == 1 and all(recorded[0].get(key) == spec.get(key) for key in ("sourcePath", "sourceSha256", "destinationPath", "retainedOriginalPath", "baselineSemanticEvidence"))
                     and recorded[0].get("destinationIdentity", {}).get("sha256") == spec.get("destinationSha256")
                     and recorded[0].get("afterSemanticSha256") == spec.get("afterSemanticEvidence", {}).get("sha256"),
                     "The supplied migration review differs from the original recorded migration")
    result = helper.verify(baseline, label)
    report = state / (label + "-preservation-" + secrets.token_hex(5) + ".json")
    write(report, result)
    need(result.get("status") == "verified", "Preservation verification blocked; inspect " + str(report) + ". Keep the original baseline and review only exact additions/migrations.")
    return {"status": "verified", "passed": True, "report": str(report), "sha256": sha(report)}


def verify_coordinator(site, result, state):
    coordinator = module("install-stack")
    need(result.get("passed") is True and result.get("status") == "requested_installer_steps_completed", "Missing successful installation result")
    report_path = absolute(result.get("report"), "installation report", True)
    report = read(report_path)
    need(report.get("passed") is True and report.get("status") == result["status"], "Installation report is not complete")
    need(report.get("siteSha256") == sha(site["_setupInstallationPath"]), "Installation report does not match the pinned installation configuration")
    receipt = result.get("hostReceipt")
    host = coordinator.read_host_receipt(site, receipt)
    need(host.get("planSha256") == sha(site["host"]["plan"]) and host.get("catalogSha256") == sha(site["host"]["catalog"]) and host.get("mode") == site["host"]["mode"], "Host receipt does not match the pinned plan, catalog and mode")
    verified = []
    for step in coordinator.steps_for(site, "all"):
        if step["name"] not in ("host.verify-final", "profiles.check-after", "core.verify", "core.model-smoke"):
            continue
        if step["kind"] == "profile":
            coordinator.profile_binding(site, receipt)
        argv = [receipt if item == "@HOST_RECEIPT@" else item for item in step["argv"]]
        verified.append(run_private(state, "resume-" + step["name"], argv, site.get("stepTimeoutSeconds", 7200)))
    return verified


def docker_ready(config, site, state):
    core = module("agenticctl")
    options = argparse.Namespace(config=site["core"]["config"], state=site["core"]["state"], docker_host=site["core"].get("dockerHost"))
    try:
        response = core.docker(options, "info", "--format", "{{.ServerVersion}}", capture=True, check=False, timeout=15)
        usable = response.returncode == 0 and bool(response.stdout.strip())
    except (RuntimeError, OSError, subprocess.SubprocessError):
        usable = False
    if usable:
        return {"passed": True, "source": "existing-local-daemon", "at": now()}
    need(not options.docker_host, "The explicitly selected local Docker socket is unusable. Repair it or review the private-daemon selection; setup will not silently change it.")
    settings = config["docker"]
    record = run_private(state, "docker-bootstrap", [str(ROOT / "scripts/bootstrap-docker.sh"), "--artifact-plan", settings["artifactPlan"], "--state", settings["state"]], 1800)
    # On a truly fresh host the selected host CLI is not installed yet. The
    # dedicated helper deliberately uses its own root-owned Docker runtime.
    identifier = hashlib.sha256(settings["state"].encode()).hexdigest()[:10]
    binary = Path("/opt") / ("agentic-docker-" + identifier) / "docker"
    socket = "unix:///run/agentic-docker-" + identifier + "/docker.sock"
    need(binary.is_file() and not binary.is_symlink(), "Dedicated Docker runtime is missing after bootstrap")
    response = subprocess.run([str(binary), "--host", socket, "info", "--format", "{{.ServerVersion}}"], text=True, capture_output=True, timeout=15, check=False)
    need(response.returncode == 0 and response.stdout.strip(), "Private Docker bootstrap returned without a usable local daemon")
    record["source"] = "private-daemon-from-reviewed-artifact-plan"
    return record


def apply(config_path, state, scope="all", actual=None, source_binding=None):
    need(os.getuid() != 0, "Run setup as the ordinary operator; existing installers use sudo only when required")
    progress_path = state / "progress.json"
    prior = read(progress_path) if progress_path.is_file() and not progress_path.is_symlink() else None
    validated = plan(config_path, state, scope, actual, resumed=bool(prior and prior.get("freshStart")))
    config, site, detected, inputs = validate(config_path, state, scope, actual, resumed=bool(prior and prior.get("freshStart")))
    site["_setupInstallationPath"] = config["installation"]
    if source_binding:
        inputs[source_binding["path"]] = source_binding["sha256"]
    if prior:
        need(prior.get("inputSha256") == inputs, "Setup inputs changed since the previous run. Review them and select a new setup state; preserve the original client baseline.")
    state_check(state, create=True)
    lock_path = state / "setup.lock"
    need(not lock_path.is_symlink(), "Setup lock cannot be a symlink")
    descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Blocked("Another setup process owns this state")
        progress = prior or {"schemaVersion": 1, "uid": os.getuid(), "createdAt": now(), "inputSha256": inputs,
                             "freshStart": config["bootstrapMode"] == "fresh" and not detected["existingProfiles"],
                             "initialExistingProfiles": detected["existingProfiles"], "completed": {}}
        progress.update(status="running", requestedScope=scope)
        write(progress_path, progress)
        try:
            inputs_unchanged(inputs)
            progress["lastPreservation"] = preserve(config, state, "before-setup")
            if scope == "all":
                if config.get("docker", {}).get("enabled"):
                    progress["completed"]["docker"] = docker_ready(config, site, state)
                    write(progress_path, progress)
                if "installation" in progress["completed"]:
                    old = progress["completed"]["installation"]
                    need(Path(old["resultPath"]).is_file() and sha(old["resultPath"]) == old["resultSha256"], "The exact prior coordinator result changed")
                    verify_coordinator(site, old["result"], state)
                else:
                    result_path = state / ("installation-result-" + secrets.token_hex(8) + ".json")
                    record = run_private(state, "installation", boot("install-stack.py", "apply", "--site", config["installation"], "--only", "all", "--result-json", result_path), site.get("stepTimeoutSeconds", 7200) * max(1, len(validated["steps"])))
                    need(result_path.is_file() and not result_path.is_symlink(), "Installer did not write its exact result")
                    result = read(result_path)
                    need(result.get("passed") is True and result.get("status") == "requested_installer_steps_completed", "Installer result was not complete")
                    record["result"] = result
                    record["resultPath"] = str(result_path)
                    record["resultSha256"] = sha(result_path)
                    progress["completed"]["installation"] = record
                    write(progress_path, progress)
                inputs_unchanged(inputs)
                progress["lastPreservation"] = preserve(config, state, "after-installation", allow_reviews=True)
            if config.get("productivity", {}).get("enabled"):
                product = config["productivity"]
                command = "verify" if "productivity" in progress["completed"] else "apply"
                record = run_private(state, "productivity-" + command, boot("productivity.py", command, "--plan", product["plan"], "--state", product["state"]), site.get("stepTimeoutSeconds", 7200))
                if command == "apply":
                    run_private(state, "productivity-verify", boot("productivity.py", "verify", "--plan", product["plan"], "--state", product["state"]), site.get("stepTimeoutSeconds", 7200))
                progress["completed"]["productivity"] = record
                write(progress_path, progress)
            if scope == "all" and config.get("enrollment", {}).get("enabled"):
                # The existing seed operation checks exact models, projects and previously registered agents.
                record = run_private(state, "core-enrollment", module("install-stack").core_argv(site, "seed"), site.get("stepTimeoutSeconds", 7200))
                progress["completed"]["enrollment"] = record
                write(progress_path, progress)
            inputs_unchanged(inputs)
            progress["lastPreservation"] = preserve(config, state, "after-setup", allow_reviews=True)
            progress.update(status="productivity_completed" if scope == "productivity" else "requested_setup_steps_completed",
                            passed=True, completedAt=now(),
                            agentEnrollment="registered-with-task-wakes-disabled" if scope == "all" and config.get("enrollment", {}).get("enabled") else "not-requested-in-this-scope",
                            realTaskAcceptance="Not asserted by setup. Complete the real internal model/tool/session/task checks before enabling task wakes.",
                            containerProfileActivation="Not asserted by setup. Qualify the actual worker/profile route using the existing handoff.")
            write(progress_path, progress)
        except Exception as exc:
            progress.update(status="blocked", passed=False, blocker=str(exc))
            write(progress_path, progress)
            raise
    return {"schemaVersion": 1, "passed": True, "status": progress["status"], "scope": scope,
            "report": str(progress_path), "agentEnrollment": progress["agentEnrollment"],
            "realTaskAcceptance": progress["realTaskAcceptance"], "containerProfileActivation": progress["containerProfileActivation"]}


def compile_minimal(source, destination):
    compiler = ROOT / "scripts/compile-site.py"
    need(compiler.is_file(), "This source checkout lacks compile-site.py; use an explicit setup configuration or the complete kit")
    result = subprocess.run(boot("compile-site.py", "--config", source, "--output", destination, "--kit-root", ROOT), capture_output=True, text=True, timeout=900, check=False,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        value = json.loads(result.stdout)
    except ValueError:
        raise Blocked("Minimal site compilation failed; run compile-site.py --check for a structured diagnostic")
    need(result.returncode == 0 and not value.get("blockers"), "Minimal site is incomplete: " + "; ".join(map(str, value.get("blockers", ["inspect compiler output"]))))
    compiled = absolute(value.get("setupConfig"), "compiled setup config", True)
    need(compiled.is_relative_to(destination), "Compiler output escaped its private destination")
    return compiled


def relocate_compiled(source, target):
    def rewrite(value):
        if isinstance(value, str) and (value == str(source) or value.startswith(str(source) + "/")):
            return str(target) + value[len(str(source)):]
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, dict):
            return {key: rewrite(item) for key, item in value.items()}
        return value
    for path in source.rglob("*"):
        need(not path.is_symlink(), "Compiler output cannot contain symlinks")
        if path.is_file() and path.suffix == ".json":
            write(path, rewrite(read(path)))
    need(not target.exists(), "Compiled setup already exists; inspect its original source binding")
    # The compiler temporary directory can live on another filesystem.
    staging = target.with_name(target.name + ".moving-" + secrets.token_hex(5))
    shutil.copytree(source, staging)
    os.rename(staging, target)


def execute_config(command, source, state, scope):
    source = absolute(str(source), "site configuration", True)
    source_binding = {"path": str(source), "sha256": sha(source)}
    if read(source).get("schemaKind") != "minimal":
        return plan(source, state, scope) if command == "plan" else apply(source, state, scope)
    binding_path = state / "minimal-source.json"
    compiled_dir = state / "compiled"
    if binding_path.exists():
        need(not binding_path.is_symlink() and read(binding_path)["source"] == source_binding, "Minimal site changed since compilation; review it and select a new setup transaction")
        compiled = absolute(read(binding_path)["setupConfig"], "compiled setup config", True)
        if command == "plan":
            return plan(compiled, state, scope, resumed=(state / "progress.json").is_file())
        return apply(compiled, state, scope, source_binding=source_binding)
    state_check(state)
    with tempfile.TemporaryDirectory(prefix="agentic-site-") as temporary:
        output = Path(temporary) / "compiled"
        compiled = compile_minimal(source, output)
        validated = plan(compiled, state, scope)
        if command == "plan":
            validated["sourceConfig"] = source_binding
            validated["compiledPlanLocation"] = "Temporary compilation was removed after this read-only plan. Apply compiles and pins it in private setup state."
            return validated
        need(os.getuid() != 0, "Run setup as the ordinary operator")
        need(sha(source) == source_binding["sha256"], "Minimal site changed during compilation")
        relative = compiled.relative_to(output)
        state_check(state, create=True)
        relocate_compiled(output, compiled_dir)
        compiled = compiled_dir / relative
        write(binding_path, {"schemaVersion": 1, "source": source_binding, "setupConfig": str(compiled)})
    return apply(compiled, state, scope, source_binding=source_binding)


def agent(config_path, state):
    config = read(absolute(str(config_path), "agent configuration", True)) if config_path else {}
    settings = config.get("agent", {})
    engine = settings.get("engine", "claude")
    need(engine in ("claude", "omp"), "agent.engine must be claude or omp")
    arguments = settings.get("args", [])
    need(isinstance(arguments, list) and all(isinstance(item, str) and "\x00" not in item for item in arguments), "agent.args must be an inspected argv array")
    forbidden = ("-p", "--print", "--approval-mode", "--dangerously-skip-permissions", "--resume", "--continue")
    need(not any(item in forbidden or any(item.startswith(flag + "=") for flag in forbidden if flag.startswith("--")) for item in arguments), "agent.args may carry profile/config options, not execution, resume or approval options")
    mode = config.get("bootstrapMode", "existing")
    need(mode in ("fresh", "existing"), "Choose bootstrapMode fresh or existing")
    env = os.environ.copy()
    env["AGENTIC_SETUP_STATE"] = str(state)
    if config_path:
        env["AGENTIC_SETUP_CONFIG"] = str(config_path)
    if mode == "existing":
        upgrade_state = absolute(settings.get("upgradeState", str(state.with_name(state.name + "-upgrade"))), "agent.upgradeState")
        argv = [str(ROOT / "upgrade.sh"), "start-claude" if engine == "claude" else "start-omp", "--state", str(upgrade_state)]
        if engine == "claude" and arguments:
            argv += ["--", *arguments]
        need(engine != "omp" or not arguments, "OMP continuation restores its previously qualified arguments; do not override them")
    else:
        need(config_path is not None, "Fresh agent setup needs an explicit site configuration")
        need(engine == "claude", "For a fresh machine, use deterministic apply or an already configured Claude; OMP agent continuation is qualified by phase 1")
        binary = shutil.which("claude")
        need(binary, "No existing Claude command is available; use deterministic setup apply to install the selected tools first")
        prompt = ("Set up this disconnected workspace using " + str(ROOT / "setup.sh") + ". Read " + str(ROOT / "docs/BOOTSTRAP_AND_LIFECYCLE.md") +
                  " and HANDOFF.md completely. The private site is " + str(config_path) + "; setup state is " + str(state) +
                  ". Run doctor and plan, then apply. Preserve every existing route, credential source, brain, skill and hook. "
                  "Use private sources first, never invent evidence, never access a public registry. If discovery finds existing client state, "
                  "select the original two-phase upgrade workflow and review the exact preservation baseline. "
                  "Report real blockers and actual acceptance results; do not claim a perfect machine or enable unqualified task wakes.")
        argv = [binary, *arguments, "--dangerously-skip-permissions", "-p", prompt]
    os.execvpe(argv[0], argv, env)


def main(argv=None):
    supplied = list(sys.argv[1:] if argv is None else argv)
    if not supplied or supplied[0].startswith("--"):
        supplied.insert(0, "apply")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("doctor", "plan", "apply", "agent"))
    parser.add_argument("--config")
    parser.add_argument("--state", default=str(Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "agentic-stack/setup-r5"))
    parser.add_argument("--only", choices=("all", "productivity"), default="all")
    args = parser.parse_args(supplied)
    state = absolute(args.state, "setup state")
    if args.command == "doctor":
        result = inventory()
        if args.config:
            result["siteConfig"] = str(absolute(args.config, "site config", True))
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "agent":
        need(args.only == "all", "agent delegates the preserved two-phase workflow; --only is for plan/apply")
        agent(Path(args.config) if args.config else None, state)
        return 0
    need(args.config, "A private site configuration is required. Run setup doctor and complete config/site-minimal.example.json; credentials remain in the existing environment.")
    print(json.dumps(execute_config(args.command, Path(args.config), state, args.only), indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Blocked, RuntimeError, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"schemaVersion": 1, "passed": False, "status": "blocked", "blockers": [str(exc)],
                          "next": "Inspect the private configuration and logs. Preserve the original baseline and completed receipts; no automatic destructive recovery is attempted."}, indent=2))
        sys.exit(2)
