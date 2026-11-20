#!/usr/bin/env python3
"""Expose explicitly selected portable delivery tools to existing Paperclip workers.

Copies complete receipt-qualified trees into the existing read-only runtime mount;
adds tracked command wrappers and probes the actual container. No model, brain,
profile, skill, hook, orchestrator schedule or project configuration is rewritten.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / (name + ".py"))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("apply", "verify"))
    parser.add_argument("--host-receipt", required=True)
    parser.add_argument("--core-state", required=True)
    parser.add_argument("--names", required=True)
    args = parser.parse_args()
    stage = module("stage-clients"); core = stage.core; host = stage.hostctl
    state = Path(args.core_state).absolute()
    stage.parents_without_links(state)
    marker = state / "agentic-install.json"
    stage.parents_without_links(marker)
    require(state.is_dir() and state.stat().st_uid == os.getuid() and marker.is_file() and json.loads(marker.read_text()).get("uid") == os.getuid(),
            "Core state/marker must belong to the intended operator")
    names = args.names.split(",")
    # These exact portable runtime recipes are qualified independently of Debian browser dependencies.
    require(names and len(names) == len(set(names)) and set(names).issubset({"worktrunk", "rtk", "zoekt", "language-servers"}), "Container activation supports only the named portable delivery runtime recipes")
    record_path = state / "reports/productivity-commands.json"
    report_path = state / "reports/productivity-runtime.json"
    stage.parents_without_links(record_path); stage.parents_without_links(report_path)
    receipt_path = Path(args.host_receipt).absolute()
    stage.parents_without_links(receipt_path)
    require(receipt_path.is_file() and receipt_path.stat().st_uid == os.getuid(), "Host receipt must be owned by the operator")
    receipt_hash = host.digest(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    require(receipt.get("schemaVersion") == 1 and receipt.get("operatorUid") == os.getuid(), "Unsupported or foreign host receipt")
    require(receipt.get("verification", {}).get("passed") is True, "Host tools must verify before container exposure")
    require(set(names).issubset(receipt.get("tools", {})), "Selected portable tools are absent from this receipt")
    for name in names:
        selection = receipt["tools"][name].get("selection", {})
        commands = selection.get("commands", {})
        require(isinstance(commands, dict) and commands and all(isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}", key) for key in commands),
                "Invalid source command names; no runtime path was written")
        for field in ("environment", "environmentDefaults"):
            values = selection.get("catalog", {}).get(field, {})
            require(isinstance(values, dict) and all(isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) and isinstance(value, str) and "\x00" not in value for key, value in values.items()),
                    "Invalid source environment; no runtime path was written")
    previous = core.read_json(record_path, {})
    if previous:
        require(previous.get("schemaVersion") == 1 and previous.get("operatorUid") == os.getuid(), "Preserving unrelated container command state")
    if args.command == "apply":
        staged = stage.stage(args.host_receipt, state, names, "productivity-runtime.json")
        require(staged.get("hostReceiptSha256") == receipt_hash and host.digest(receipt_path) == receipt_hash,
                "Host receipt changed before portable command promotion")
        wrappers = {}
        for name in names:
            item = staged["clients"][name]
            selection = receipt["tools"][name]["selection"]
            for command, executable in item["containerCommands"].items():
                text = "#!/bin/sh\nset -eu\n"
                for key, value in sorted(selection.get("catalog", {}).get("environmentDefaults", {}).items()):
                    text += 'if [ "${' + key + '+x}" != x ]; then export ' + key + "=" + shlex.quote(value) + "; fi\n"
                for key, value in sorted(selection.get("catalog", {}).get("environment", {}).items()):
                    text += "export " + key + "=" + shlex.quote(value) + "\n"
                text += "exec " + shlex.quote(executable) + ' "$@"\n'
                for alias in ("agentic-" + command, command):
                    path = state / "runtime/bin" / alias
                    stage.parents_without_links(path)
                    current = host.snapshot(path)
                    prior = previous.get("commands", {}).get(alias)
                    require(current["kind"] == "missing" or prior and current == prior["snapshot"], "Preserving an existing untracked/changed runtime command: " + alias)
                    wrappers[alias] = {"path": path, "text": text, "tool": name, "command": command}
        # Every destination is checked before the first command is written.
        commands = {}
        for alias, item in wrappers.items():
            core.atomic_text(item["path"], item["text"], 0o755)
            commands[alias] = {"snapshot": host.snapshot(item["path"]), "tool": item["tool"], "command": item["command"]}
        previous = {"schemaVersion": 1, "operatorUid": os.getuid(), "hostReceipt": str(Path(args.host_receipt).absolute()),
                    "names": names, "commands": commands, "containerExecutionQualified": False}
        core.write_json(record_path, previous)
    else:
        require(previous and previous.get("names") == names and previous.get("hostReceipt") == str(Path(args.host_receipt).absolute()), "No matching container delivery installation record")
        staged = core.read_json(report_path)
    require(staged.get("schemaVersion") == 1 and staged.get("operatorUid") == os.getuid() and set(staged.get("clients", {})) == set(names),
            "Staged container report does not match this operator and selected tool set")
    require(staged.get("hostReceiptSha256") == receipt_hash, "Host receipt changed since portable runtime staging")
    expected_aliases = {alias: (name, command) for name in names
                        for command in receipt["tools"][name]["selection"]["commands"]
                        for alias in (command, "agentic-" + command)}
    require(set(previous.get("commands", {})) == set(expected_aliases), "Container command aliases do not match the selected receipt")
    for alias, item in previous["commands"].items():
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,107}", alias) and (item.get("tool"), item.get("command")) == expected_aliases[alias],
                "Invalid container command identity")
    previous["containerExecutionQualified"] = False
    previous["checks"] = []
    previous["scope"] = "Verification in progress; prior success is not current acceptance"
    core.write_json(record_path, previous)
    checks = []
    for name in names:
        entry = staged["clients"][name]
        require(host.tree_identity(entry["destination"]) == entry["sourceTreeSha256"], "Staged portable runtime changed: " + name)
    for alias, entry in previous["commands"].items():
        require(host.snapshot(state / "runtime/bin" / alias) == entry["snapshot"], "Container command entry point changed: " + alias)
        if not alias.startswith("agentic-"):
            continue
        spec = receipt["tools"][entry["tool"]]["selection"]["commands"][entry["command"]]
        result = core.exec_worker(argparse.Namespace(state=str(state), config=None, docker_host=None),
                                  ["/opt/agentic/bin/" + alias, *spec.get("verifyArgs", ["--version"])],
                                  timeout=spec.get("verifyTimeoutSeconds", 60), capture=True)
        passed = result.returncode == 0
        if spec.get("verifyPattern"):
            passed = passed and re.search(spec["verifyPattern"], result.stdout + result.stderr) is not None
        checks.append({"command": alias, "passed": passed, "exitCode": result.returncode,
                       "output": (result.stdout + result.stderr)[-4000:]})
    previous["checks"] = checks
    previous["containerExecutionQualified"] = bool(checks) and all(item["passed"] for item in checks)
    previous["scope"] = "Portable command runtime checks; real model/tool delivery acceptance remains a separate phase gate"
    core.write_json(record_path, previous)
    print(json.dumps(previous, indent=2))
    return 0 if previous["containerExecutionQualified"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
