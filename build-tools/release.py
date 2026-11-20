#!/usr/bin/env python3
"""Build and verify an offline release without fetching from public sources.

prepare creates Git-trackable runtime checksums and payload.lock.json. The optional
integration source bundle and its commit receipt are release-only supplemental
files to avoid a self-referential Git hash. package includes and hashes them too.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile
import time

SUPPLEMENTAL = {"payload/sources/agentic-integration-r5.bundle", "provenance/r5/integration-source.json", "RELEASE_FILES.sha256"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def files(root):
    found = []
    for p in sorted(root.rglob("*")):
        if ".git" in p.relative_to(root).parts or "__pycache__" in p.parts:
            raise ValueError("Remove build/Git metadata from release tree: " + str(p))
        if p.is_symlink():
            raise ValueError("Outer release layout must contain regular files/directories only: " + str(p))
        if p.is_file():
            found.append(p)
    return found


def prepare(root, version):
    locked = {}
    for p in files(root):
        relative = p.relative_to(root).as_posix()
        if relative.startswith("payload/") and relative not in SUPPLEMENTAL:
            locked[relative] = {"sha256": digest(p), "bytes": p.stat().st_size, "mode": stat.S_IMODE(p.stat().st_mode)}
    (root / "payload.lock.json").write_text(json.dumps({"schemaVersion": 1, "release": version,
        "scope": "Offline runtime/source dependency payload; integration source bundle is supplemental release material", "files": locked}, indent=2) + "\n")
    manifest_path = root / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(kitVersion=version, payloadBytes=sum(v["bytes"] for v in locked.values()),
                    managedFileCount=len([p for p in files(root) if p.relative_to(root).as_posix() not in SUPPLEMENTAL | {"SHA256SUMS"}]))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    sums = []
    for p in files(root):
        relative = p.relative_to(root).as_posix()
        if relative not in SUPPLEMENTAL | {"SHA256SUMS"}:
            sums.append(digest(p) + "  " + relative + "\n")
    (root / "SHA256SUMS").write_text("".join(sums))
    print(json.dumps({"prepared": True, "runtimeFiles": len(sums), "payloadFiles": len(locked), "payloadBytes": manifest["payloadBytes"]}), flush=True)


def verify_inputs(root):
    sums = {}
    for line in (root / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = root / name
        if Path(name).is_absolute() or ".." in Path(name).parts or digest(path) != expected:
            raise ValueError("Runtime checksum mismatch: " + name)
        sums[name] = expected
    return sums


def package(root, output, prefix):
    if output.exists():
        raise ValueError("Preserving existing release output: " + str(output))
    verify_inputs(root)
    regular = [p for p in files(root) if p.name != "RELEASE_FILES.sha256"]
    (root / "RELEASE_FILES.sha256").write_text("".join(digest(p) + "  " + p.relative_to(root).as_posix() + "\n" for p in regular))
    temporary = output.with_name(output.name + ".writing")
    if temporary.exists():
        raise ValueError("Inspect prior incomplete release before retrying")
    count = 0; total = 0; last = 0
    try:
        with temporary.open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=5, mtime=0) as compressed:
                with tarfile.open(mode="w|", fileobj=compressed, format=tarfile.PAX_FORMAT) as archive:
                    for path in files(root):
                        info = tarfile.TarInfo(prefix + "/" + path.relative_to(root).as_posix())
                        info.size = path.stat().st_size; info.mode = stat.S_IMODE(path.stat().st_mode)
                        info.uid = 0; info.gid = 0; info.uname = "root"; info.gname = "root"; info.mtime = 0
                        with path.open("rb") as stream:
                            archive.addfile(info, stream)
                        count += 1; total += info.size
                        if total - last > 1024 ** 3:
                            print(json.dumps({"packedInputBytes": total, "files": count}), flush=True); last = total
        os.replace(temporary, output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    expected = {p.relative_to(root).as_posix(): {"sha256": digest(p), "bytes": p.stat().st_size, "mode": stat.S_IMODE(p.stat().st_mode)} for p in files(root)}
    observed = set()
    with tarfile.open(output, "r|gz") as archive:
        for entry in archive:
            if not entry.isfile() or not entry.name.startswith(prefix + "/"):
                raise ValueError("Unexpected archive member")
            name = entry.name[len(prefix) + 1:]
            if name not in expected or name in observed:
                raise ValueError("Unexpected or duplicate release member: " + name)
            observed.add(name); item = expected[name]
            h = hashlib.sha256()
            with archive.extractfile(entry) as stream:
                for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    h.update(block)
            if entry.size != item["bytes"] or entry.mode != item["mode"] or h.hexdigest() != item["sha256"]:
                raise ValueError("Packaged member differs: " + name)
    if observed != set(expected):
        raise ValueError("Release is missing files")
    sha = digest(output)
    Path(str(output) + ".sha256").write_text(sha + "  " + output.name + "\n")
    result = {"archive": str(output), "bytes": output.stat().st_size, "sha256": sha,
              "regularFilesVerified": len(observed), "uncompressedFileBytes": total, "passed": True}
    Path(str(output) + ".validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "package"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--version", default="2026-11-20-r5")
    parser.add_argument("--output")
    parser.add_argument("--prefix", default="agentic-workspace-r5")
    args = parser.parse_args()
    root = Path(args.root).absolute()
    if args.command == "prepare":
        prepare(root, args.version)
    else:
        if not args.output or not args.prefix or "/" in args.prefix or args.prefix in (".", ".."):
            parser.error("package needs --output and one safe archive --prefix")
        package(root, Path(args.output).absolute(), args.prefix)
