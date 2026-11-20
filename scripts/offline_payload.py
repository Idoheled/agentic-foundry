#!/usr/bin/env python3
"""Pack, validate, verify and hydrate the versioned Git LFS offline payload.

The source-controlled manifest binds to payload.lock.json. Objects are ordinary
Git LFS files; this tool never downloads anything or changes installed software.
Existing differing files, modes, manifests and objects are preserved.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "agentic-foundry-payload-chunks"
MAX_CHUNK = 512 * 1024 * 1024
BLOCK = 4 * 1024 * 1024
HASH = re.compile(r"^[0-9a-f]{64}$")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=no_duplicate_keys)


def integer(value, minimum=0, maximum=None):
    return type(value) is int and value >= minimum and (maximum is None or value <= maximum)


def sha_ok(value):
    return isinstance(value, str) and HASH.fullmatch(value) is not None


def safe_name(name):
    need(isinstance(name, str) and name and "\x00" not in name and "\n" not in name and "\r" not in name and "\\" not in name, "Invalid payload path")
    path = PurePosixPath(name)
    need(not path.is_absolute() and len(path.parts) >= 2 and path.parts[0] == "payload" and
         ".." not in path.parts and str(path) == name, "Unsafe payload path: " + name)
    return path


def guard(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        need(not item.is_symlink(), "Refusing symlink path: " + str(item))
    return path


def regular(path):
    path = guard(path)
    need(path.is_file() and stat.S_ISREG(path.stat().st_mode), "Missing regular file: " + str(path))
    return path


def digest(path):
    value = hashlib.sha256()
    with regular(path).open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            value.update(block)
    return value.hexdigest()


def destination(root, name):
    return guard(root / safe_name(name))


def object_path(root, oid):
    need(sha_ok(oid), "Invalid object identity")
    return guard(root / "offline" / "objects" / "sha256" / (oid + ".chunk"))


def metadata(entry, name):
    need(isinstance(entry, dict), "Invalid metadata: " + name)
    need(sha_ok(entry.get("sha256")) and integer(entry.get("bytes")) and
         integer(entry.get("mode"), maximum=0o777), "Invalid identity/size/mode: " + name)


def load(root):
    root = guard(root)
    lock_path = regular(root / "payload.lock.json")
    lock = read_json(lock_path)
    manifest = read_json(regular(root / "offline" / "manifest.json"))
    need(isinstance(lock, dict) and lock.get("schemaVersion") == 1 and isinstance(lock.get("files"), dict) and lock["files"], "Invalid payload lock")
    need(isinstance(manifest, dict) and manifest.get("schemaVersion") == 1 and manifest.get("format") == FORMAT, "Unsupported offline manifest")
    need(manifest.get("payloadLockSha256") == digest(lock_path), "Offline manifest does not match payload.lock.json")
    need(manifest.get("release") == lock.get("release"), "Payload release differs from lock")
    need(integer(manifest.get("maxChunkBytes"), 1, MAX_CHUNK), "Invalid chunk size limit")
    files, objects, supplemental = manifest.get("files"), manifest.get("objects"), manifest.get("supplementalFiles")
    need(isinstance(files, dict) and files and isinstance(objects, dict) and isinstance(supplemental, list), "Invalid manifest collections")
    need(all(isinstance(name, str) for name in supplemental) and len(set(supplemental)) == len(supplemental), "Duplicate or invalid supplemental paths")
    need(set(files) == set(lock["files"]) | set(supplemental) and not set(lock["files"]) & set(supplemental), "Locked/supplemental payload coverage differs")
    used = set()
    for oid, entry in objects.items():
        need(sha_ok(oid) and isinstance(entry, dict) and set(entry) == {"bytes"} and integer(entry.get("bytes"), 1, manifest["maxChunkBytes"]), "Invalid object definition")
    for name, entry in files.items():
        safe_name(name); metadata(entry, name)
        need(set(entry) == {"sha256", "bytes", "mode", "chunks"}, "Unexpected file metadata: " + name)
        chunks = entry["chunks"]
        need(isinstance(chunks, list) and all(sha_ok(oid) and oid in objects for oid in chunks), "Invalid or missing chunk reference: " + name)
        need(sum(objects[oid]["bytes"] for oid in chunks) == entry["bytes"], "Chunk sizes do not reconstruct payload: " + name)
        need(bool(chunks) == bool(entry["bytes"]), "Invalid empty payload representation: " + name)
        if entry["bytes"] == 0:
            need(entry["sha256"] == hashlib.sha256(b"").hexdigest(), "Empty payload hash differs")
        if name in lock["files"]:
            expected = lock["files"][name]; metadata(expected, name)
            need(all(entry[key] == expected[key] for key in ("sha256", "bytes", "mode")), "Manifest changes locked payload: " + name)
        used.update(chunks)
    need(used == set(objects), "Manifest contains unreferenced objects")
    return manifest


def summary(manifest):
    return {"files": len(manifest["files"]), "objects": len(manifest["objects"]),
            "payloadBytes": sum(entry["bytes"] for entry in manifest["files"].values()),
            "objectBytes": sum(entry["bytes"] for entry in manifest["objects"].values()),
            "release": manifest["release"]}


def stream_file(root, manifest, name, output=None):
    entry = manifest["files"][name]
    full = hashlib.sha256(); total = 0
    for oid in entry["chunks"]:
        path = regular(object_path(root, oid))
        expected = manifest["objects"][oid]["bytes"]
        need(path.stat().st_size == expected, "Missing LFS bytes or wrong object size: " + str(path) + "; run git lfs pull in the connected staging environment")
        chunk = hashlib.sha256(); count = 0
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(BLOCK), b""):
                count += len(block); total += len(block); chunk.update(block); full.update(block)
                if output is not None:
                    output.write(block)
        need(count == expected and chunk.hexdigest() == oid, "LFS object checksum differs: " + oid)
    need(total == entry["bytes"] and full.hexdigest() == entry["sha256"], "Reconstructed payload checksum differs: " + name)


def verify(root, manifest):
    for name in manifest["files"]:
        stream_file(root, manifest, name)
    return {"passed": True, "operation": "verify", **summary(manifest)}


def existing_matches(path, entry):
    regular(path)
    need(path.stat().st_size == entry["bytes"] and stat.S_IMODE(path.stat().st_mode) == entry["mode"] and digest(path) == entry["sha256"],
         "Preserving differing existing payload bytes or mode: " + str(path))


def hydrate(root, manifest, link_objects=False):
    # Validate all already-present destinations before the first write. This
    # prevents a late collision from leaving an otherwise avoidable partial run.
    for name, entry in manifest["files"].items():
        target = destination(root, name)
        if target.exists():
            existing_matches(target, entry)
    counts = {"hydrated": 0, "reused": 0, "linked": 0}
    for name, entry in manifest["files"].items():
        target = destination(root, name)
        if target.exists():
            existing_matches(target, entry); counts["reused"] += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        guard(target.parent)
        if link_objects and len(entry["chunks"]) == 1:
            source = regular(object_path(root, entry["chunks"][0]))
            if stat.S_IMODE(source.stat().st_mode) == entry["mode"]:
                stream_file(root, manifest, name)
                try:
                    os.link(source, target, follow_symlinks=False)
                    counts["hydrated"] += 1; counts["linked"] += 1
                    continue
                except OSError as exc:
                    if exc.errno not in (errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP):
                        raise
        fd, temporary = tempfile.mkstemp(prefix=".foundry-payload-", dir=target.parent)
        temporary = Path(temporary)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream_file(root, manifest, name, stream)
                stream.flush(); os.fsync(stream.fileno())
                os.fchmod(stream.fileno(), entry["mode"])
            guard(target)
            os.link(temporary, target, follow_symlinks=False)
            counts["hydrated"] += 1
        finally:
            temporary.unlink(missing_ok=True)
    return {"passed": True, "operation": "hydrate", **counts, **summary(manifest)}


def clone_range(source, target, offset, length):
    """Try Linux reflink without changing the source; unsupported filesystems fail."""
    import fcntl
    with source.open("rb") as inp, target.open("r+b") as out:
        fcntl.ioctl(out.fileno(), 0x4020940D, struct.pack("qQQQ", inp.fileno(), offset, length, 0))
        out.truncate(length)


def write_object(root, source, offset, length, link_source, reflink):
    folder = guard(root / "offline" / "objects" / "sha256")
    folder.mkdir(parents=True, exist_ok=True)
    guard(folder)
    fd, temporary = tempfile.mkstemp(prefix=".packing-", dir=folder)
    os.close(fd); temporary = Path(temporary)
    method = "copy"
    try:
        if link_source and offset == 0 and length == source.stat().st_size:
            try:
                temporary.unlink()
                os.link(source, temporary, follow_symlinks=False)
                method = "hardlink"
            except OSError as exc:
                if exc.errno not in (errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP):
                    raise
                temporary.touch(mode=0o600)
        if method != "hardlink":
            cloned = False
            if reflink != "never":
                try:
                    clone_range(source, temporary, offset, length)
                    cloned = True; method = "reflink"
                except (OSError, ImportError):
                    if reflink == "always":
                        raise ValueError("This filesystem cannot reflink the requested range")
            if not cloned:
                with source.open("rb") as inp, temporary.open("wb") as out:
                    inp.seek(offset); remaining = length
                    while remaining:
                        block = inp.read(min(BLOCK, remaining))
                        need(block, "Source ended while packing: " + str(source))
                        out.write(block); remaining -= len(block)
            os.chmod(temporary, 0o644)
        need(temporary.stat().st_size == length, "Packed object size differs")
        oid = digest(temporary)
        target = object_path(root, oid)
        if target.exists():
            need(target.stat().st_size == length and digest(target) == oid, "Preserving differing existing object: " + oid)
            return oid, "reused"
        os.link(temporary, target, follow_symlinks=False)
        return oid, method
    finally:
        temporary.unlink(missing_ok=True)


def inventory_chunks(source, size, chunk_bytes):
    """Read exact object identities without making a second copy of source data."""
    full = hashlib.sha256(); result = []
    with regular(source).open("rb") as stream:
        for offset in range(0, size, chunk_bytes):
            length = min(chunk_bytes, size - offset); remaining = length
            chunk = hashlib.sha256()
            while remaining:
                block = stream.read(min(BLOCK, remaining))
                need(block, "Source ended while inventorying: " + str(source))
                remaining -= len(block); chunk.update(block); full.update(block)
            result.append((chunk.hexdigest(), length))
        need(not stream.read(1), "Source grew while inventorying: " + str(source))
    return result, full.hexdigest()


def pack(root, source_root, chunk_bytes=MAX_CHUNK, link_source=False, reflink="auto", manifest_only=False):
    root = guard(root); source_root = guard(source_root)
    need(integer(chunk_bytes, 1, MAX_CHUNK), "Chunk size must be between 1 and 512 MiB")
    lock_path = regular(root / "payload.lock.json")
    need(digest(lock_path) == digest(regular(source_root / "payload.lock.json")), "Source and target payload locks differ")
    lock = read_json(lock_path)
    need(lock.get("schemaVersion") == 1 and isinstance(lock.get("files"), dict) and lock["files"], "Invalid payload lock")
    payload = guard(source_root / "payload")
    all_files = []
    for candidate in sorted(payload.rglob("*")):
        guard(candidate)
        need(candidate.is_file() or candidate.is_dir(), "Non-regular source payload item")
        if candidate.is_file():
            all_files.append(candidate)
    names = {p.relative_to(source_root).as_posix() for p in all_files}
    need(set(lock["files"]) <= names, "Source is missing locked payload files")
    manifest = {"schemaVersion": 1, "format": FORMAT, "release": lock.get("release"),
                "payloadLockSha256": digest(lock_path), "maxChunkBytes": chunk_bytes,
                "files": {}, "objects": {}, "supplementalFiles": sorted(names - set(lock["files"]))}
    methods = {"hardlink": 0, "reflink": 0, "copy": 0, "reused": 0}
    by_identity = {}; done = 0; last_report = 0
    for path in all_files:
        name = path.relative_to(source_root).as_posix(); safe_name(name)
        entry = {"sha256": digest(path), "bytes": path.stat().st_size, "mode": stat.S_IMODE(path.stat().st_mode)}
        metadata(entry, name)
        if name in lock["files"]:
            expected = lock["files"][name]; metadata(expected, name)
            need(all(entry[k] == expected[k] for k in ("sha256", "bytes", "mode")), "Source differs from lock: " + name)
        identity = (entry["sha256"], entry["bytes"])
        if identity in by_identity:
            chunks = list(by_identity[identity])
        elif manifest_only:
            identities, full_hash = inventory_chunks(path, entry["bytes"], chunk_bytes)
            need(full_hash == entry["sha256"], "Source changed while inventorying: " + name)
            chunks = [oid for oid, _ in identities]
            for oid, length in identities:
                manifest["objects"][oid] = {"bytes": length}
            by_identity[identity] = chunks
        else:
            chunks = []
            for offset in range(0, entry["bytes"], chunk_bytes):
                length = min(chunk_bytes, entry["bytes"] - offset)
                oid, method = write_object(root, path, offset, length, link_source, reflink)
                chunks.append(oid); manifest["objects"][oid] = {"bytes": length}; methods[method] += 1
            by_identity[identity] = chunks
        manifest["files"][name] = {**entry, "chunks": chunks}
        done += entry["bytes"]
        if done - last_report >= 1024 ** 3:
            print(json.dumps({"packedPayloadBytes": done, "files": len(manifest["files"]), "objects": len(manifest["objects"])}), file=sys.stderr, flush=True)
            last_report = done
    # A source changing during object creation must not yield a manifest which
    # claims a fully locked payload. Verify reconstruction before publication.
    if not manifest_only:
        verify(root, manifest)
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    target = guard(root / "offline" / "manifest.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    guard(target.parent)
    if target.exists():
        need(target.read_text() == text, "Preserving differing offline manifest; inspect the requested new release first")
    else:
        fd, temporary = tempfile.mkstemp(prefix=".manifest-", dir=target.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(text); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o644)
            os.link(temporary, target, follow_symlinks=False)
        finally:
            Path(temporary).unlink(missing_ok=True)
    load(root)
    return {"passed": True, "operation": "pack", "manifestOnly": manifest_only,
            "objectBytesWritten": not manifest_only, "storageMethods": methods, **summary(manifest)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "verify", "hydrate", "pack"))
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--source-root", help="Complete extracted release root; pack only")
    parser.add_argument("--chunk-bytes", type=int, default=MAX_CHUNK)
    parser.add_argument("--link-source", action="store_true", help="Pack whole-file objects using hardlinks where possible; source bytes must remain immutable")
    parser.add_argument("--reflink", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--link-objects", action="store_true", help="Hydrate immutable single-chunk files using hardlinks when their modes already match")
    parser.add_argument("--manifest-only", action="store_true", help="Pack metadata only: hash source bytes without storing objects (for space-constrained release publishers)")
    args = parser.parse_args(argv)
    root = Path(args.root).absolute()
    if args.command == "pack":
        need(args.source_root, "pack requires --source-root")
        result = pack(root, Path(args.source_root).absolute(), args.chunk_bytes, args.link_source, args.reflink, args.manifest_only)
    else:
        need(not args.manifest_only, "--manifest-only is a pack option")
        manifest = load(root)
        if args.command == "validate":
            result = {"passed": True, "operation": "validate", "objectBytesChecked": False, **summary(manifest)}
        elif args.command == "verify":
            result = verify(root, manifest)
        else:
            result = hydrate(root, manifest, args.link_objects)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
