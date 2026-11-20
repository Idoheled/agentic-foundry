#!/usr/bin/env python3
"""Builder: identify executable/archive members without executing upstream code."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(block)
    return value.hexdigest()


def identities(root, catalog):
    result = {}
    for name, tool in catalog["tools"].items():
        artifact = tool.get("artifact")
        if not artifact:
            continue
        path = root / artifact["path"]
        commands = {command: value if isinstance(value, str) else value["path"] for command, value in tool.get("commands", {}).items()}
        wanted = set(commands.values()) | ({"ASSET_MANIFEST.json"} if tool.get("kind") == "asset-tree" else set())
        found = {}
        strip = artifact.get("stripComponents", 0)
        if artifact["format"] == "file":
            with path.open("rb") as stream:
                value = digest(stream)
            found.update({target: value for target in wanted})
        elif artifact["format"] == "tar":
            with tarfile.open(path, "r:*") as archive:
                mapping = {}
                for member in archive.getmembers():
                    parts = PurePosixPath(member.name).parts[strip:]
                    if parts:
                        mapping[str(PurePosixPath(*parts))] = member
                for target in wanted:
                    member = mapping.get(target)
                    if member:
                        stream = archive.extractfile(member)
                        if stream:
                            with stream:
                                found[target] = digest(stream)
        elif artifact["format"] == "zip":
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    target = str(PurePosixPath(*PurePosixPath(member.filename).parts[strip:]))
                    if target in wanted:
                        with archive.open(member) as stream:
                            found[target] = digest(stream)
        missing = wanted - set(found)
        if missing:
            raise ValueError(name + " missing members: " + str(sorted(missing)))
        result[name] = {"artifactSha256": artifact["sha256"], "commands": {command: found[target] for command, target in commands.items()},
                        "files": {target: found[target] for target in wanted if target not in commands.values()}}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--catalog", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    result = {}
    for catalog in args.catalog:
        result.update(identities(root, json.loads(Path(catalog).read_text())))
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"tools": len(result), "output": args.output}))
