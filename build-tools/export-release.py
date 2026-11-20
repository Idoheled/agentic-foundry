#!/usr/bin/env python3
"""Export a clean tagged checkout + hydrated payload as one verified standalone tar.

Git metadata, local/private state and offline LFS object storage are excluded.
The original runtime layout and setup.sh remain usable without Git or LFS.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import offline_payload as payload
import source_integrity


def export(root, output, ref, prefix=None):
    root = payload.guard(root); output = payload.guard(output)
    payload.need((root / ".git").exists(), "Export requires a Git checkout with a recorded release tag")
    payload.need(isinstance(ref, str) and ref.startswith("v") and source_integrity.SEMVER.fullmatch(ref[1:]), "Use an explicit semantic release tag, such as v0.1.0")
    payload.need(not output.exists(), "Preserving existing export: " + str(output))
    head = source_integrity.git(root, "rev-parse", "HEAD").strip()
    tagged = source_integrity.git(root, "rev-parse", "refs/tags/" + ref + "^{commit}").strip()
    payload.need(head == tagged, "Checkout HEAD differs from the requested release tag")
    payload.need(not source_integrity.git(root, "status", "--porcelain=v1", "--untracked-files=normal").strip(), "Export requires a clean source checkout")
    result, controls, manifest = source_integrity.check(root, with_payload=True)
    version = controls["version"]
    payload.need(ref == "v" + version, "Release tag differs from VERSION")
    prefix = prefix or "agentic-foundry-" + version
    payload.need(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", prefix) and prefix not in (".", ".."), "Unsafe archive prefix")
    output.parent.mkdir(parents=True, exist_ok=True); payload.guard(output.parent)
    temporary = output.with_name(output.name + ".writing")
    payload.need(not temporary.exists(), "Inspect a prior incomplete export before retrying")
    expected = dict(controls["files"])
    expected[source_integrity.INVENTORY] = {"sha256": payload.digest(root / source_integrity.INVENTORY), "bytes": (root / source_integrity.INVENTORY).stat().st_size, "mode": 0o644}
    expected[source_integrity.SUMS] = {"sha256": payload.digest(root / source_integrity.SUMS), "bytes": (root / source_integrity.SUMS).stat().st_size, "mode": 0o644}
    expected.update({name: {key: entry[key] for key in ("sha256", "bytes", "mode")} for name, entry in manifest["files"].items()})
    total = 0
    try:
        with temporary.open("xb") as raw:
            with gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=5, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                    for name in sorted(expected):
                        entry = expected[name]; path = payload.regular(root / name)
                        info = tarfile.TarInfo(prefix + "/" + name)
                        info.size = entry["bytes"]; info.mode = entry["mode"]; info.mtime = 0
                        info.uid = info.gid = 0; info.uname = info.gname = "root"
                        with path.open("rb") as stream:
                            archive.addfile(info, stream)
                        total += info.size
        os.replace(temporary, output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    observed = set()
    with tarfile.open(output, "r|gz") as archive:
        for member in archive:
            payload.need(member.isfile() and member.name.startswith(prefix + "/"), "Unexpected export archive entry")
            name = member.name[len(prefix) + 1:]
            payload.need(name in expected and name not in observed, "Unexpected or duplicate export member: " + name)
            observed.add(name); entry = expected[name]
            digest = hashlib.sha256()
            with archive.extractfile(member) as stream:
                for block in iter(lambda: stream.read(payload.BLOCK), b""):
                    digest.update(block)
            payload.need(member.size == entry["bytes"] and member.mode == entry["mode"] and digest.hexdigest() == entry["sha256"], "Exported member differs: " + name)
    payload.need(observed == set(expected), "Export is missing files")
    sha = payload.digest(output)
    report = {"passed": True, "sourceVersion": version, "sourceTag": ref, "sourceCommit": head,
              "payloadRelease": manifest["release"], "archive": output.name,
              "sha256": sha, "bytes": output.stat().st_size, "uncompressedFileBytes": total,
              "regularFilesVerified": len(observed), "payloadFiles": len(manifest["files"]),
              "gitMetadataIncluded": False, "duplicateLfsObjectsIncluded": False,
              "scope": "Source integrity, hydrated payload identities and every exported archive member; not target deployment acceptance"}
    Path(str(output) + ".sha256").write_text(sha + "  " + output.name + "\n")
    Path(str(output) + ".validation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", required=True)
    parser.add_argument("--ref", required=True, help="Exact local tag matching VERSION and HEAD")
    parser.add_argument("--prefix")
    args = parser.parse_args(argv)
    print(json.dumps(export(Path(args.root).absolute(), Path(args.output).absolute(), args.ref, args.prefix), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
