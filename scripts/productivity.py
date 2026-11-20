#!/usr/bin/env python3
"""Install and verify the selected delivery tools through the existing host provisioner."""
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def absolute(value, label):
    p = Path(value).expanduser()
    require(p.is_absolute() and ".." not in p.parts, label + " must be an absolute normalized path")
    return p


def state_path(value, create=False):
    p = absolute(value, "state")
    require(not any(x.is_symlink() for x in [p, *p.parents]), "State cannot traverse symlinks")
    marker = p / "productivity-state.json"
    if p.exists():
        require(p.is_dir() and p.stat().st_uid == os.getuid(), "Productivity state belongs to another operator")
        require(not marker.is_symlink(), "Refusing productivity state marker symlink")
        if marker.exists():
            value = read(marker)
            require(value.get("schemaVersion") == 1 and value.get("uid") == os.getuid(), "Unrecognized productivity state")
        else:
            require(not any(p.iterdir()), "Preserving unrelated nonempty productivity state; select a separate directory")
    if create:
        p.mkdir(parents=True, exist_ok=True, mode=0o700)
        require(p.stat().st_uid == os.getuid() and p.stat().st_mode & 0o077 == 0,
                "Productivity state must be a private directory owned by the operator")
        if not marker.exists():
            atomic(marker, {"schemaVersion": 1, "uid": os.getuid()})
    return p


def atomic(path, data):
    require(not path.is_symlink(), "Refusing report symlink")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def inputs(args):
    plan_path = absolute(args.plan, "plan")
    plan = read(plan_path)
    require(plan.get("schemaVersion") == 1, "Productivity plan schemaVersion must be 1")
    mode = plan.get("mode", "system")
    require(mode in ("system", "user"), "Choose mode system or user")
    catalog = absolute(plan.get("catalog", str(ROOT / "config/productivity-catalog.json")), "catalog")
    known = read(catalog)
    selected = plan.get("tools")
    require(isinstance(selected, dict) and selected, "Select the productivity tools to install")
    require(set(selected).issubset(known.get("tools", {})), "Selected tool is absent from productivity catalog")
    checks = plan.get("privateRepositoriesChecked")
    require(isinstance(checks, list) and checks and all(isinstance(v, str) and v.strip() and "REPLACE_" not in v for v in checks),
            "Inspect private repositories and record the factual results first")
    return plan_path, plan, catalog, mode


def invoke(args, command, catalog, mode, receipt=None):
    argv = [sys.executable, str(ROOT / "scripts/hostctl.py"), command,
            "--catalog", str(catalog), "--plan", str(Path(args.plan).absolute()),
            "--payload-root", str(ROOT), "--state", str(Path(args.state) / "host"), "--mode", mode]
    if args.prefix:
        argv.extend(["--prefix", str(absolute(args.prefix, "test prefix"))])
    if receipt:
        argv.extend(["--receipt", receipt])
    environment = os.environ.copy()
    local_bin = Path("/usr/local/bin") if mode == "system" else Path.home() / ".local/bin"
    environment["PATH"] = str(local_bin) + os.pathsep + environment.get("PATH", "/usr/bin:/bin")
    done = subprocess.run(argv, text=True, capture_output=True, env=environment, timeout=21600)
    require(done.returncode == 0, "Productivity host provisioner failed: " + (done.stderr or done.stdout)[-10000:])
    return json.loads(done.stdout)


def containers(plan, command, receipt):
    names = plan.get("containerTools", [])
    if not names:
        return None
    core_state = absolute(plan.get("coreState", ""), "coreState")
    require(isinstance(names, list) and all(isinstance(name, str) and name in plan["tools"] for name in names), "containerTools must be selected productivity tool names")
    done = subprocess.run([sys.executable, str(ROOT / "scripts/stage-productivity.py"), command,
                           "--host-receipt", receipt, "--core-state", str(core_state), "--names", ",".join(names)],
                          text=True, capture_output=True, timeout=21600)
    require(done.returncode == 0, "Portable tools container staging/qualification failed: " + (done.stderr or done.stdout)[-10000:])
    return json.loads(done.stdout)


def readiness(plan, mode):
    requirements = []
    if "worktrunk" in plan["tools"]:
        requirements.append(("git", shutil.which("git"), ["--version"], (2, 43)))
    if set(plan["tools"]) & {"language-servers", "playwright"}:
        local_bin = Path("/usr/local/bin") if mode == "system" else Path.home() / ".local/bin"
        node = os.environ.get("AGENTIC_NODE") or (str(local_bin / "agentic-node") if (local_bin / "agentic-node").is_file() else shutil.which("node"))
        requirements.append(("node", node, ["--version"], (22, 22, 2) if "language-servers" in plan["tools"] else (20,)))
    results = []
    for name, executable, argv, minimum in requirements:
        require(executable and Path(executable).is_absolute() and os.access(executable, os.X_OK), name + " prerequisite is missing; provision it from the private/native host plan first")
        done = subprocess.run([executable, *argv], capture_output=True, text=True, timeout=30)
        version = re.search(r"(?:^|\s|v)([0-9]+\.[0-9]+(?:\.[0-9]+)?)", done.stdout + done.stderr)
        parsed = tuple(map(int, version.group(1).split("."))) if version else ()
        require(done.returncode == 0 and parsed >= minimum, name + " prerequisite needs version " + ".".join(map(str, minimum)) + " or newer")
        results.append({"command": name, "path": executable, "version": version.group(1), "passed": True})
    return results


def acceptance(args, plan, mode):
    selected = plan.get("acceptance", [])
    require(isinstance(selected, list) and len(selected) == len(set(selected)) and set(selected).issubset({"inspect", "benchmark", "browser"}), "Unknown productivity acceptance gate")
    if not selected:
        return []
    local_bin = Path("/usr/local/bin") if mode == "system" else Path.home() / ".local/bin"
    if args.prefix:
        local_bin = Path(args.prefix) / str(local_bin).lstrip("/")
    run_root = Path(args.state) / ("acceptance-" + uuid.uuid4().hex)
    run_root.mkdir(mode=0o700)
    results = []
    for name in selected:
        tool, command = {"inspect": ("inspect", "inspect-smoke"), "benchmark": ("inspect", "bench-selftest"), "browser": ("playwright", "browser-smoke")}[name]
        require(tool in plan["tools"], "Acceptance gate requires selected tool " + tool)
        argv = [str(local_bin / ("agentic-" + command))]
        if name != "benchmark":
            argv.extend(["--state", str(run_root / name)])
        if name == "browser" and plan.get("browserExecutable"):
            argv.extend(["--browser", str(absolute(plan["browserExecutable"], "browserExecutable"))])
        output = run_root / (name + ".log")
        fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            done = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
        result = {"gate": name, "passed": done.returncode == 0, "exitCode": done.returncode, "output": str(output), "outputSha256": digest(output)}
        results.append(result)
        atomic(run_root / "result.json", {"schemaVersion": 1, "passed": all(item["passed"] for item in results), "checks": results})
        require(done.returncode == 0, name + " functional acceptance failed; inspect " + str(output) + ". Installation is present but this capability is not accepted")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "verify"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--prefix", help="Test-only fake filesystem prefix")
    args = parser.parse_args(argv)
    plan_path, plan, catalog, mode = inputs(args)
    state = state_path(args.state, create=args.command == "apply")
    binding = {"plan": str(plan_path), "planSha256": digest(plan_path), "catalog": str(catalog),
               "catalogSha256": digest(catalog), "mode": mode}
    if args.command == "plan":
        result = invoke(args, "plan", catalog, mode)
        print(json.dumps({"schemaVersion": 1, "binding": binding, "hostPlan": result,
                          "productionModelAcceptance": "Not run; tools are verified separately from your model routes"}, indent=2))
        return 0
    require(state.is_dir(), "No productivity installation state; run apply first")
    prerequisites = readiness(plan, mode)
    lock_path = state / "productivity.lock"
    require(not lock_path.is_symlink(), "Refusing operation lock symlink")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt_file = state / "productivity.json"
        require(not receipt_file.is_symlink(), "Refusing receipt symlink")
        if args.command == "verify":
            saved = read(receipt_file)
            require(saved.get("binding") == binding, "Plan or catalog changed since installation; inspect before reapplying")
            result = invoke(args, "check", catalog, mode, saved["hostReceipt"])
            container_result = containers(plan, "verify", saved["hostReceipt"])
            accepted = acceptance(args, plan, mode)
            print(json.dumps({"schemaVersion": 1, "passed": result.get("passed") is True,
                              "hostReceipt": saved["hostReceipt"], "verification": result, "containerVerification": container_result,
                              "prerequisites": prerequisites, "functionalAcceptance": accepted}, indent=2))
            return 0 if result.get("passed") is True else 2
        result = invoke(args, "apply", catalog, mode)
        require(result.get("passed") is True and result.get("status") == "installed_and_verified",
                "Some selected productivity tools did not install and verify")
        container_result = containers(plan, "apply", result["receipt"])
        accepted = acceptance(args, plan, mode)
        saved = {"schemaVersion": 1, "binding": binding, "hostReceipt": result["receipt"],
                 "status": "installed_and_verified", "tools": sorted(plan["tools"]),
                 "portableContainerToolsVerified": container_result.get("containerExecutionQualified") if container_result else None,
                 "prerequisites": prerequisites, "functionalAcceptance": accepted,
                 "note": "No existing brain, model route, hook or skill configuration was edited by this installer."}
        atomic(receipt_file, saved)
        print(json.dumps(saved, indent=2))
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
