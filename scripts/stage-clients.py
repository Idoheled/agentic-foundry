#!/usr/bin/env python3
"""Stage qualified complete host-client trees into the managed core runtime; no Docker calls."""
import argparse
import ctypes
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


hostctl = module("client_stage_hostctl", "hostctl.py")
core = module("client_stage_core", "agenticctl.py")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def parents_without_links(path):
    for part in (path, *path.parents):
        require(not part.is_symlink(), "Inspect symlinked staging path before continuing: " + str(part))


def check_tree(root):
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), "Client source must be a complete real directory")
    resolved = root.resolve()
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode), "Unsupported special file in client tree")
        if path.is_symlink():
            require(not Path(os.readlink(path)).is_absolute(), "Client tree contains an absolute symlink")
        require(path.resolve().is_relative_to(resolved), "Client tree symlink escapes its complete installation")


def rename_no_replace(source, destination):
    # Linux renameat2 provides same-filesystem atomic promotion without replacing even an empty directory.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    require(rename is not None, "This host lacks atomic no-replace directory promotion; leave staged clients unpromoted")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise FileExistsError(code, os.strerror(code), str(destination))
        raise OSError(code, os.strerror(code), str(destination))


def stage(host_receipt, state_value, names, report_name="client-runtime.json"):
    state = Path(state_value).expanduser().absolute()
    parents_without_links(state)
    marker = state / "agentic-install.json"
    require(marker.is_file() and not marker.is_symlink(), "Initialize the dedicated core stack before staging clients")
    owner = os.getuid()
    require(state.stat().st_uid == owner and json.loads(marker.read_text()).get("uid") == owner,
            "Core stack state/marker belongs to a different operator")
    require(names and len(names) == len(set(names)) and all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}", name) for name in names),
            "Provide unique comma-separated client catalog names")
    receipt_path = Path(host_receipt).expanduser().absolute()
    require(receipt_path.is_file() and not receipt_path.is_symlink(), "Use the actual qualified hostctl receipt file")
    raw = receipt_path.read_bytes()
    receipt_sha = hashlib.sha256(raw).hexdigest()
    receipt = json.loads(raw)
    require(receipt_path.stat().st_uid == owner and receipt.get("schemaVersion") == 1 and receipt.get("operatorUid") == owner,
            "Host receipt belongs to another operator or has an unsupported schema")
    require(receipt.get("status") in ("installed_and_verified", "installed_with_blockers") and
            receipt.get("verification", {}).get("passed") is True,
            "Hostctl receipt has not passed installation verification")
    chosen = {}
    for name in names:
        record = receipt.get("tools", {}).get(name)
        require(isinstance(record, dict), "Selected client is missing from the hostctl receipt: " + name)
        staged = record.get("staged", {})
        require(staged.get("reuse") is False and staged.get("installPath") and staged.get("treeSha256"),
                "Cannot stage an unknown dependency closure from a reused bare executable: " + name + "; normalize its complete runtime tree first")
        source = Path(staged["installPath"])
        check_tree(source)
        identity = hostctl.tree_identity(source)
        require(identity == staged["treeSha256"], "Qualified host tree changed: " + name)
        selection = record.get("selection", {})
        version = str(selection.get("version", ""))
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}", version), "Client receipt needs its exact safe version identifier")
        chosen[name] = {"source": source, "identity": identity, "selection": selection,
                        "directory": version + "-" + identity[:16]}
    # Use the controller's ordinary-operator and managed-directory checks, without its disk/runtime preflight.
    state = core.make_state(argparse.Namespace(state=str(state)))
    clients_root = state / "runtime/clients"
    parents_without_links(clients_root)
    clients_root.mkdir(parents=True, exist_ok=True)
    require(re.fullmatch(r"[a-z][a-z0-9-]*\.json", report_name), "Invalid client staging report name")
    report_path = state / "reports" / report_name
    require(not report_path.is_symlink(), "Client-runtime report cannot be a symlink")
    lock_path = state / "reports/client-staging.lock"
    require(not lock_path.is_symlink(), "Client staging lock cannot be a symlink")
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Preflight every destination before copying the first tree.
        for name, item in chosen.items():
            destination = clients_root / name / item["directory"]
            parents_without_links(destination)
            if destination.exists():
                require(destination.is_dir() and hostctl.tree_identity(destination) == item["identity"],
                        "Preserving foreign or changed client destination: " + str(destination))
            item["destination"] = destination
        clients = {}
        for name, item in chosen.items():
            destination = item["destination"]
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".staging-") as temporary:
                    tree = Path(temporary) / "tree"
                    shutil.copytree(item["source"], tree, symlinks=True)
                    check_tree(tree)
                    require(hostctl.tree_identity(tree) == item["identity"], "Client source changed while copying: " + name)
                    rename_no_replace(tree, destination)
            require(hostctl.tree_identity(destination) == item["identity"], "Staged tree identity mismatch: " + name)
            container_root = "/opt/agentic/clients/" + name + "/" + item["directory"]
            commands = {}
            for command, spec in item["selection"].get("commands", {}).items():
                relative = spec if isinstance(spec, str) else spec["path"]
                hostctl.relative(relative)
                commands[command] = container_root + "/" + relative
            clients[name] = {"sourceInstallPath": str(item["source"]), "sourceTreeSha256": item["identity"],
                "sourceArtifact": item["selection"].get("artifact"), "source": item["selection"].get("source"),
                "destination": str(destination), "containerRoot": container_root, "containerCommands": commands,
                "requiredPaths": item["selection"].get("catalog", {}).get("requiredPaths", []),
                "treeIdentityVerified": True, "containerExecutionQualified": False}
        require(hostctl.digest(receipt_path) == receipt_sha, "Hostctl receipt changed during staging; no success report written")
        previous = core.read_json(report_path, {})
        if previous:
            require(previous.get("schemaVersion") == 1 and previous.get("operatorUid") == owner,
                    "Preserving an unrelated client-runtime report")
            backup = state / "reports" / (report_name[:-5] + "-before-" + hashlib.sha256(report_path.read_bytes()).hexdigest()[:16] + ".json")
            if not backup.exists():
                core.write_json(backup, previous)
        report = {"schemaVersion": 1, "operatorUid": owner, "hostReceipt": str(receipt_path), "hostReceiptSha256": receipt_sha,
            "passed": True, "scope": "Complete selected host trees copied and identity-verified in core runtime; no container execution or profile installation performed",
            "clients": clients,
            "profilePlanHints": {"nativeProfilesRoot": clients.get("native-profiles", {}).get("containerRoot"),
                "pythonCommands": clients.get("python", {}).get("containerCommands", {}),
                "next": "Use these immutable container paths in the site-specific profile plan. Run the real profile installer with verified Python as the ordinary operator, then qualify actual container execution and models."}}
        core.write_json(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-receipt", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--names", default="codex,claude,python,native-profiles")
    args = parser.parse_args()
    report = stage(args.host_receipt, args.state, [name.strip() for name in args.names.split(",")])
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        sys.exit(2)
