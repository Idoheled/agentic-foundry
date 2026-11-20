#!/usr/bin/env python3
"""Provision inspected, source-selected host tools. Python 3.9+, standard library only."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid
import zipfile

SCHEMA = 1
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,99}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")


class Blocked(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Blocked(message)


def factual(value, label):
    require(isinstance(value, str) and value.strip() and "REPLACE_" not in value, label + " needs factual evidence")
    return value


def digest(path):
    value = hashlib.sha256()
    with pathlib.Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path):
    return json.loads(pathlib.Path(path).read_text())


def atomic_json(path, value, owner=None):
    path = pathlib.Path(path)
    require(not path.is_symlink(), "Refusing managed JSON symlink: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".writing-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        if owner and os.geteuid() == 0:
            os.chown(temporary, *owner)
        os.replace(temporary, path)
    finally:
        pathlib.Path(temporary).unlink(missing_ok=True)


def snapshot(path):
    path = pathlib.Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"kind": "missing"}
    result = {"uid": info.st_uid, "gid": info.st_gid, "mode": stat.S_IMODE(info.st_mode)}
    if stat.S_ISLNK(info.st_mode):
        result.update(kind="symlink", target=os.readlink(path))
    elif stat.S_ISREG(info.st_mode):
        result.update(kind="file", sha256=digest(path), size=info.st_size)
    elif stat.S_ISDIR(info.st_mode):
        result["kind"] = "directory"
    else:
        result["kind"] = "special"
    return result


def copy_preserving_owner(source, destination):
    shutil.copy2(source, destination, follow_symlinks=False)
    if os.geteuid() == 0:
        info = pathlib.Path(source).lstat()
        os.chown(destination, info.st_uid, info.st_gid, follow_symlinks=False)


def matches(actual, expected):
    if not isinstance(expected, dict) or actual.get("kind") != expected.get("kind"):
        return False
    mandatory = {"file": ("sha256", "uid"), "symlink": ("target", "uid"), "missing": ()}
    if actual["kind"] not in mandatory or any(key not in expected for key in mandatory[actual["kind"]]):
        return False
    return all(actual.get(key) == value for key, value in expected.items())


def relative(value):
    require(isinstance(value, str) and value and "\\" not in value, "Expected a relative POSIX path")
    path = pathlib.PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and str(path) != ".", "Unsafe relative path: " + value)
    return path


def safe_parents(path):
    for ancestor in [path.parent, *path.parents]:
        require(not ancestor.is_symlink(), "Inspect symlinked installation parent before continuing: " + str(ancestor))


def contained(path, root):
    return pathlib.Path(path).resolve().is_relative_to(pathlib.Path(root).resolve())


def archive_tree(archive, destination, fmt, strip=0):
    """Extract regular files first, then validated relative links; no devices or traversal."""
    require(isinstance(strip, int) and 0 <= strip <= 20, "Invalid stripComponents")
    destination = pathlib.Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    entries, seen = [], set()

    def add(name, kind, mode, data=None, link=None):
        original = relative(name.rstrip("/"))
        if len(original.parts) <= strip:
            return
        rel = pathlib.PurePosixPath(*original.parts[strip:])
        require(str(rel) not in seen, "Duplicate archive destination: " + str(rel))
        seen.add(str(rel))
        require(kind in ("file", "dir", "symlink", "hardlink"), "Unsupported archive entry: " + name)
        if kind == "symlink":
            require(isinstance(link, str) and link and not pathlib.PurePosixPath(link).is_absolute() and "\\" not in link,
                    "Absolute or invalid archive symlink: " + name)
            require(contained(destination / rel.parent / link, destination), "Archive symlink escapes tree: " + name)
        if kind == "hardlink":
            target = relative(link)
            require(len(target.parts) > strip, "Invalid stripped hardlink")
            link = str(pathlib.PurePosixPath(*target.parts[strip:]))
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if kind == "dir":
            target.mkdir(exist_ok=True)
        elif kind == "file":
            with target.open("xb") as stream:
                shutil.copyfileobj(data, stream, length=1024 * 1024)
            target.chmod(0o755 if mode & 0o111 else 0o644)
        entries.append((rel, kind, mode, None, link))

    if fmt == "tar":
        with tarfile.open(archive, "r:*") as bundle:
            for member in bundle:
                if member.name.rstrip("/") in ("", "."):
                    continue
                kind = "file" if member.isfile() else "dir" if member.isdir() else "symlink" if member.issym() else "hardlink" if member.islnk() else "unsupported"
                if member.isfile():
                    with bundle.extractfile(member) as source:
                        add(member.name, kind, member.mode, source, member.linkname)
                else:
                    add(member.name, kind, member.mode, None, member.linkname)
    elif fmt == "zip":
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                mode = member.external_attr >> 16
                is_link = stat.S_ISLNK(mode)
                if is_link:
                    require(member.file_size <= 4096, "Oversized archive symlink")
                    add(member.filename, "symlink", mode, None, bundle.read(member).decode("utf-8"))
                elif member.is_dir():
                    add(member.filename, "dir", mode)
                else:
                    with bundle.open(member) as source:
                        add(member.filename, "file", mode, source)
    else:
        raise Blocked("Unsupported archive format: " + fmt)
    pending = [(rel, link) for rel, kind, _, _, link in entries if kind == "hardlink"]
    while pending:
        remaining = []
        for rel, link in pending:
            target = destination / link
            if target.is_file() and not target.is_symlink():
                os.link(target, destination / rel)
            else:
                remaining.append((rel, link))
        require(len(remaining) < len(pending), "Unresolvable archive hardlink")
        pending = remaining
    for rel, kind, _, _, link in entries:
        if kind == "symlink":
            os.symlink(link, destination / rel)
    for target in destination.rglob("*"):
        require(contained(target, destination), "Resolved archive link escapes installation: " + str(target))
        if target.is_dir() and not target.is_symlink():
            target.chmod(0o755)


def tree_identity(root):
    records = []
    for path in sorted(pathlib.Path(root).rglob("*")):
        item = snapshot(path)
        item.pop("uid", None)
        item.pop("gid", None)
        records.append([str(path.relative_to(root)), item])
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


class Host:
    def __init__(self, args):
        self.args = args
        self.prefix = pathlib.Path(args.prefix).resolve() if args.prefix else None
        self.home = pathlib.Path(args.operator_home or str(pathlib.Path.home()))
        self.owner = (args.operator_uid if args.operator_uid is not None else os.getuid(),
                      args.operator_gid if args.operator_gid is not None else os.getgid())
        self.base = pathlib.Path("/opt/agentic-stack") if args.mode == "system" else self.home / ".local/share/agentic-stack"
        self.bin = pathlib.Path("/usr/local/bin") if args.mode == "system" else self.home / ".local/bin"
        raw_state = pathlib.Path(args.state).expanduser().absolute()
        require(not raw_state.is_symlink(), "State directory must not be a symlink")
        safe_parents(raw_state / "placeholder")
        self.state = raw_state.resolve()

    def path(self, logical):
        logical = pathlib.Path(logical)
        require(logical.is_absolute() and ".." not in logical.parts, "Host path must be absolute and normalized")
        return self.prefix / str(logical).lstrip("/") if self.prefix else logical

    def package_owner(self, logical):
        if self.prefix:
            owners = getattr(self.args, "package_owners", None)
            return (read_json(owners) if owners else {}).get(str(logical))
        if shutil.which("dpkg-query"):
            result = subprocess.run(["dpkg-query", "--search", str(logical)], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        if shutil.which("rpm"):
            result = subprocess.run(["rpm", "-qf", "--", str(logical)], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        return None

    def save(self, path, value):
        path = pathlib.Path(path).absolute()
        require(path.resolve().is_relative_to(self.state), "Reports and receipts must be saved inside the selected state directory")
        safe_parents(path)
        self.ensure_state()
        atomic_json(path, value, self.owner)

    def ensure_state(self):
        safe_parents(self.state / "placeholder")
        require(not self.state.is_symlink(), "State directory cannot be a symlink")
        created = not self.state.exists()
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        if created and os.geteuid() == 0:
            os.chown(self.state, *self.owner)
        require(self.state.is_dir() and self.state.stat().st_uid == self.owner[0], "State must belong to the intended operator; unrelated system directories are not installation state")
        marker = self.state / "hostctl-state.json"
        require(not marker.is_symlink(), "State marker cannot be a symlink")
        if marker.exists():
            data = read_json(marker)
            require(data.get("schemaVersion") == SCHEMA and data.get("operatorUid") == self.owner[0] and data.get("mode") == self.args.mode,
                    "State belongs to a different operator/mode")
        else:
            require(not any(self.state.iterdir()), "Refusing to populate an unrelated nonempty state directory")
            atomic_json(marker, {"schemaVersion": SCHEMA, "operatorUid": self.owner[0], "mode": self.args.mode}, self.owner)

    def load_inputs(self):
        catalog, plan = read_json(self.args.catalog), read_json(self.args.plan)
        require(catalog.get("schemaVersion") == SCHEMA and plan.get("schemaVersion") == SCHEMA, "Unsupported catalog/plan schema")
        checks = plan.get("privateRepositoriesChecked")
        require(isinstance(checks, list) and checks, "Inspect private repositories before selecting artifacts")
        for check in checks:
            factual(check, "privateRepositoriesChecked")
        require(isinstance(plan.get("tools"), dict) and plan["tools"], "Select at least one tool")
        resolved = {}
        for name, choice in plan["tools"].items():
            require(NAME.fullmatch(name), "Invalid tool name")
            require(name in catalog.get("tools", {}), "Tool is absent from catalog: " + name)
            tool = catalog["tools"][name]
            if tool.get("kind") == "native-package-group":
                resolved[name] = {"kind": "native-package-group", "catalog": tool, "choice": choice}
                continue
            asset_tree = tool.get("kind") == "asset-tree"
            environment = tool.get("environment", {})
            require(isinstance(environment, dict) and all(isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) and
                    isinstance(value, str) and "\x00" not in value for key, value in environment.items()),
                    "Catalog environment must map valid variable names to literal non-NUL strings")
            defaults = tool.get("environmentDefaults", {})
            require(isinstance(defaults, dict) and all(isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) and
                    isinstance(value, str) and "\x00" not in value for key, value in defaults.items()),
                    "Catalog environmentDefaults must map variable names to literal non-NUL strings")
            if asset_tree:
                require(tool.get("commands", {}) == {}, "Asset trees do not define executable commands")
                require(isinstance(tool.get("requiredPaths"), list) and tool["requiredPaths"], "Asset trees require explicit requiredPaths")
                require(not choice.get("canonicalLinks"), "Asset trees do not create command links")
            source = choice.get("source")
            require(source in ("existing", "internal", "kit"), "Invalid source for " + name)
            factual(choice.get("evidence"), name + ".evidence")
            if source == "kit":
                require(choice.get("fallbackReason") in ("unavailable", "incompatible", "insufficient"), "Kit fallback requires a reason: " + name)
            commands = {}
            for command, value in tool.get("commands", {}).items():
                require(NAME.fullmatch(command), "Invalid command name")
                value = {"path": value} if isinstance(value, str) else dict(value)
                relative(value["path"])
                verify = value.get("verifyArgs", tool.get("verifyArgs", ["--version"]))
                require(isinstance(verify, list) and all(isinstance(arg, str) and "\x00" not in arg for arg in verify), "verifyArgs must be an argv array")
                value["verifyArgs"] = verify
                commands[command] = value
            require(commands or asset_tree, "Tool has no commands: " + name)
            version = str(choice.get("version", tool.get("version", "")))
            require(NAME.fullmatch(version), "Tool needs a safe version identifier: " + name)
            reuse = source == "existing" and not choice.get("normalizePath", False)
            require(not asset_tree or not reuse, "Asset trees require a complete archive, not executable reuse")
            record = {"name": name, "source": source, "version": version, "commands": commands,
                      "catalog": tool, "choice": choice, "reuse": reuse}
            if reuse:
                require(choice.get("adequate") is True, "Existing reuse needs an explicit adequacy finding: " + name)
                selected = choice.get("executables", {})
                if len(commands) == 1 and not selected:
                    selected = {next(iter(commands)): {"path": choice.get("path"), "sha256": choice.get("sha256")}}
                for command in commands:
                    selected_path = pathlib.Path(selected.get(command, {}).get("path", ""))
                    require(selected_path.is_absolute(), "Existing executable path must be absolute: " + command)
                    physical = self.path(selected_path)
                    expected = selected[command].get("sha256", "")
                    require(SHA.fullmatch(expected) and physical.is_file() and digest(physical) == expected,
                            "Existing executable identity differs: " + command)
                    require(os.access(physical, os.X_OK), "Existing command is not executable: " + command)
                record["executables"] = selected
            else:
                artifact = dict(tool.get("artifact", {}))
                if source == "kit":
                    path = pathlib.Path(self.args.payload_root).resolve() / relative(artifact["path"])
                    require(contained(path, self.args.payload_root), "Kit artifact escapes payload root")
                else:
                    artifact.update({key: choice[key] for key in ("format", "stripComponents", "destination", "sha256") if key in choice})
                    path = pathlib.Path(choice.get("path", ""))
                    require(path.is_absolute(), "Selected artifact path must be absolute: " + name)
                    if source == "existing":
                        path = self.path(path)
                    else:
                        require(not contained(path, self.args.payload_root), "Kit payload must be declared as source kit")
                expected = artifact.get("sha256", "")
                require(SHA.fullmatch(expected) and path.is_file() and digest(path) == expected, "Artifact SHA-256 mismatch or missing artifact: " + name)
                require(artifact.get("format") in ("file", "tar", "zip"), "Unsupported artifact format: " + name)
                require(not asset_tree or artifact.get("format") == "tar", "Asset trees require a tar archive")
                artifact["path"] = str(path.resolve())
                record["artifact"] = artifact
                record["installPath"] = str(self.base / "tools" / name / (version + "-" + expected[:12]))
            resolved[name] = record
        return catalog, plan, resolved

    def index(self):
        path = self.state / "managed-launchers.json"
        require(not path.is_symlink(), "Managed launcher index cannot be a symlink")
        return read_json(path) if path.exists() else {}

    def inspect_destination(self, logical, expected=None, reason=None, owned=False):
        actual_path = self.path(logical)
        safe_parents(actual_path)
        current = snapshot(actual_path)
        require(current["kind"] in ("missing", "file", "symlink"), "Refusing directory/special command occupant: " + str(logical))
        package = self.package_owner(logical)
        require(not package, "Package-owned path requires the native package manager: " + str(logical))
        if current["kind"] != "missing":
            require(matches(current, expected), "Existing command changed or lacks an inspection snapshot: " + str(logical))
            if not owned:
                factual(reason, "replacement reason for " + str(logical))
        elif expected is not None:
            require(matches(current, expected), "Destination changed after inspection: " + str(logical))
        return current

    def destination_plan(self, resolved):
        index, destinations, taken = self.index(), [], set()
        for name, tool in resolved.items():
            if tool.get("kind") == "native-package-group":
                continue
            choice = tool["choice"]
            for command in tool["commands"]:
                logical = self.bin / ("agentic-" + command)
                known = index.get(str(logical), {})
                expected = choice.get("namespaceExpected", {}).get(command, known.get("snapshot"))
                current = self.inspect_destination(logical, expected, choice.get("replaceReason"), bool(known))
                require(str(logical) not in taken, "Duplicate command destination")
                taken.add(str(logical))
                destinations.append({"tool": name, "command": command, "path": str(logical), "before": current, "kind": "launcher", "previousManagedRecord": known})
            for link in choice.get("canonicalLinks", []):
                logical = pathlib.Path(link["path"])
                require(logical.parent == self.bin and NAME.fullmatch(logical.name), "Canonical links must use the selected local bin directory; OS paths need native package management")
                command = link.get("command", next(iter(tool["commands"])))
                require(command in tool["commands"], "Unknown canonical command")
                known = index.get(str(logical), {})
                expected = known.get("snapshot", link.get("expected"))
                current = self.inspect_destination(logical, expected, link.get("replaceReason"), bool(known))
                require(str(logical) not in taken, "Duplicate command destination")
                taken.add(str(logical))
                destinations.append({"tool": name, "command": command, "path": str(logical), "before": current, "kind": "canonical", "previousManagedRecord": known})
        return destinations

    def platform_check(self, resolved):
        import platform
        actual_arch = platform.machine()
        libc_name, libc_version = platform.libc_ver()
        os_release = {}
        release_file = pathlib.Path("/etc/os-release")
        if release_file.is_file():
            for line in release_file.read_text().splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    os_release[key] = value.strip('"')
        for name, tool in resolved.items():
            platform_rule = tool.get("catalog", {}).get("platform", {})
            arches = platform_rule.get("architectures", [])
            require(not arches or actual_arch in arches, "Unsupported architecture for " + name)
            required = platform_rule.get("glibcMin")
            if required:
                require(libc_name == "glibc" and tuple(map(int, libc_version.split("."))) >= tuple(map(int, required.split("."))),
                        "Host glibc does not meet the catalog requirement for " + name)
            if platform_rule.get("osIds"):
                require(os_release.get("ID") in platform_rule["osIds"], "This OS needs its own qualified native dependencies for " + name)
            if platform_rule.get("osVersionMajor"):
                require(os_release.get("VERSION_ID", "").split(".")[0] in platform_rule["osVersionMajor"],
                        "This OS version needs its own qualified native dependencies for " + name)

    def validate(self):
        catalog, plan, resolved = self.load_inputs()
        self.platform_check(resolved)
        return {"schemaVersion": SCHEMA, "mode": self.args.mode, "tools": resolved,
                "destinations": self.destination_plan(resolved), "privateRepositoriesChecked": plan["privateRepositoriesChecked"],
                "nativeHandoffs": [name for name, tool in resolved.items() if tool.get("kind") == "native-package-group"]}

    def inventory(self):
        catalog = read_json(self.args.catalog)
        result = {"schemaVersion": SCHEMA, "mode": self.args.mode, "tools": {}}
        for name, tool in catalog.get("tools", {}).items():
            commands = {}
            for command in tool.get("commands", {}):
                locations = [self.bin / ("agentic-" + command), self.bin / command, pathlib.Path("/usr/bin") / command]
                if not self.prefix:
                    discovered = shutil.which(command)
                    if discovered and pathlib.Path(discovered) not in locations:
                        locations.append(pathlib.Path(discovered))
                records = []
                for logical in locations:
                    physical = self.path(logical)
                    record = {"path": str(logical), "snapshot": snapshot(physical), "packageOwner": self.package_owner(logical)}
                    if physical.is_file():
                        record.update(resolvedPath=str(physical.resolve()), executableSha256=digest(physical))
                    records.append(record)
                commands[command] = records
            result["tools"][name] = commands
        return result

    def run_check(self, executable, command, env=None):
        try:
            result = subprocess.run([str(executable), *command["verifyArgs"]], capture_output=True, text=True,
                                    timeout=command.get("verifyTimeoutSeconds", 30), env=env)
            output = (result.stdout + result.stderr)[-12000:]
            pattern = command.get("verifyPattern")
            passed = result.returncode == 0 and (not pattern or re.search(pattern, output) is not None)
            return {"passed": passed, "exitCode": result.returncode, "output": output,
                    "executable": str(executable), "argv": command["verifyArgs"]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"passed": False, "error": str(exc), "executable": str(executable)}

    def tool_env(self, tool, root=None):
        env = os.environ.copy()
        for key, value in tool["catalog"].get("environmentDefaults", {}).items():
            env.setdefault(key, value)
        env.update(tool["catalog"].get("environment", {}))
        if root is None:
            paths = [str(self.path(value)) for value in tool["choice"].get("pathEntries", [])]
        else:
            entries = tool["catalog"].get("pathEntries", ["bin"])
            paths = [str(root / relative(value)) for value in entries]
        env["PATH"] = os.pathsep.join(paths + [env.get("PATH", "/usr/bin:/bin")])
        return env

    def stage_tool(self, name, tool, receipt_id):
        if tool["reuse"]:
            checks = {command: self.run_check(self.path(selected["path"]), tool["commands"][command], self.tool_env(tool))
                      for command, selected in tool["executables"].items()}
            require(all(check["passed"] for check in checks.values()), "Existing tool failed verification: " + name)
            return {"reuse": True, "executables": tool["executables"], "checks": checks}
        logical = pathlib.Path(tool["installPath"])
        final = self.path(logical)
        safe_parents(final)
        with tempfile.TemporaryDirectory(prefix="agentic-stage-") as temporary:
            stage = pathlib.Path(temporary) / "tree"
            stage.mkdir()
            artifact = tool["artifact"]
            if artifact["format"] == "file":
                require(len(tool["commands"]) == 1 or artifact.get("destination"), "Raw multi-command tool needs destination")
                target = stage / relative(artifact.get("destination", next(iter(tool["commands"].values()))["path"]))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(artifact["path"], target)
                target.chmod(0o755)
            else:
                archive_tree(artifact["path"], stage, artifact["format"], artifact.get("stripComponents", 0))
            for command in tool["commands"].values():
                executable = stage / relative(command["path"])
                require(executable.is_file() and contained(executable, stage), "Missing or escaping tool executable: " + str(executable))
                executable.chmod(0o755)
            for needed in tool["catalog"].get("requiredPaths", []):
                dependency = stage / relative(needed)
                require(dependency.exists() and contained(dependency, stage), "Required tool dependency is absent or escapes the tree: " + needed)
            identity = tree_identity(stage)
            if final.exists() or final.is_symlink():
                require(final.is_dir() and not final.is_symlink() and tree_identity(final) == identity,
                        "Existing versioned installation differs; preserve and inspect: " + str(logical))
            else:
                final.parent.mkdir(parents=True, exist_ok=True)
                staging = final.with_name(final.name + ".staging-" + receipt_id)
                shutil.copytree(stage, staging, symlinks=True)
                os.rename(staging, final)
        checks = {command: self.run_check(final / value["path"], value, self.tool_env(tool, final))
                  for command, value in tool["commands"].items()}
        require(all(check["passed"] for check in checks.values()), "Staged tool failed verification; no command entry point promoted: " + name)
        return {"reuse": False, "installPath": str(logical), "treeSha256": identity, "checks": checks}

    def launcher(self, tool, staged, command):
        if staged["reuse"]:
            executable = self.path(staged["executables"][command]["path"])
            paths = tool["choice"].get("pathEntries", [])
            paths = [str(self.path(path)) for path in paths]
        else:
            root = self.path(staged["installPath"])
            executable = root / tool["commands"][command]["path"]
            paths = [str(root / relative(path)) for path in tool["catalog"].get("pathEntries", ["bin"])]
        text = "#!/bin/sh\nset -eu\n"
        for key, value in sorted(tool["catalog"].get("environmentDefaults", {}).items()):
            text += 'if [ "${' + key + '+x}" != x ]; then export ' + key + "=" + shlex.quote(value) + "; fi\n"
        for key, value in sorted(tool["catalog"].get("environment", {}).items()):
            text += "export " + key + "=" + shlex.quote(value) + "\n"
        if paths:
            text += "export PATH=" + shlex.quote(os.pathsep.join(paths)) + ':"${PATH:-/usr/bin:/bin}"\n'
        text += "exec " + shlex.quote(str(executable)) + ' "$@"\n'
        return text

    def promote(self, item, tool, staged, receipt):
        path = self.path(item["path"])
        require(snapshot(path) == item["before"], "Destination changed during staging: " + item["path"])
        safe_parents(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        action = dict(item)
        if item["before"]["kind"] != "missing":
            backup_logical = self.base / "hostctl-backups" / receipt["id"] / str(len(receipt["actions"]))
            backup = self.path(backup_logical)
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            copy_preserving_owner(path, backup)
            action["backupPath"] = str(backup_logical)
        temporary = path.with_name(path.name + ".installing-" + uuid.uuid4().hex)
        try:
            if item["kind"] == "launcher":
                temporary.write_text(self.launcher(tool, staged, item["command"]))
                temporary.chmod(0o755)
            else:
                os.symlink(self.path(self.bin / ("agentic-" + item["command"])), temporary)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        action["after"] = snapshot(path)
        receipt["actions"].append(action)
        self.save(self.state / "receipts" / (receipt["id"] + ".json"), receipt)

    def apply(self):
        plan = self.validate()
        receipt = {"schemaVersion": SCHEMA, "id": dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8],
                   "mode": self.args.mode, "operatorUid": self.owner[0], "operatorGid": self.owner[1],
                   "catalogSha256": digest(self.args.catalog), "planSha256": digest(self.args.plan),
                   "status": "applying", "actions": [], "tools": {}, "retirements": [], "blockers": []}
        receipt_path = self.state / "receipts" / (receipt["id"] + ".json")
        self.save(receipt_path, receipt)
        try:
            for name, tool in plan["tools"].items():
                if tool.get("kind") == "native-package-group":
                    receipt["blockers"].append(name + ": native package group requires its target-distro package helper; no OS files were replaced")
                    continue
                staged = self.stage_tool(name, tool, receipt["id"])
                receipt["tools"][name] = {"selection": tool, "staged": staged}
            for item in plan["destinations"]:
                tool = receipt["tools"][item["tool"]]
                self.promote(item, tool["selection"], tool["staged"], receipt)
            checks = self.verify_receipt(receipt)
            require(checks["passed"], "Promoted command failed verification; inspect receipt and roll back")
            receipt["verification"] = checks
            receipt["status"] = "installed_with_blockers" if receipt["blockers"] else "installed_and_verified"
            index = self.index()
            for action in receipt["actions"]:
                index[action["path"]] = {"snapshot": action["after"], "receipt": receipt["id"]}
            self.save(self.state / "managed-launchers.json", index)
            self.save(self.state / "latest.json", {"receipt": str(receipt_path)})
        except Exception as exc:
            receipt["status"] = "failed"
            receipt["blockers"].append(str(exc))
            self.save(receipt_path, receipt)
            raise
        self.save(receipt_path, receipt)
        return {"receipt": str(receipt_path), "status": receipt["status"], "passed": not receipt["blockers"], "verification": receipt["verification"], "blockers": receipt["blockers"]}

    def receipt(self):
        path = pathlib.Path(self.args.receipt) if self.args.receipt else pathlib.Path(read_json(self.state / "latest.json")["receipt"])
        require(path.resolve().is_relative_to(self.state), "Receipt must be inside the selected state directory")
        require(not path.is_symlink(), "Receipt cannot be a symlink")
        receipt = read_json(path)
        require(receipt.get("mode") == self.args.mode and receipt.get("operatorUid") == self.owner[0], "Receipt belongs to a different mode/operator")
        return path, receipt

    def verify_receipt(self, receipt):
        checks = []
        for name, record in receipt["tools"].items():
            staged, tool = record["staged"], record["selection"]
            root = None
            if not staged["reuse"]:
                root = self.path(staged["installPath"])
                checks.append({"tool": name, "check": "installed-tree-identity", "passed": root.is_dir() and tree_identity(root) == staged["treeSha256"]})
            for command, spec in tool["commands"].items():
                if staged["reuse"]:
                    selected = staged["executables"][command]
                    original = self.path(selected["path"])
                    checks.append({"tool": name, "check": "reused-file-identity", "passed": original.is_file() and digest(original) == selected["sha256"]})
                launcher = self.path(self.bin / ("agentic-" + command))
                result = self.run_check(launcher, spec, self.tool_env(tool, root))
                result.update(tool=name, check="namespaced-command", command=command)
                checks.append(result)
                fresh_env = self.tool_env(tool, root)
                fresh_env["PATH"] = str(self.path(self.bin)) + ":" + fresh_env["PATH"]
                shell_spec = dict(spec)
                shell_spec["verifyArgs"] = ["-c", 'command -v "$1" && shift && exec "$@"', "hostctl", "agentic-" + command, "agentic-" + command, *spec["verifyArgs"]]
                fresh = self.run_check("/bin/sh", shell_spec, fresh_env)
                fresh.update(tool=name, check="fresh-shell-command", command=command)
                checks.append(fresh)
        for action in receipt["actions"]:
            checks.append({"check": "entry-point-identity", "path": action["path"], "passed": snapshot(self.path(action["path"])) == action["after"]})
            if action["kind"] == "canonical":
                spec = receipt["tools"][action["tool"]]["selection"]["commands"][action["command"]]
                result = self.run_check(self.path(action["path"]), spec)
                result.update(check="canonical-command", path=action["path"])
                checks.append(result)
        return {"passed": bool(checks) and all(item["passed"] for item in checks), "checks": checks}

    def verify(self):
        path, receipt = self.receipt()
        result = self.verify_receipt(receipt)
        receipt["verification"] = result
        self.save(path, receipt)
        return result

    def check(self):
        """Verify the bound installation without rewriting its immutable receipt."""
        unused_path, receipt = self.receipt()
        return self.verify_receipt(receipt)

    def retire(self):
        path, receipt = self.receipt()
        require(self.verify_receipt(receipt)["passed"], "Replacement commands must verify before retirement")
        blockers = []
        for name, record in receipt["tools"].items():
            for request in record["selection"]["choice"].get("retire", []):
                old = pathlib.Path(request["path"])
                physical = self.path(old)
                try:
                    require(old.is_absolute(), "Retirement path must be absolute")
                    safe_parents(physical)
                    prior = next((item for item in receipt["retirements"] if item["path"] == str(old)), None)
                    if prior:
                        require(snapshot(physical)["kind"] == "missing" and snapshot(self.path(prior["quarantinePath"])) == prior["before"], "Previously retired path or quarantine changed")
                        continue
                    require(request.get("unreferencedWithinInspectedScope") is True, "Cannot prove old path is unused within the inspected scope")
                    checked = request.get("consumersChecked")
                    require(isinstance(checked, list) and checked, "Consumer inspection evidence is missing")
                    for evidence in checked:
                        factual(evidence, "consumersChecked")
                    factual(request.get("evidence"), "retirement evidence")
                    require(not self.package_owner(old), "Retirement of package-owned paths requires native package management")
                    current = snapshot(physical)
                    require(current["kind"] in ("file", "symlink") and matches(current, request.get("expected")),
                            "Retirement permits only the exact inspected unmanaged file/link")
                    require(not old.is_relative_to(self.base) and not physical.is_relative_to(self.state), "Cannot retire managed installation/state content through an old-path request")
                    require(not any(action["path"] == str(old) for action in receipt["actions"]), "Cannot retire a promoted entry point")
                    for staged_tool in receipt["tools"].values():
                        staged = staged_tool["staged"]
                        if staged["reuse"]:
                            require(all(self.path(item["path"]).resolve() != physical.resolve() for item in staged["executables"].values()),
                                    "Replacement still depends on the old executable")
                    quarantine_logical = self.base / "quarantine" / receipt["id"] / (str(len(receipt["retirements"])) + "-" + old.name)
                    quarantine = self.path(quarantine_logical)
                    safe_parents(quarantine)
                    quarantine.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    require(not quarantine.exists() and not quarantine.is_symlink(), "Quarantine destination already exists")
                    shutil.move(str(physical), str(quarantine))
                    if os.geteuid() == 0:
                        os.chown(quarantine, current["uid"], current["gid"], follow_symlinks=False)
                    receipt["retirements"].append({"tool": name, "path": str(old), "before": current,
                                                   "quarantinePath": str(quarantine_logical), "consumersChecked": checked, "evidence": request["evidence"]})
                    self.save(path, receipt)
                except Blocked as exc:
                    blockers.append({"path": str(old), "reason": str(exc)})
        result = {"retired": receipt["retirements"], "blockers": blockers, "passed": not blockers}
        receipt["retirementResult"] = result
        self.save(path, receipt)
        return result

    def rollback(self):
        path, receipt = self.receipt()
        require(receipt.get("status") != "rolled_back", "Receipt is already rolled back")
        # Inspect all current occupants before restoring any of them.
        for item in receipt["retirements"]:
            safe_parents(self.path(item["path"]))
            require(snapshot(self.path(item["path"]))["kind"] == "missing", "Retired path has been reused; inspect before rollback")
            require(snapshot(self.path(item["quarantinePath"])) == item["before"], "Quarantine content changed")
        for action in receipt["actions"]:
            safe_parents(self.path(action["path"]))
            require(snapshot(self.path(action["path"])) == action["after"], "Entry point changed since installation; inspect before rollback")
            if action.get("backupPath"):
                require(snapshot(self.path(action["backupPath"])) == action["before"], "Command backup changed")
        for item in reversed(receipt["retirements"]):
            destination = self.path(item["path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(self.path(item["quarantinePath"])), str(destination))
        index = self.index()
        for action in reversed(receipt["actions"]):
            destination = self.path(action["path"])
            if action.get("backupPath"):
                backup = self.path(action["backupPath"])
                temporary = destination.with_name(destination.name + ".restore-" + uuid.uuid4().hex)
                copy_preserving_owner(backup, temporary)
                os.replace(temporary, destination)
            else:
                destination.unlink()
            if action.get("previousManagedRecord"):
                index[action["path"]] = action["previousManagedRecord"]
            else:
                index.pop(action["path"], None)
        receipt["status"] = "rolled_back"
        receipt["rollback"] = {"passed": True, "retainedVersionedTrees": True, "note": "Versioned installations remain available; restored prior entry points and retired files only."}
        self.save(self.state / "managed-launchers.json", index)
        self.save(path, receipt)
        return receipt["rollback"]


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=["inventory", "validate", "plan", "apply", "verify", "check", "retire", "rollback"])
    result.add_argument("--catalog", required=True)
    result.add_argument("--plan")
    result.add_argument("--payload-root", required=True)
    result.add_argument("--state", default=str(pathlib.Path.home() / ".local/state/agentic-stack/hostctl"))
    result.add_argument("--mode", choices=["system", "user"], default="system")
    result.add_argument("--receipt")
    result.add_argument("--output")
    result.add_argument("--prefix", help="Test-only fake filesystem prefix; no privileged host installation")
    result.add_argument("--package-owners", help="Fake package-ownership map; requires --prefix")
    result.add_argument("--operator-uid", type=int, help=argparse.SUPPRESS)
    result.add_argument("--operator-gid", type=int, help=argparse.SUPPRESS)
    result.add_argument("--operator-home", help=argparse.SUPPRESS)
    return result


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(argv)
    require(not args.package_owners or args.prefix, "Fake package owners are available only with --prefix")
    if args.command in ("validate", "plan", "apply"):
        require(args.plan, "This command requires --plan with inspected private-source selections")
    mutating = args.command in ("apply", "verify", "retire", "rollback")
    # Check the original spelling before elevation, and retain it for the child to check again.
    host = Host(args)
    if args.mode == "system" and not args.prefix and mutating and os.geteuid() != 0:
        require(shutil.which("sudo"), "System installation needs existing noninteractive sudo; explicit --mode user remains available")
        command = ["sudo", "-n", sys.executable, "-I", str(pathlib.Path(__file__).resolve()), *argv,
                   "--state", str(pathlib.Path(args.state).expanduser().absolute()), "--operator-uid", str(os.getuid()),
                   "--operator-gid", str(os.getgid()), "--operator-home", str(pathlib.Path.home())]
        return subprocess.run(command).returncode
    if args.mode == "system" and not args.prefix and mutating and os.geteuid() == 0:
        require(args.operator_uid is not None and args.operator_gid is not None and args.operator_home,
                "Start through the intended ordinary operator; the controller will use existing sudo authority")
        require(str(args.operator_uid) == os.environ.get("SUDO_UID"), "Privileged operator identity does not match sudo")
    lock = None
    try:
        if mutating:
            host.ensure_state()
            lock_path = host.state / "operation.lock"
            require(not lock_path.is_symlink(), "Refusing lock symlink")
            lock = lock_path.open("a")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        method = host.validate if args.command == "plan" else getattr(host, args.command)
        result = method()
        if args.output:
            host.save(pathlib.Path(args.output), result)
        print(json.dumps(result, indent=2))
        return 0 if result.get("passed", True) else 2
    finally:
        if lock:
            lock.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Blocked, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
