#!/usr/bin/env python3
"""Purge exact retired files after completed acceptance; retain a verified rollback tar."""
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True

SHA = re.compile(r"[a-f0-9]{64}\Z")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def absolute(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "Use normalized absolute paths")
    return path


def safe_parents(path):
    for parent in (Path(path).parent, *Path(path).parent.parents):
        require(not parent.is_symlink(), "Symlinked parent is not permitted: " + str(parent))


def read_bound(path, expected):
    path = absolute(path)
    safe_parents(path)
    require(not path.is_symlink() and path.is_file(), "Bound input must be a regular file")
    require(SHA.fullmatch(expected or "") and sha(path) == expected, "Input hash changed: " + str(path))
    with path.open() as stream:
        value = json.load(stream)
    require(sha(path) == expected, "Input changed while being read")
    return value


def private_write(path, value, owner):
    path = Path(path)
    safe_parents(path)
    require(not path.is_symlink(), "Refusing receipt symlink")
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".writing-")
    try:
        os.fchmod(descriptor, 0o600)
        if os.geteuid() == 0:
            os.fchown(descriptor, *owner)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_hostctl():
    source = Path(__file__).resolve().with_name("hostctl.py")
    require(source.is_file(), "Install this helper next to the kit's hostctl.py")
    spec = importlib.util.spec_from_file_location("cleanup_hostctl", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def active_file_consumers(path):
    """Detect current executable/mapped-file consumers; receipt retains wider inspection scope."""
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode):
        return []
    wanted = (info.st_dev, info.st_ino)
    consumers = []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            current = (directory / "exe").stat()
            if (current.st_dev, current.st_ino) == wanted:
                consumers.append({"pid": int(directory.name), "kind": "executable"})
                continue
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
        try:
            for line in (directory / "maps").read_text().splitlines():
                parts = line.split(None, 5)
                if len(parts) < 5 or not parts[4].isdigit():
                    continue
                major, minor = (int(item, 16) for item in parts[3].split(":"))
                if (os.makedev(major, minor), int(parts[4])) == wanted:
                    consumers.append({"pid": int(directory.name), "kind": "mapping"})
                    break
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return consumers


class Cleanup:
    def __init__(self, args, hostctl=None):
        self.args = args
        self.hostctl = hostctl or load_hostctl()
        self.owner = (args.operator_uid if args.operator_uid is not None else os.getuid(),
                      args.operator_gid if args.operator_gid is not None else os.getgid())
        self.home = absolute(args.operator_home or str(Path.home()))
        self.state = absolute(args.state)
        self.host_state = absolute(args.host_state)
        self.host = self.hostctl.Host(argparse.Namespace(
            mode=args.mode, prefix=args.prefix, state=str(self.host_state),
            operator_home=str(self.home), operator_uid=self.owner[0], operator_gid=self.owner[1],
            package_owners=args.package_owners))
        self.receipt_path = absolute(args.host_receipt)
        require(self.receipt_path.resolve().is_relative_to(self.host_state.resolve()), "Host receipt is outside host state")
        self.receipt = read_bound(self.receipt_path, args.host_receipt_sha256)
        self.completion = read_bound(args.completion, args.completion_sha256)
        require(self.receipt_path.stat().st_uid == self.owner[0] and Path(args.completion).stat().st_uid == self.owner[0],
                "Host receipt and completion must belong to the intended operator")
        marker_path = self.host_state / "hostctl-state.json"
        require(marker_path.is_file() and not marker_path.is_symlink(), "Host state marker is absent or unsafe")
        marker = json.loads(marker_path.read_text())
        require(marker.get("schemaVersion") == 1 and marker.get("operatorUid") == self.owner[0] and
                marker.get("mode") == args.mode, "Host state marker operator/mode mismatch")
        require(self.receipt.get("schemaVersion") == 1 and self.receipt.get("operatorUid") == self.owner[0]
                and self.receipt.get("mode") == args.mode, "Host receipt operator/mode/schema mismatch")
        require(self.receipt.get("status") == "installed_and_verified" and
                self.receipt.get("verification", {}).get("passed") is True and not self.receipt.get("blockers"),
                "Host installation must be verified without blockers")
        require(self.completion.get("schemaVersion") == 1 and self.completion.get("status") == "completed"
                and self.completion.get("passed") is True, "Final target acceptance has not completed")
        binding = {"path": str(self.receipt_path), "sha256": args.host_receipt_sha256}
        require(binding in self.completion.get("hostReceipts", []), "Completion does not bind this exact host receipt")
        for key in ("preservationReport", "acceptanceEvidence"):
            evidence = self.completion.get(key, {})
            read_bound(evidence.get("path", ""), evidence.get("sha256", ""))
        roots = self.completion.get("protectedRoots")
        require(isinstance(roots, list) and roots, "Completion must declare actual protected profile/brain/credential paths")
        self.protected = [absolute(value) for value in roots]
        self.protected += [self.home / value for value in (".claude", ".claude.json", ".omp", ".codex", ".agents", ".config/opencode")]
        self.protected += [Path(__file__).resolve().parents[1], self.host.base / "tools", self.host.bin, self.host_state, self.state]
        identity = args.host_receipt_sha256 + ":" + args.completion_sha256
        self.transaction = hashlib.sha256(identity.encode()).hexdigest()[:24]
        self.directory = self.state / self.transaction
        self.record_path = self.directory / "cleanup-receipt.json"
        self.archive = self.directory / "rollback-files.tar.gz"
        require(not self.state.is_relative_to(self.host.base) and not self.host.base.is_relative_to(self.state),
                "Use a separate cleanup state outside managed runtimes")
        require(not self.state.is_relative_to(self.host_state) and not self.host_state.is_relative_to(self.state),
                "Use separate nonnested cleanup and host state directories")
        safe_parents(self.state / "placeholder")

    def exact_inputs(self):
        read_bound(self.receipt_path, self.args.host_receipt_sha256)
        completion = read_bound(self.args.completion, self.args.completion_sha256)
        for key in ("preservationReport", "acceptanceEvidence"):
            evidence = completion[key]
            read_bound(evidence["path"], evidence["sha256"])

    def items(self):
        identifier = self.receipt.get("id", "")
        require(re.fullmatch(r"[A-Za-z0-9_-]+", identifier or ""), "Invalid host receipt id")
        root = self.host.base / "quarantine" / identifier
        records = self.receipt.get("retirements", [])
        require(isinstance(records, list), "Invalid retirements inventory")
        if records:
            require(self.receipt.get("retirementResult", {}).get("passed") is True,
                    "All requested retirement checks must have passed")
        items, seen = [], set()
        for index, item in enumerate(records):
            logical = absolute(item["quarantinePath"])
            old = absolute(item["path"])
            before = item["before"]
            require(logical.parent == root and logical not in seen, "Quarantine item is outside its exact receipt directory or duplicated")
            seen.add(logical)
            require(before.get("kind") in ("file", "symlink"), "Only receipt-listed regular files and symlinks may be purged")
            require(old != logical and not old.is_relative_to(self.host.base) and
                    not self.host.path(old).is_relative_to(self.host_state), "Retirement source cannot be managed runtime/state")
            require(item.get("consumersChecked") and item.get("evidence"), "Missing consumer inspection evidence")
            tool = self.receipt.get("tools", {}).get(item.get("tool"), {})
            requests = tool.get("selection", {}).get("choice", {}).get("retire", [])
            request = next((request for request in requests if request.get("path") == str(old)), None)
            require(request and request.get("unreferencedWithinInspectedScope") is True and
                    self.hostctl.matches(before, request.get("expected")), "Retirement is not bound to its inspected original request")
            require(not any(old == root or old.is_relative_to(root) for root in self.protected),
                    "Protected profile, brain, credential, kit, runtime or state path cannot be cleaned")
            require(not any(logical == root or logical.is_relative_to(root) for root in self.protected),
                    "Quarantine path overlaps protected profile/brain data")
            require(not any(action.get("path") in (str(old), str(logical)) for action in self.receipt.get("actions", [])),
                    "Cannot clean a promoted entrypoint")
            safe_parents(self.host.path(logical))
            safe_parents(self.host.path(old))
            require(self.hostctl.snapshot(self.host.path(old))["kind"] == "missing", "Old active path has been reused; inspect before cleanup")
            require(not self.host.package_owner(old) and not self.host.package_owner(logical),
                    "Package-owned paths must use native package management")
            items.append({"path": str(old), "quarantinePath": str(logical), "before": before,
                          "member": "files/" + str(index).zfill(6)})
        return items

    def verify_host(self):
        result = self.host.verify_receipt(self.receipt)
        require(result.get("passed") is True, "Fresh replacement host verification failed; no cleanup")
        return result

    def record(self):
        if not self.record_path.exists():
            require(not self.record_path.is_symlink(), "Refusing cleanup receipt symlink")
            return None
        require(not self.record_path.is_symlink(), "Refusing cleanup receipt symlink")
        safe_parents(self.record_path)
        value = json.loads(self.record_path.read_text())
        require(value.get("schemaVersion") == 1 and value.get("transaction") == self.transaction and
                value.get("hostReceiptSha256") == self.args.host_receipt_sha256 and
                value.get("completionSha256") == self.args.completion_sha256,
                "Cleanup receipt is bound to different inputs")
        require(value.get("items") == self.items(), "Cleanup receipt inventory changed")
        return value

    def verify_archive(self, record):
        require(not self.archive.is_symlink() and self.archive.is_file(), "Rollback archive is missing or unsafe")
        require(sha(self.archive) == record.get("archiveSha256"), "Rollback archive changed")
        expected = {item["member"]: item for item in record["items"]}
        with tarfile.open(self.archive, "r:gz") as archive:
            members = archive.getmembers()
            require(len(members) == len(expected) and set(member.name for member in members) == set(expected),
                    "Rollback archive membership differs")
            for member in members:
                before = expected[member.name]["before"]
                require(member.uid == before["uid"] and member.gid == before["gid"] and
                        member.mode == before["mode"], "Rollback metadata differs")
                if before["kind"] == "symlink":
                    require(member.issym() and member.linkname == before["target"], "Rollback symlink differs")
                else:
                    require(member.isreg() and member.size == before["size"], "Rollback file type/size differs")
                    stream = archive.extractfile(member)
                    digest = hashlib.sha256()
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                    require(digest.hexdigest() == before["sha256"], "Rollback file bytes differ")

    def check_items(self, items, allow_missing=False, check_active=True):
        for item in items:
            physical = self.host.path(item["quarantinePath"])
            safe_parents(physical)
            actual = self.hostctl.snapshot(physical)
            if allow_missing and actual["kind"] == "missing":
                continue
            require(actual == item["before"], "Quarantined file changed: " + str(physical))
            if check_active:
                require(not active_file_consumers(physical), "Retired file is still executable or mapped by a running process")

    def plan(self):
        items = self.items()
        record = self.record()
        if record:
            self.verify_archive(record)
        self.verify_host()
        self.check_items(items, allow_missing=bool(record and record.get("status") in ("backed_up", "deleting", "completed")))
        self.exact_inputs()
        return {"passed": True, "transaction": self.transaction, "items": items,
                "rollbackArchive": str(self.archive), "receipt": str(self.record_path),
                "operation": "Delete only exact quarantine file/link objects; preserve verified rollback archive"}

    def ensure_state(self):
        safe_parents(self.state / "placeholder")
        if self.state.exists():
            require(self.state.is_dir() and self.state.stat().st_uid == self.owner[0], "Cleanup state must belong to the operator")
            marker = self.state / "cleanup-state.json"
            require(not marker.is_symlink() and marker.is_file(), "Existing cleanup state lacks its marker")
            data = json.loads(marker.read_text())
            require(data == {"schemaVersion": 1, "operatorUid": self.owner[0]}, "Cleanup state belongs to another operator")
        else:
            self.state.mkdir(parents=True, mode=0o700)
            if os.geteuid() == 0:
                os.chown(self.state, *self.owner)
            private_write(self.state / "cleanup-state.json", {"schemaVersion": 1, "operatorUid": self.owner[0]}, self.owner)
        self.state.chmod(0o700)
        require(not self.directory.is_symlink(), "Transaction directory cannot be a symlink")
        self.directory.mkdir(mode=0o700, exist_ok=True)
        require(self.directory.stat().st_uid == self.owner[0] or os.geteuid() == 0, "Transaction owner differs")
        if os.geteuid() == 0:
            os.chown(self.directory, *self.owner)
        self.directory.chmod(0o700)

    def backup(self, items):
        require(not self.archive.exists() and not self.archive.is_symlink(),
                "Uncommitted archive exists; preserve and inspect it before resuming")
        descriptor, temporary = tempfile.mkstemp(dir=self.directory, prefix="rollback.writing-")
        os.fchmod(descriptor, 0o600)
        os.close(descriptor)
        try:
            with tarfile.open(temporary, "w:gz", compresslevel=6) as archive:
                for item in items:
                    physical = self.host.path(item["quarantinePath"])
                    before = item["before"]
                    require(self.hostctl.snapshot(physical) == before, "Quarantine changed while backing up")
                    member = tarfile.TarInfo(item["member"])
                    member.uid, member.gid, member.mode = before["uid"], before["gid"], before["mode"]
                    member.mtime = 0
                    if before["kind"] == "symlink":
                        member.type, member.linkname = tarfile.SYMTYPE, before["target"]
                        archive.addfile(member)
                    else:
                        member.type, member.size = tarfile.REGTYPE, before["size"]
                        fd = os.open(physical, os.O_RDONLY | os.O_NOFOLLOW)
                        with os.fdopen(fd, "rb") as stream:
                            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "Backup source is not regular")
                            archive.addfile(member, stream)
                    require(self.hostctl.snapshot(physical) == before, "Quarantine changed during backup")
            if os.geteuid() == 0:
                os.chown(temporary, *self.owner)
            with open(temporary, "rb") as stream:
                os.fsync(stream.fileno())
            os.replace(temporary, self.archive)
            record = {"schemaVersion": 1, "transaction": self.transaction, "status": "backed_up",
                      "operatorUid": self.owner[0], "hostReceipt": str(self.receipt_path),
                      "hostReceiptSha256": self.args.host_receipt_sha256,
                      "completion": str(absolute(self.args.completion)), "completionSha256": self.args.completion_sha256,
                      "archive": str(self.archive), "archiveSha256": sha(self.archive), "items": items, "deleted": [],
                      "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                      "recovery": "Run cleanup-retired.py restore with identical bound arguments, then hostctl rollback with this exact host receipt."}
            self.verify_archive(record)
            private_write(self.record_path, record, self.owner)
            return record
        finally:
            Path(temporary).unlink(missing_ok=True)

    @contextlib.contextmanager
    def locks(self):
        self.ensure_state()
        locks = []
        try:
            for path in (self.host_state / "operation.lock", self.state / "operation.lock"):
                safe_parents(path)
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
                lock = os.fdopen(descriptor, "w")
                locks.append(lock)
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            for lock in reversed(locks):
                lock.close()

    def apply(self):
        with self.locks():
            plan = self.plan()
            record = self.record() or self.backup(plan["items"])
            require(record["status"] != "restored", "Restored cleanup requires a newly qualified workflow before another purge")
            self.verify_archive(record)
            self.check_items(record["items"], allow_missing=True)
            self.exact_inputs()
            if record["status"] == "completed":
                require(all(self.hostctl.snapshot(self.host.path(x["quarantinePath"]))["kind"] == "missing" for x in record["items"]),
                        "Completed cleanup paths have been repopulated")
                return {"passed": True, "status": "completed", "receipt": str(self.record_path), "alreadyCompleted": True}
            record["status"] = "deleting"
            private_write(self.record_path, record, self.owner)
            for item in record["items"]:
                self.exact_inputs()
                physical = self.host.path(item["quarantinePath"])
                safe_parents(physical)
                actual = self.hostctl.snapshot(physical)
                if actual["kind"] != "missing":
                    require(actual == item["before"], "Quarantine changed immediately before deletion")
                    require(not active_file_consumers(physical), "Retired file acquired a running consumer")
                    require(not self.host.package_owner(item["path"]), "Old source became package-owned")
                    directory_fd = os.open(physical.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                    try:
                        os.unlink(physical.name, dir_fd=directory_fd)
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                if item["quarantinePath"] not in record["deleted"]:
                    record["deleted"].append(item["quarantinePath"])
                private_write(self.record_path, record, self.owner)
            record["status"] = "completed"
            record["completedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
            private_write(self.record_path, record, self.owner)
            return {"passed": True, "status": "completed", "deletedCount": len(record["items"]),
                    "receipt": str(self.record_path), "rollbackArchive": str(self.archive),
                    "rollbackArchiveSha256": record["archiveSha256"]}

    def restore(self):
        with self.locks():
            self.exact_inputs()
            record = self.record()
            require(record is not None, "No cleanup receipt exists")
            self.verify_archive(record)
            require(record["status"] in ("backed_up", "deleting", "completed", "restoring", "restored"), "Cleanup receipt has unknown status")
            # All existing occupants must be exact originals before any writes.
            self.check_items(record["items"], allow_missing=True, check_active=False)
            record["status"] = "restoring"
            private_write(self.record_path, record, self.owner)
            with tarfile.open(self.archive, "r:gz") as archive:
                for item in record["items"]:
                    destination = self.host.path(item["quarantinePath"])
                    if self.hostctl.snapshot(destination)["kind"] != "missing":
                        continue
                    safe_parents(destination)
                    require(destination.parent.is_dir(), "Original quarantine directory disappeared; inspect before restore")
                    member = archive.getmember(item["member"])
                    before = item["before"]
                    if before["kind"] == "symlink":
                        os.symlink(member.linkname, destination)
                        if os.geteuid() == 0:
                            os.chown(destination, before["uid"], before["gid"], follow_symlinks=False)
                    else:
                        descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix=".restoring-")
                        try:
                            with os.fdopen(descriptor, "wb") as output:
                                shutil.copyfileobj(archive.extractfile(member), output)
                                output.flush()
                                if os.geteuid() == 0:
                                    os.fchown(output.fileno(), before["uid"], before["gid"])
                                os.fchmod(output.fileno(), before["mode"])
                                os.fsync(output.fileno())
                            require(self.hostctl.snapshot(temporary) == before, "Staged restoration identity differs")
                            # link() publishes without replacing a concurrent new occupant.
                            os.link(temporary, destination, follow_symlinks=False)
                        finally:
                            Path(temporary).unlink(missing_ok=True)
                    require(self.hostctl.snapshot(destination) == before, "Restored quarantine identity differs")
            record["status"] = "restored"
            private_write(self.record_path, record, self.owner)
            return {"passed": True, "status": "restored", "receipt": str(self.record_path),
                    "next": "Quarantine restored. Use hostctl rollback with the exact original host receipt after inspecting current entrypoints."}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("plan", "apply", "restore"))
    for name in ("host-receipt", "host-receipt-sha256", "completion", "completion-sha256", "host-state", "state"):
        result.add_argument("--" + name, required=True)
    result.add_argument("--mode", choices=("system", "user"), default="system")
    result.add_argument("--prefix", help="Test-only fake filesystem prefix")
    result.add_argument("--package-owners", help="Test-only package owner map, requires --prefix")
    result.add_argument("--operator-uid", type=int, help=argparse.SUPPRESS)
    result.add_argument("--operator-gid", type=int, help=argparse.SUPPRESS)
    result.add_argument("--operator-home", help=argparse.SUPPRESS)
    return result


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(arguments)
    require(not args.package_owners or args.prefix, "Fake package ownership requires a test prefix")
    if args.mode == "system" and not args.prefix:
        if os.geteuid() != 0:
            require(shutil.which("sudo"), "System cleanup needs existing noninteractive sudo authority")
            return subprocess.run(["sudo", "-n", sys.executable, "-I", str(Path(__file__).resolve()), *arguments,
                                   "--operator-uid", str(os.getuid()), "--operator-gid", str(os.getgid()),
                                   "--operator-home", str(Path.home())]).returncode
        require(args.operator_uid is not None and args.operator_gid is not None and args.operator_home and
                str(args.operator_uid) == os.environ.get("SUDO_UID"), "Start through the intended ordinary operator")
    cleanup = Cleanup(args)
    print(json.dumps(getattr(cleanup, args.command)(), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
