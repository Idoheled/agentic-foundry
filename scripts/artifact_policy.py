#!/usr/bin/env python3
"""Validate receiving-agent sourcing decisions. No downloads or package-manager calls."""
import argparse
import hashlib
import json
import pathlib
import re
import sys

FILES = {
    "docker": ("payload/packages/docker-29.10.0.tgz", "archive"),
    "dockerDaemon": ("payload/packages/docker-29.10.0.tgz", "archive"),
    "compose": ("payload/packages/docker-compose-v5.8.0-linux-x86_64", "executable"),
    "omp": ("payload/binaries/omp-v19.0.1-offline.1-linux-x64", "executable"),
    "herdr": ("payload/binaries/herdr-v0.9.5-linux-x86_64", "executable"),
    "opencode": ("payload/binaries/opencode-v1.18.34-linux-x64-baseline.tar.gz", "archive"),
    "ompAdapter": ("payload/adapters/paperclip-omp-adapter-0.7.0-offline.1-runtime.tar.gz", "archive"),
}
REQUIRED_FILES = tuple(k for k in FILES if k != "dockerDaemon")
IMAGE_TAGS = {"paperclip": "agentic-offline/paperclip:2026.1117.0", "postgres": "agentic-offline/postgres:17-alpine"}
PUBLIC_REGISTRIES = {"docker.io", "index.docker.io", "registry-1.docker.io", "ghcr.io", "quay.io", "gcr.io", "public.ecr.aws", "mcr.microsoft.com"}

def digest(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def require_text(value, label):
    if not isinstance(value, str) or not value.strip() or "REPLACE_" in value:
        raise ValueError(label + " requires a factual, non-placeholder value")
    return value

class ArtifactPolicy:
    def __init__(self, root, plan):
        self.root = pathlib.Path(root).resolve()
        self.plan = plan
        if plan.get("schemaVersion") != 1:
            raise ValueError("artifact plan schemaVersion must be 1")
        checks = plan.get("privateRepositoriesChecked")
        if not isinstance(checks, list) or not checks:
            raise ValueError("Inspect internal repositories first; privateRepositoriesChecked cannot be empty")
        for check in checks:
            require_text(check, "privateRepositoriesChecked entry")
        registries = plan.get("approvedInternalRegistries", [])
        if not isinstance(registries, list):
            raise ValueError("approvedInternalRegistries must be an array of host[:port] names")
        for registry in registries:
            require_text(registry, "internal registry")
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*(?::[0-9]+)?", registry) or registry.split(":", 1)[0] in PUBLIC_REGISTRIES:
                raise ValueError("Use approved internal registry hosts only, without URLs or credentials")
        self.sums = {}
        for line in (self.root / "SHA256SUMS").read_text().splitlines():
            sha, name = line.split("  ", 1)
            self.sums[name] = sha
        self.lock = json.loads((self.root / "provenance/image-lock.json").read_text())

    @classmethod
    def from_path(cls, root, path):
        path = pathlib.Path(path).expanduser()
        if not path.is_absolute():
            raise ValueError("artifactPlan must be an absolute path to a private JSON plan")
        return cls(root, json.loads(path.read_text()))

    def decision(self, entry, label):
        if not isinstance(entry, dict):
            raise ValueError("Missing artifact selection: " + label)
        source = entry.get("source")
        if source not in ("existing", "internal", "kit"):
            raise ValueError(label + ": source must be existing, internal or kit")
        require_text(entry.get("evidence"), label + ".evidence")
        if source == "kit" and entry.get("fallbackReason") not in ("unavailable", "incompatible", "insufficient"):
            raise ValueError(label + ": kit fallback requires fallbackReason unavailable, incompatible or insufficient")
        return source

    def qualification(self, name, entry, sha):
        path = pathlib.Path(require_text(entry.get("qualificationReport"), name + ".qualificationReport")).expanduser()
        if not path.is_absolute():
            raise ValueError("qualificationReport must be absolute")
        report = json.loads(path.read_text())
        required = {"version-executes", "local-engine-compatible"}
        required.add("selected-socket-access" if name == "docker" else "compose-config-with-raw-env")
        passed = {item.get("name") for item in report.get("checks", [])
                  if item.get("passed") is True and isinstance(item.get("evidence"), str) and item["evidence"].strip()}
        if (report.get("schemaVersion") != 1 or report.get("artifact") != name or
                report.get("sha256") != sha or report.get("passed") is not True or not required.issubset(passed)):
            raise ValueError(name + ": host-tool qualification report does not cover the required checks and artifact hash")
        return {"path": str(path.resolve()), "sha256": digest(path)}

    def resolve_file(self, name):
        if name not in FILES:
            raise ValueError("Unknown artifact: " + name)
        entry = self.plan.get("files", {}).get(name)
        if name == "dockerDaemon" and entry is None:
            entry = self.plan.get("files", {}).get("docker")
        source = self.decision(entry, "files." + name)
        relative, default_format = FILES[name]
        fmt = entry.get("format", default_format)
        if fmt != default_format and not (name in ("docker", "opencode") and fmt == "executable"):
            raise ValueError(name + ": unsupported artifact format")
        baseline = self.sums.get(relative)
        if not baseline:
            raise ValueError("Missing baseline digest: " + relative)
        if name == "opencode" and fmt == "executable" and source != "kit":
            workers = json.loads((self.root / "payload/manifests/worker-artifacts.json").read_text())
            baseline = next(worker["installed_binary"]["sha256"] for worker in workers["workers"] if worker["name"] == "opencode")
        if source == "kit":
            if fmt != default_format:
                raise ValueError("Kit selections use their packaged format")
            path, expected = self.root / relative, baseline
        else:
            path = pathlib.Path(require_text(entry.get("path"), name + ".path")).expanduser()
            if not path.is_absolute():
                raise ValueError(name + ".path must be absolute")
            expected = entry.get("sha256", "")
            if not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError(name + ".sha256 must be a lowercase SHA-256 digest")
            if path.resolve().is_relative_to(self.root / "payload"):
                raise ValueError(name + ": kit payload paths must be declared as source kit")
        if not path.is_file():
            raise ValueError("Selected artifact is missing: " + name)
        actual = digest(path)
        if actual != expected:
            raise ValueError("Selected artifact SHA-256 mismatch: " + name)
        qualification = None
        if source != "kit" and (actual != baseline or (name == "docker" and fmt == "executable")):
            if name not in ("docker", "compose") or fmt != "executable":
                raise ValueError(name + ": internal artifact differs from the tested baseline; qualify it and adapt the recipe before use. A different hash alone is not a fallback reason")
            qualification = self.qualification(name, entry, actual)
        return {"source": source, "path": str(path.resolve()), "sha256": actual, "format": fmt,
                "evidence": entry["evidence"], "fallbackReason": entry.get("fallbackReason"), "qualification": qualification}

    def resolve_images(self):
        result = {}
        for name in IMAGE_TAGS:
            entry = self.plan.get("images", {}).get(name)
            source = self.decision(entry, "images." + name)
            expected = self.lock[name]["configDigest"]
            if source == "kit":
                ref = IMAGE_TAGS[name]
            else:
                ref = require_text(entry.get("imageRef"), name + ".imageRef")
                cached_id = source == "existing" and ref == expected
                if not cached_id:
                    if not re.fullmatch(r"[a-z0-9][a-z0-9.:-]*/[a-zA-Z0-9_./-]+@sha256:[0-9a-f]{64}", ref):
                        raise ValueError(name + ": use an explicit registry/repository@sha256:... image reference, or a tested existing local config ID")
                    registry = ref.split("/", 1)[0]
                    if registry not in self.plan.get("approvedInternalRegistries", []):
                        raise ValueError(name + ": image registry is not in approvedInternalRegistries")
                if entry.get("expectedConfigDigest") != expected:
                    raise ValueError(name + ": image must preserve the tested config digest; qualify a different build and adapt the recipe explicitly")
            result[name] = {"source": source, "imageRef": ref, "expectedConfigDigest": expected,
                            "evidence": entry["evidence"], "fallbackReason": entry.get("fallbackReason")}
        return result

    def resolve(self):
        images = self.resolve_images()
        files = {name: self.resolve_file(name) for name in REQUIRED_FILES}
        return {"schemaVersion": 1, "privateRepositoriesChecked": self.plan["privateRepositoriesChecked"],
                "files": files, "images": images}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--file", choices=tuple(FILES))
    args = parser.parse_args()
    policy = ArtifactPolicy.from_path(pathlib.Path(__file__).resolve().parents[1], args.plan)
    if args.file:
        selection = policy.resolve_file(args.file)
        if args.file == "dockerDaemon" and selection["format"] != "archive":
            raise ValueError("Private daemon bootstrap needs files.dockerDaemon archive selection; reuse the existing daemon otherwise")
        print(selection["path"])
    else:
        policy.resolve()
        print("PASS: sourcing plan is complete and selected file hashes match; image identities will be checked at import")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)
