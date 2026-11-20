#!/usr/bin/env python3
"""Install inspected native packages from scoped internal APT or the verified Debian13 fallback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import contextlib

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = re.compile(r"[a-z0-9][a-z0-9+.-]*(?::amd64)?(?:=[A-Za-z0-9.+:~_-]+)?\Z")

def fail(message): raise RuntimeError(message)
def read(path): return json.loads(Path(path).read_text())
def factual(value, label):
    if not isinstance(value, str) or not value.strip() or "REPLACE_" in value: fail(label + " requires factual evidence")
def state_path(value):
    path = Path(value).expanduser().absolute()
    for part in (path, *path.parents):
        if part.is_symlink(): fail("Native state and its parents cannot be symlinks")
    return path
def ensure_state(path, uid, gid):
    marker = path / "native-package-state.json"
    if path.exists():
        if not path.is_dir() or path.stat().st_uid != uid: fail("Native state must be an operator-owned directory")
        if marker.is_symlink(): fail("Native state marker cannot be a symlink")
        if marker.exists():
            if read(marker).get("uid") != uid: fail("Native state marker belongs to another operator")
        elif any(path.iterdir()): fail("Refusing an unrelated nonempty native state directory")
    else:
        path.mkdir(parents=True, mode=0o700)
        if os.geteuid() == 0: os.chown(path, uid, gid)
    if not marker.exists():
        with private_output(marker, uid, gid) as stream: json.dump({"schemaVersion": 1, "uid": uid, "gid": gid}, stream)
    path.chmod(0o700)
@contextlib.contextmanager
def private_output(path, uid, gid):
    if path.is_symlink() or (path.exists() and not path.is_file()): fail("Inspect existing native output: " + str(path))
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".writing-")
    os.fchmod(fd, 0o600)
    if os.geteuid() == 0: os.fchown(fd, uid, gid)
    try:
        with os.fdopen(fd, "w") as stream: yield stream
    finally:
        os.replace(temporary, path)
def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""): h.update(block)
    return h.hexdigest()
def system_info():
    data = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1); data[k] = v.strip('"')
    return {"id": data.get("ID"), "versionID": data.get("VERSION_ID"), "architecture": platform.machine()}
def validate(plan, actual):
    if plan.get("schemaVersion") != 1: fail("Native plan schemaVersion must be 1")
    if plan.get("expectedOS") != actual: fail("Native plan does not match the detected OS/version/architecture")
    if actual["architecture"] not in ("x86_64", "amd64"): fail("This package profile is Linux x86_64 only")
    checks = plan.get("privateRepositoriesChecked")
    if not isinstance(checks, list) or not checks or any(not isinstance(x, str) or not x.strip() or "REPLACE_" in x for x in checks):
        fail("Record actual internal repository inspection before choosing native packages")
    if not isinstance(plan.get("evidence"), str) or not plan["evidence"].strip() or "REPLACE_" in plan["evidence"]:
        fail("Native plan requires factual evidence")
    packages = plan.get("packages")
    if not isinstance(packages, list) or not packages or any(not isinstance(x, str) or not PACKAGE_NAME.fullmatch(x) for x in packages):
        fail("Use explicit native package names, optionally pinned versions; no paths or shell arguments")
    source = plan.get("source")
    if source == "kit":
        if actual["id"] != "debian" or actual["versionID"].split(".")[0] != "13":
            fail("Bundled DEBs are only for Debian13; use that host's approved internal native repository")
        if plan.get("fallbackReason") not in ("unavailable", "incompatible", "insufficient"):
            fail("Native kit fallback requires an evidenced fallbackReason")
    elif source == "internal":
        if actual["id"] not in ("debian", "ubuntu"):
            fail("This helper supports APT hosts. On other distributions use their native package manager and equivalent evidence")
        entries = plan.get("repositories"); hosts = plan.get("approvedInternalHosts")
        if not isinstance(entries, list) or not entries or not isinstance(hosts, list) or not hosts:
            fail("Internal APT requires explicit repositories and approvedInternalHosts")
        public = {"deb.debian.org", "security.debian.org", "archive.ubuntu.com", "security.ubuntu.com", "ports.ubuntu.com"}
        for entry in entries:
            raw_uri = entry.get("uri", "")
            if not isinstance(raw_uri, str) or any(ord(c) <= 32 or ord(c) == 127 for c in raw_uri):
                fail("Repository URI must not contain whitespace or control characters")
            url = urllib.parse.urlparse(raw_uri)
            if (url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment
                    or url.netloc not in hosts or url.hostname in public):
                fail("Repository URI must be approved internal HTTPS with existing credential helpers and CA trust")
            if not re.fullmatch(r"[A-Za-z0-9_./+-]+", entry.get("suite", "")): fail("Invalid repository suite")
            if not isinstance(entry.get("components"), list) or not entry["components"] or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9_./+-]+", x) for x in entry["components"]):
                fail("Repository components are required")
            signing = Path(entry.get("signedBy", ""))
            if not signing.is_absolute() or not signing.is_file() or any(c.isspace() for c in str(signing)):
                fail("Each repository needs its existing absolute signedBy keyring path without whitespace")
    else: fail("Native source must be internal or kit; adequate installed capabilities should be recorded as reused")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "plan", "apply"))
    parser.add_argument("--plan")
    parser.add_argument("--state", default=str(Path.home() / ".local/state/agentic-stack/native-packages"))
    parser.add_argument("--operator-uid", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--operator-gid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(); actual = system_info()
    if args.command == "inventory":
        names = ["git", "cc", "c++", "make", "cmake", "ninja", "pkg-config", "tmux", "rsync", "file", "strace", "lsof", "socat", "shellcheck"]
        print(json.dumps({"os": actual, "commands": {name: shutil.which(name) for name in names}}, indent=2)); return
    if not args.plan: fail("--plan is required")
    plan_path = Path(args.plan).expanduser().resolve()
    plan = read(plan_path); validate(plan, actual)
    state = state_path(args.state)  # Preserve the raw path through the privilege transition.
    uid, gid = os.getuid(), os.getgid()
    if args.command == "apply": factual(plan.get("hostRecoveryEvidence"), "hostRecoveryEvidence")
    if not shutil.which("apt-get"): fail("APT is unavailable; use the matching host package manager")
    if args.command == "apply" and os.geteuid() != 0:
        if not shutil.which("sudo"): fail("Existing administrative authority is required")
        os.execvp("sudo", ["sudo", "-n", sys.executable, "-I", str(Path(__file__).resolve()), "apply", "--plan", str(plan_path), "--state", str(state),
                          "--operator-uid", str(uid), "--operator-gid", str(gid)])
    if args.command == "apply" and os.geteuid() == 0:
        if args.operator_uid is None or args.operator_gid is None or str(args.operator_uid) != os.environ.get("SUDO_UID"):
            fail("Start through the ordinary operator; existing sudo authority is used for the package transaction")
        uid, gid = args.operator_uid, args.operator_gid
    ensure_state(state, uid, gid)
    with tempfile.TemporaryDirectory(prefix="agentic-native-", dir=state) as temporary:
        work = Path(temporary); (work / "lists/partial").mkdir(parents=True)
        (work / "archives/partial").mkdir(parents=True)
        source_file = work / "sources.list"; source_parts = work / "sources.list.d"; source_parts.mkdir()
        if plan["source"] == "kit":
            repo = ROOT / "payload/packages/debian13-amd64"
            inventory = read(ROOT / "provenance/r3-native-packages.json")
            for package in inventory["packages"]:
                if sha(repo / package["filename"]) != package["sha256"]: fail("Native checksum mismatch: " + package["package"])
            if sha(repo / "Packages") != inventory["packagesIndexSha256"]: fail("Native package index checksum mismatch")
            source_file.write_text("deb [trusted=yes] " + repo.as_uri() + " ./\n")
        else:
            lines = ["deb [arch=amd64 signed-by=" + e["signedBy"] + "] " + e["uri"] + " " + e["suite"] + " " + " ".join(e["components"])
                     for e in plan["repositories"]]
            source_file.write_text("\n".join(lines) + "\n")
        options = ["-o", "Dir::Etc::sourcelist=" + str(source_file), "-o", "Dir::Etc::sourceparts=" + str(source_parts),
                   "-o", "Dir::State::lists=" + str(work / "lists"), "-o", "Dir::Cache::archives=" + str(work / "archives"),
                   "-o", "APT::Get::List-Cleanup=false", "-o", "Acquire::http::AllowRedirect=false",
                   "-o", "Acquire::https::AllowRedirect=false"]
        env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
        log_path = state / "last-operation.log"
        with private_output(log_path, uid, gid) as log:
            def execute(argv):
                result = subprocess.run(argv, env=env, text=True, stdout=log, stderr=subprocess.STDOUT)
                if result.returncode: fail("Native operation failed; inspect private last-operation.log")
            execute(["apt-get", *options, "update"])
            simulation = subprocess.run(["apt-get", *options, "--simulate", "--no-remove", "--no-install-recommends", "install", *plan["packages"]],
                                        env=env, text=True, capture_output=True)
            log.write(simulation.stdout); log.write(simulation.stderr); log.flush()
            if simulation.returncode or re.search(r"^Remv ", simulation.stdout, re.MULTILINE):
                fail("Native package plan fails or removes packages; inspect and adjust it")
            uris = subprocess.run(["apt-get", *options, "--print-uris", "--download-only", "--yes", "--no-remove",
                                   "--no-install-recommends", "install", *plan["packages"]],
                                  env=env, text=True, capture_output=True)
            if uris.returncode: fail("Could not inspect planned native package download locations")
            for line in uris.stdout.splitlines():
                found = re.match(r"^'([^']+)' ", line)
                if not found: continue
                address = urllib.parse.urlparse(found.group(1))
                if plan["source"] == "internal":
                    if address.scheme != "https" or address.netloc not in plan["approvedInternalHosts"]:
                        fail("Native package resolved outside the approved internal repositories")
                elif address.scheme != "file" or not Path(urllib.parse.unquote(address.path)).resolve().is_relative_to(repo.resolve()):
                    fail("Native kit package resolved outside the verified local repository")
            planned = {"os": actual, "source": plan["source"], "requestedPackages": plan["packages"],
                       "simulation": simulation.stdout, "globalSourcesModified": False}
            if args.command == "apply":
                execute(["apt-get", *options, "--yes", "--no-remove", "--no-install-recommends",
                         "-o", "Dpkg::Options::=--force-confold", "install", *plan["packages"]])
                result = subprocess.run(["dpkg-query", "-W", "-f=${Package}\t${Version}\t${db:Status-Status}\n",
                                         *[x.split("=")[0] for x in plan["packages"]]], text=True, capture_output=True, check=True)
                rows = [line.split("\t") for line in result.stdout.splitlines()]
                expected = {x.split("=")[0].split(":")[0] for x in plan["packages"]}
                installed = {row[0].split(":")[0] for row in rows if len(row) == 3 and row[2] == "installed"}
                if not expected.issubset(installed): fail("Native package postcheck did not report all requested packages installed")
                planned.update(applied=True, installed=result.stdout)
            else: planned["applied"] = False
        report = state / ("installed.json" if args.command == "apply" else "plan.json")
        with private_output(report, uid, gid) as stream: json.dump(planned, stream, indent=2); stream.write("\n")
        print(("Installed and recorded native packages" if args.command == "apply" else "Recorded native simulation") + ": " + str(report))
        print("Package-manager changes need the documented host recovery procedure; they are not an atomic rollback.")

if __name__ == "__main__":
    try: main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr); sys.exit(1)
