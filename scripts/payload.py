#!/usr/bin/env python3
"""Hydrate a lean Git checkout from a private offline payload mirror or verified release tar.

No public downloads, shell interpolation, credential handling or target installation.
Existing differing files are preserved. Payload identities are pinned in payload.lock.json.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_relative(name):
    p = PurePosixPath(name)
    require(not p.is_absolute() and ".." not in p.parts and "\\" not in name and p.parts and p.parts[0] == "payload", "Unsafe locked payload path")
    return p


def destination(root, name):
    path = root / safe_relative(name)
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Payload destination traverses a symlink: " + name)
    return path


def install_stream(stream, target, entry):
    if target.exists():
        require(target.is_file() and target.stat().st_size == entry["bytes"] and digest(target) == entry["sha256"], "Preserving differing existing payload: " + str(target))
        return "reused"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".staging-")
    h = hashlib.sha256(); count = 0
    try:
        with os.fdopen(fd, "wb") as out:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                out.write(block); h.update(block); count += len(block)
        require(count == entry["bytes"] and h.hexdigest() == entry["sha256"], "Supplied payload does not match lock: " + str(target))
        os.chmod(tmp, entry.get("mode", 0o644))
        # No replacement if another operation created the destination while hashing.
        os.link(tmp, target)
        return "hydrated"
    finally:
        Path(tmp).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "hydrate"))
    parser.add_argument("--root", default=str(ROOT))
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--from-dir", help="Private mirror root containing payload/ or an extracted release root")
    source.add_argument("--archive", help="Local full release tar or tar.gz")
    parser.add_argument("--sha256", help="Expected full release archive hash from the release record")
    args = parser.parse_args()
    root = Path(args.root).absolute()
    lock = json.loads((root / "payload.lock.json").read_text())
    require(lock.get("schemaVersion") == 1, "Unsupported payload lock")
    files = lock.get("files", {})
    require(files and all(name.startswith("payload/") for name in files), "Empty or invalid payload lock")
    results = {}
    if args.command == "verify":
        for name, entry in files.items():
            path = destination(root, name)
            results[name] = path.is_file() and path.stat().st_size == entry["bytes"] and digest(path) == entry["sha256"]
        failed = [name for name, passed in results.items() if not passed]
        print(json.dumps({"passed": not failed, "checked": len(results), "missingOrDifferent": failed}, indent=2))
        return 2 if failed else 0
    require(args.from_dir or args.archive, "hydrate requires --from-dir or --archive; no network source is assumed")
    if args.from_dir:
        mirror = Path(args.from_dir).absolute()
        require(mirror.is_dir(), "Private payload mirror is not a directory")
        for name, entry in files.items():
            source_file = mirror / safe_relative(name)
            require(source_file.is_file() and source_file.resolve().is_relative_to(mirror.resolve()), "Missing or escaping private payload: " + name)
            with source_file.open("rb") as stream:
                results[name] = install_stream(stream, destination(root, name), entry)
    else:
        archive = Path(args.archive).absolute()
        require(args.sha256 and len(args.sha256) == 64 and digest(archive) == args.sha256, "Release archive digest is required and must match")
        seen = set()
        with tarfile.open(archive, "r|*") as bundle:
            for member in bundle:
                name = PurePosixPath(member.name)
                require(not name.is_absolute() and ".." not in name.parts and "\\" not in member.name, "Unsafe release archive path")
                if member.isdir():
                    continue
                require(member.isfile(), "Release archive must contain regular files and directories only")
                relative = str(name) if name.parts and name.parts[0] == "payload" else str(PurePosixPath(*name.parts[1:]))
                if relative not in files:
                    continue
                require(relative not in seen, "Duplicate payload in release archive")
                seen.add(relative)
                entry = files[relative]
                require(member.size == entry["bytes"], "Release payload length differs from lock")
                with bundle.extractfile(member) as stream:
                    results[relative] = install_stream(stream, destination(root, relative), entry)
        require(set(files) == seen, "Release archive is missing locked payload files")
    print(json.dumps({"passed": True, "hydrated": sum(v == "hydrated" for v in results.values()), "reused": sum(v == "reused" for v in results.values())}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, tarfile.TarError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
