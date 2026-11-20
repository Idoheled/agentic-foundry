"""Source-only checksum contract shared by refresh and standalone export tools."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile

import offline_payload as payload

INVENTORY = "SOURCE_MANIFEST.json"
SUMS = "SHA256SUMS"
EXACT_EXCLUSIONS = {INVENTORY, SUMS, "RELEASE_FILES.sha256"}
TOP_EXCLUSIONS = {".git", "payload", "private", "state", "workspaces", "runtime", "dist",
                  "build", "reports", "release-evidence", ".pytest_cache"}
PART_EXCLUSIONS = {"__pycache__", "node_modules", ".venv", ".git"}
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def eligible(name):
    path = PurePosixPath(name)
    payload.need(isinstance(name, str) and name and "\x00" not in name and "\n" not in name and "\r" not in name and "\\" not in name,
                 "Invalid source inventory path")
    payload.need(not path.is_absolute() and ".." not in path.parts and str(path) == name, "Unsafe source inventory path: " + name)
    return not (name in EXACT_EXCLUSIONS or path.parts[0] in TOP_EXCLUSIONS or
                any(part in PART_EXCLUSIONS for part in path.parts) or
                path.parts[:2] == ("offline", "objects") or
                path.suffix in (".pyc", ".pyo"))


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=True).stdout


def version(root):
    value = payload.regular(root / "VERSION").read_text().strip()
    payload.need(SEMVER.fullmatch(value) is not None, "VERSION must contain a semantic version without a v prefix")
    return value


def source_names(root, stored=None):
    if (root / ".git").exists():
        names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\x00")
        return sorted({name for name in names if name and eligible(name)})
    payload.need(stored and isinstance(stored.get("files"), dict), "An exported source tree requires SOURCE_MANIFEST.json")
    names = sorted(stored["files"])
    payload.need(all(eligible(name) for name in names), "Exported source inventory includes an excluded path")
    return names


def normalized_mode(path):
    # Git records regular files as 100644 or 100755. Owner read/write mask and
    # workstation umask are not part of the portable source-release contract.
    return 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644


def control_record(root, names):
    files = {}
    for name in names:
        path = payload.regular(root / name)
        files[name] = {"sha256": payload.digest(path), "bytes": path.stat().st_size, "mode": normalized_mode(path)}
    payload.need({"VERSION", "payload.lock.json", "offline/manifest.json"} <= set(files), "Source inventory is missing required control files")
    return {"schemaVersion": 1, "scope": "Maintained source controls; immutable payload identities are pinned separately",
            "version": version(root), "files": files}


def encode(record):
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def expected(root, names):
    manifest = payload.load(root)
    record = control_record(root, names)
    inventory_text = encode(record)
    entries = {name: entry["sha256"] for name, entry in record["files"].items()}
    entries[INVENTORY] = hashlib.sha256(inventory_text.encode()).hexdigest()
    entries.update({name: entry["sha256"] for name, entry in manifest["files"].items()})
    sums_text = "".join(entries[name] + "  " + name + "\n" for name in sorted(entries))
    return record, inventory_text, sums_text, manifest


def atomic_write(path, text):
    path = payload.guard(path)
    if path.exists() and path.read_text() == text:
        return
    fd, temporary = tempfile.mkstemp(prefix=".foundry-integrity-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o644)
        payload.guard(path)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def check(root, with_payload=False):
    root = payload.guard(root)
    stored = payload.read_json(payload.regular(root / INVENTORY))
    payload.need(stored.get("schemaVersion") == 1, "Unsupported source inventory")
    record, inventory_text, sums_text, manifest = expected(root, source_names(root, stored))
    payload.need((root / INVENTORY).read_text() == inventory_text,
                 "SOURCE_MANIFEST.json is stale; review source changes and run scripts/refresh-checksums.py --write")
    payload.need(payload.regular(root / SUMS).read_text() == sums_text,
                 "SHA256SUMS is stale; review source changes and run scripts/refresh-checksums.py --write")
    if with_payload:
        for name, entry in manifest["files"].items():
            payload.existing_matches(payload.destination(root, name), entry)
    return {"passed": True, "operation": "check", "sourceVersion": record["version"],
            "sourceFiles": len(record["files"]), "payloadFiles": len(manifest["files"]),
            "payloadBytesChecked": with_payload}, record, manifest


def refresh(root):
    root = payload.guard(root)
    payload.need((root / ".git").exists(), "Refresh maintained source checksums in a Git checkout, not a deployed/exported release")
    record, inventory_text, sums_text, manifest = expected(root, source_names(root))
    atomic_write(root / INVENTORY, inventory_text)
    atomic_write(root / SUMS, sums_text)
    return {"passed": True, "operation": "write", "sourceVersion": record["version"],
            "sourceFiles": len(record["files"]), "payloadFiles": len(manifest["files"]),
            "payloadBytesChecked": False}
