#!/usr/bin/env python3
"""Coordinate explicit private installation plans; preserve routing, credentials and installer receipts."""
import argparse
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def fact(value, label):
    require(isinstance(value, str) and value.strip() and "REPLACE_" not in value, label + " requires factual nonplaceholder evidence")


def absolute(value, label, exists=False):
    require(isinstance(value, str) and value.startswith("/") and "REPLACE_" not in value,
            label + " must be an explicit absolute path")
    path = Path(value).expanduser()
    require(".." not in path.parts, label + " must be normalized")
    if exists:
        require(path.is_file(), label + " file is unavailable: " + str(path))
    return str(path)


def private_sources(plan, label):
    checks = plan.get("privateRepositoriesChecked")
    require(isinstance(checks, list) and checks, label + " requires completed private repository inspection")
    for item in checks:
        fact(item, label + ".privateRepositoriesChecked")


def write_private(path, value):
    path = Path(path)
    require(not path.is_symlink(), "Refusing a report symlink: " + str(path))
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".writing-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def safe_state(path):
    path = Path(path)
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "Coordinator state and parents must not be symlinks")
    marker = path / "installation-coordinator.json"
    if path.exists():
        require(path.is_dir() and path.stat().st_uid == os.getuid(), "Coordinator state must belong to this operator")
        require(not marker.is_symlink(), "Coordinator marker cannot be a symlink")
        if marker.exists():
            require(read(marker).get("uid") == os.getuid(), "Coordinator marker belongs to another operator")
        else:
            require(not any(path.iterdir()), "Preserving unrelated nonempty coordinator state")
    else:
        path.mkdir(parents=True, mode=0o700)
    if not marker.exists():
        write_private(marker, {"schemaVersion": 1, "uid": os.getuid()})
    path.chmod(0o700)
    return path


def enabled(site, name):
    value = site.get(name)
    return isinstance(value, dict) and value.get("enabled", True) is True


def bootstrap(script, *parts):
    return [str(ROOT / "scripts/python.sh"), str(ROOT / "scripts" / script), *map(str, parts)]


def load_site(path, only):
    site = read(path)
    require(site.get("schemaVersion") == 1, "Installation schemaVersion must be 1")
    fact(site.get("evidence"), "installation.evidence")
    site["coordinatorState"] = absolute(site.get("coordinatorState"), "coordinatorState")
    if only in ("all", "host", "profiles"):
        host = site.get("host", {})
        require(host.get("mode") in ("system", "user"), "Choose explicit host.mode system or user")
        absolute(host.get("plan"), "host.plan", True)
        absolute(host.get("state"), "host.state")
        host["catalog"] = absolute(host.get("catalog", str(ROOT / "config/host-catalog.json")), "host.catalog", True)
        private_sources(read(host["plan"]), "host.plan")
    if only == "native" or only == "all" and enabled(site, "native"):
        require(enabled(site, "native"), "Native-only installation requires an explicit enabled native plan")
        native = site["native"]
        absolute(native.get("plan"), "native.plan", True)
        absolute(native.get("state"), "native.state")
        private_sources(read(native["plan"]), "native.plan")
    if only == "all" and enabled(site, "core"):
        core = site["core"]
        absolute(core.get("config"), "core.config", True)
        absolute(core.get("state"), "core.state")
        config = read(core["config"])
        private_sources(read(absolute(config.get("artifactPlan"), "core.config.artifactPlan", True)), "core artifact plan")
        if core.get("dockerHost"):
            require(core["dockerHost"].startswith("unix://"), "Choose the inspected local Unix Docker socket")
    if only == "all" and enabled(site, "clients"):
        require(enabled(site, "core"), "Client staging requires the explicit core installation")
        names = site["clients"].get("names")
        require(isinstance(names, list) and names and all(isinstance(name, str) and name and "," not in name for name in names),
                "clients.names must list the chosen host catalog names")
    if only == "profiles" or only == "all" and enabled(site, "profiles"):
        require(enabled(site, "profiles"), "Profiles-only installation requires an explicit profile plan")
        absolute(site["profiles"].get("plan"), "profiles.plan", True)
        profile = read(site["profiles"]["plan"])
        require(profile.get("schemaVersion") == 1 and isinstance(profile.get("clients"), dict) and profile["clients"], "Complete the explicit native profile plan")
        for key in ("assetRoot", "python", "auditDirectory", "receiptDirectory"):
            absolute(profile.get(key), "profiles.plan." + key)
        fact(profile.get("pythonSha256"), "profiles.plan.pythonSha256")
        for client, values in profile["clients"].items():
            fields = {"claude": ("configDir",), "codex": ("home", "skillsDir"), "omp": ("agentDir",)}
            require(client in fields, "Unsupported native profile client")
            for field in fields[client]:
                absolute(values.get(field), "profiles.plan.clients." + client + "." + field)
            if client == "codex" and values.get("activateReviewedHooks") is True:
                fact(profile.get("reviewedAssetManifestSha256"), "explicitly reviewed asset manifest hash")
                absolute(values.get("binary"), "reviewed Codex binary")
                fact(values.get("binarySha256"), "reviewed Codex binary hash")
    if site.get("modelSmoke"):
        require(only != "all" or enabled(site, "core"), "modelSmoke requires the configured core stack")
    require(isinstance(site.get("retireOldTools", False), bool) and isinstance(site.get("modelSmoke", False), bool), "Retirement/modelSmoke must be explicit booleans")
    if only == "all":
        state_paths = {"coordinator": Path(site["coordinatorState"]), "host": Path(site["host"]["state"])}
        state_paths.update({name: Path(site[name]["state"]) for name in ("native", "core") if enabled(site, name)})
        for left, first in state_paths.items():
            for right, second in state_paths.items():
                if left < right:
                    require(not first.is_relative_to(second) and not second.is_relative_to(first),
                            "Use separate non-nested state directories for " + left + " and " + right)
    timeout = site.get("stepTimeoutSeconds", 7200)
    require(isinstance(timeout, int) and not isinstance(timeout, bool) and 1 <= timeout <= 86400,
            "stepTimeoutSeconds must be an integer from 1 to 86400")
    return site


def host_argv(site, command, receipt=None):
    host = site["host"]
    args = bootstrap("hostctl.py", command, "--catalog", host["catalog"], "--payload-root", ROOT,
                     "--plan", host["plan"], "--state", host["state"], "--mode", host["mode"])
    if receipt:
        args += ["--receipt", receipt]
    return args


def core_argv(site, command):
    core = site["core"]
    args = [str(ROOT / "install.sh"), command, "--config", core["config"], "--state", core["state"]]
    if core.get("dockerHost"):
        args += ["--docker-host", core["dockerHost"]]
    return args


def steps_for(site, only):
    steps = []
    def add(name, argv, kind=None):
        steps.append({"name": name, "argv": argv, "kind": kind or "command"})
    if only == "native" or only == "all" and enabled(site, "native"):
        native = site["native"]
        for command in ("plan", "apply"):
            add("native." + command, bootstrap("native-packages.py", command, "--plan", native["plan"], "--state", native["state"]))
    if only in ("all", "host"):
        add("host.plan", host_argv(site, "plan"))
        add("host.apply", host_argv(site, "apply"), "host-apply")
        add("host.verify", host_argv(site, "verify", "@HOST_RECEIPT@"))
    elif only == "profiles":
        add("host.verify-existing", host_argv(site, "verify", "@HOST_RECEIPT@"))
    if only == "all" and enabled(site, "core"):
        add("core.sources", core_argv(site, "sources"))
        add("core.install", core_argv(site, "install"))
        add("core.status", core_argv(site, "status"))
    if only == "all" and enabled(site, "clients"):
        add("clients.stage", bootstrap("stage-clients.py", "--host-receipt", "@HOST_RECEIPT@", "--state", site["core"]["state"],
                                      "--names", ",".join(site["clients"]["names"])))
    if only == "profiles" or only == "all" and enabled(site, "profiles"):
        profile = read(site["profiles"]["plan"])
        command = [profile["python"], str(Path(profile["assetRoot"]) / "install_profiles.py"), "--plan", site["profiles"]["plan"]]
        for suffix in ("check", "apply", "check-after"):
            add("profiles." + suffix, command + ["--check" if suffix != "apply" else "--apply"], "profile")
    if only in ("all", "host", "profiles"):
        add("host.verify-final", host_argv(site, "verify", "@HOST_RECEIPT@"))
    if only == "all" and enabled(site, "core"):
        add("core.verify", core_argv(site, "verify"))
        if site.get("modelSmoke") is True:
            add("core.model-smoke", core_argv(site, "model-smoke"))
    if site.get("retireOldTools") is True and only in ("all", "host"):
        require(only == "all", "Retirement is allowed only after the complete requested workflow, through install-all")
        add("host.retire", host_argv(site, "retire", "@HOST_RECEIPT@"))
    return steps


def read_host_receipt(site, path):
    path = Path(absolute(str(path), "host receipt", True))
    require(not path.is_symlink() and path.resolve().is_relative_to(Path(site["host"]["state"]).resolve()), "Use a receipt inside the selected host state")
    receipt = read(path)
    require(path.stat().st_uid == os.getuid() and receipt.get("operatorUid") == os.getuid(), "Host receipt belongs to another operator")
    require(receipt.get("status") in ("installed_and_verified", "installed_with_blockers") and receipt.get("verification", {}).get("passed") is True,
            "Host installation receipt has not passed verification")
    return receipt


def profile_binding(site, receipt_path):
    receipt = read_host_receipt(site, receipt_path)
    settings = site["profiles"]
    plan = read(settings["plan"])
    spec = importlib.util.spec_from_file_location("coordinator_hostctl", ROOT / "scripts/hostctl.py")
    hostctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hostctl)
    tools = receipt["tools"]
    asset = tools.get(settings.get("assetTool", "native-profiles"), {})
    staged = asset.get("staged", {})
    require(staged.get("reuse") is False and staged.get("installPath"), "Native profiles need their permanent complete asset-tree installation")
    root = Path(staged["installPath"])
    require(root.is_dir() and hostctl.tree_identity(root) == staged.get("treeSha256"), "Native profile asset tree changed")
    require(Path(plan["assetRoot"]) == root, "Profile plan assetRoot does not match the exact host receipt")
    python_tool = tools.get(settings.get("pythonTool", "python"), {})
    python_staged = python_tool.get("staged", {})
    command = settings.get("pythonCommand", "python3")
    if python_staged.get("reuse") is True:
        chosen = python_staged.get("executables", {}).get(command, {})
        python = Path(chosen.get("path", ""))
        require(python.is_file() and sha(python) == chosen.get("sha256"), "Selected existing Python changed")
    else:
        require(python_staged.get("installPath"), "Profile installation needs the selected verified Python")
        python_root = Path(python_staged["installPath"])
        require(hostctl.tree_identity(python_root) == python_staged.get("treeSha256"), "Selected Python tree changed")
        entry = python_tool["selection"].get("commands", {}).get(command)
        require(entry is not None, "Python command is not declared in the selected catalog")
        relative = entry if isinstance(entry, str) else entry["path"]
        hostctl.relative(relative)
        python = python_root / relative
    require(python.is_file() and os.access(python, os.X_OK) and Path(plan["python"]).resolve() == python.resolve() and sha(python) == plan["pythonSha256"],
            "Profile plan Python path/hash does not match the verified host receipt")
    require((root / "install_profiles.py").is_file(), "Permanent native profile installer is missing")
    # Deliberately do not generate or alter reviewedAssetManifestSha256 or hook trust fields.


def apply(site, steps, only, site_path):
    require(os.getuid() != 0, "Run the coordinator as the ordinary operator; child installers use existing sudo where required")
    state = safe_state(site["coordinatorState"])
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    run_dir = state / run_id
    run_dir.mkdir(mode=0o700)
    report_path = run_dir / "installation-report.json"
    report = {"schemaVersion": 1, "uid": os.getuid(), "siteSha256": sha(site_path), "status": "running", "steps": [],
              "scope": "Explicit installer coordination; no agent enrollment, model routing edits or automatic hook-trust selection"}
    write_private(report_path, report)
    receipt_path = None
    lock_path = state / "installation.lock"
    require(not lock_path.is_symlink(), "Coordinator lock cannot be a symlink")
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if only == "profiles":
                receipt_path = site.get("hostReceipt")
                if not receipt_path:
                    latest = Path(site["host"]["state"]) / "latest.json"
                    require(latest.is_file() and not latest.is_symlink(), "Supply an exact hostReceipt or finish host provisioning first")
                    receipt_path = read(latest)["receipt"]
                read_host_receipt(site, receipt_path)
            for index, step in enumerate(steps):
                if "@HOST_RECEIPT@" in step["argv"]:
                    require(receipt_path, "This step needs the exact successfully applied host receipt")
                argv = [receipt_path if value == "@HOST_RECEIPT@" else value for value in step["argv"]]
                if step["kind"] == "profile":
                    profile_binding(site, receipt_path)
                print("Running " + step["name"] + "; detailed output stays in the private coordinator log", flush=True)
                child_env = os.environ.copy()
                child_env["PYTHONDONTWRITEBYTECODE"] = "1"
                result = subprocess.run(argv, text=True, capture_output=True, timeout=site.get("stepTimeoutSeconds", 7200), check=False, env=child_env)
                log_path = run_dir / (str(index).zfill(2) + "-" + step["name"] + ".log")
                descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w") as log:
                    log.write(result.stdout)
                    log.write(result.stderr)
                record = {"name": step["name"], "exitCode": result.returncode, "log": str(log_path), "passed": result.returncode == 0}
                report["steps"].append(record)
                write_private(report_path, report)
                require(result.returncode == 0, step["name"] + " failed; inspect " + str(log_path) + ". Subsequent stages and retirement were not run")
                if step["kind"] == "host-apply":
                    output = json.loads(result.stdout)
                    receipt_path = absolute(output.get("receipt"), "new host apply receipt", True)
                    read_host_receipt(site, receipt_path)
                    report["hostReceipt"] = receipt_path
            require(sha(site_path) == report["siteSha256"], "Installation JSON changed during execution; inspect the completed steps before continuing")
            report["status"] = "requested_installer_steps_completed"
            report["passed"] = True
            report["containerProfileActivation"] = "Not executed; use the staged immutable runtime paths and qualify the actual container/profile/model workflow onsite"
            report["agentEnrollment"] = "Not performed"
        except Exception as exc:
            report.update(status="blocked", passed=False, blocker=str(exc))
            write_private(report_path, report)
            raise
        write_private(report_path, report)
    return {"passed": True, "report": str(report_path), "status": report["status"], "hostReceipt": receipt_path}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply"))
    parser.add_argument("--site", required=True)
    parser.add_argument("--only", choices=("all", "host", "native", "profiles"), default="all")
    parser.add_argument("--result-json", help="Write the exact successful coordinator result to an explicit private file")
    args = parser.parse_args()
    site_path = absolute(args.site, "installation site JSON", True)
    site = load_site(site_path, args.only)
    steps = steps_for(site, args.only)
    if args.command == "plan":
        print(json.dumps({"schemaVersion": 1, "scope": args.only, "steps": steps,
            "dynamicArguments": {"@HOST_RECEIPT@": "Exact receipt returned by this host.apply; profiles-only uses the supplied hostReceipt or inspected host latest.json"},
            "note": "This lists exact installer argv; it does not execute their validation or certify onsite facts."}, indent=2))
    else:
        result_path = None
        if args.result_json:
            result_path = Path(absolute(args.result_json, "coordinator result path"))
            require(not result_path.exists() and not result_path.is_symlink(), "Preserving an existing coordinator result")
            require(result_path.parent.is_dir() and result_path.parent.stat().st_uid == os.getuid(), "Coordinator result parent must belong to this operator")
            require(not any(parent.is_symlink() for parent in result_path.parents), "Coordinator result parents cannot be symlinks")
        result = apply(site, steps, args.only, site_path)
        if result_path is not None:
            write_private(result_path, result)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        sys.exit(2)
