#!/usr/bin/env python3
"""Private, fail-closed preservation receipts for a two-phase agent upgrade.

Python 3.9+ standard library only. This verifies the declared configuration scope;
it does not infer undisclosed profiles, certify model behavior, or snapshot live DBs.
"""
import argparse
import copy
import datetime
import fnmatch
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import uuid

SCHEMA = 1
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_FILES = 50000

# These are forbidden semantic field names, not automatic exclusions. A rule
# still has to name each actual scalar leaf and explain its metadata role.
MUTABLE_FORBIDDEN_WORDS = {
    "model", "models", "provider", "providers", "route", "routes", "routing",
    "auth", "authentication", "authorization", "credential", "credentials",
    "secret", "secrets", "password", "passwords", "token", "key", "keys",
    "hook", "hooks", "skill", "skills", "brain", "brains", "instruction", "instructions",
    "permission", "permissions", "prompt", "prompts", "policy", "policies",
    "sandbox", "trust", "trusted", "command", "commands", "exec", "executable",
    "tool", "tools", "mcp", "plugin", "plugins", "extension", "extensions",
    "default", "defaults", "profile", "profiles", "config", "configuration", "setting", "settings",
    "endpoint", "endpoints", "url", "urls", "host", "hostname", "port", "proxy",
    "certificate", "certificates", "environment", "env", "memory", "memories",
    "resume", "continuation", "account", "organization", "tenant", "allowed", "denied",
    "allow", "deny", "enabled", "disabled", "feature", "features",
    "api", "client", "context", "limit", "limits", "max", "maximum", "min", "minimum",
}
MUTABLE_USAGE_FIELDS = {
    "lastcost", "lastusagecost", "lastsessioncost", "usagecost", "totalusagecost",
    "lastduration", "lastdurationms", "lastapiduration", "lastapidurationms",
    "lasttoolduration", "lasttooldurationms", "lastsessionduration", "lastsessiondurationms",
    "lasttotalinputtokens", "lasttotaloutputtokens", "lasttotalcachecreationinputtokens",
    "lasttotalcachereadinputtokens", "lastlinesadded", "lastlinesremoved",
    "lasttotalwebsearchrequests", "sessioncount", "usagecount", "launchcount", "runcount",
}


def mutable_kind(field):
    compact = re.sub(r"[^a-z0-9]", "", field.lower())
    if compact in MUTABLE_USAGE_FIELDS:
        return "numeric-usage"
    if compact in ("lastsessionid", "lastcompletedsessionid"):
        return "historical-session-id"
    if re.fullmatch(r"(?:last(?:used|seen|active|opened|closed|started|finished|completed|updated|modified|accessed|session|exit|activity|interaction|launch)?|created|updated|modified|accessed|opened|closed|started|finished|completed)(?:at|time|timestamp|date)", compact):
        return "timestamp"
    raise PreservationError("Ambiguous mutable field; only explicit timestamp, historical-session-id and supported usage metadata names are eligible")


class PreservationError(ValueError):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def absolute(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise PreservationError("Expected an absolute filesystem path")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise PreservationError("Paths must be absolute and contain no '..': " + value)
    return path


def metadata(info):
    return {"mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid}


def private_dir(path, create=False):
    path = absolute(str(path))
    for item in reversed([path] + list(path.parents)):
        if item == Path("/"):
            continue
        try:
            value = item.lstat()
        except FileNotFoundError:
            if not create:
                raise PreservationError("Private directory is missing: " + str(item))
            item.mkdir(mode=0o700)
            value = item.lstat()
        if not stat.S_ISDIR(value.st_mode):
            raise PreservationError("Private state path has a non-directory or symlink ancestor: " + str(item))
    info = path.lstat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise PreservationError("Private state directory must be operator-owned with mode 0700: " + str(path))
    return path


def write_private(path, data, exclusive=True, mode=0o600):
    path = absolute(str(path))
    private_dir(path.parent, create=True)
    if exclusive and os.path.lexists(path):
        raise PreservationError("Refusing to overwrite existing preservation evidence: " + str(path))
    if not exclusive and os.path.lexists(path):
        existing = path.lstat()
        if not stat.S_ISREG(existing.st_mode) or existing.st_uid != os.getuid():
            raise PreservationError("Report path is not an owned regular file: " + str(path))
    temporary = path.parent / (".preserve-" + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def read_regular(path, max_bytes=MAX_FILE):
    path = absolute(str(path))
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise PreservationError("Cannot read regular preservation file: " + str(path)) from None
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise PreservationError("Unsupported or oversized preservation file: " + str(path))
        chunks, size = [], 0
        while True:
            data = os.read(fd, min(1024 * 1024, max_bytes + 1))
            if not data:
                break
            size += len(data)
            if size > max_bytes:
                raise PreservationError("Preservation file exceeds its size bound: " + str(path))
            chunks.append(data)
        after = os.fstat(fd)
        current = path.lstat()
        key = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
        if key(before) != key(after) or key(after) != key(current):
            raise PreservationError("Preservation file changed while being read: " + str(path))
        return b"".join(chunks), after
    finally:
        os.close(fd)


def json_load(data, context="JSON"):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise PreservationError("Duplicate object keys in " + context)
            value[key] = item
        return value
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(PreservationError("Non-finite JSON value")))
    except (UnicodeError, json.JSONDecodeError):
        raise PreservationError("Invalid " + context) from None


def read_json(path):
    return json_load(read_regular(path)[0], "JSON at " + str(path))


def pointer_parts(pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/") or len(pointer) < 2:
        raise PreservationError("Mutable metadata needs a literal non-root JSON pointer")
    if any(char in pointer for char in "*?[]") or re.search(r"~(?![01])", pointer):
        raise PreservationError("Mutable metadata pointers cannot contain wildcards or invalid JSON-pointer escapes")
    parts = [re.sub(r"~([01])", lambda match: "/" if match[1] == "1" else "~", part)
             for part in pointer[1:].split("/")]
    if any(not part for part in parts):
        raise PreservationError("Mutable metadata pointers cannot contain empty field names")
    for index, part in enumerate(parts):
        words = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", part)
        words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", words)
        words = set(re.findall(r"[a-z0-9]+", words.lower()))
        compact = re.sub(r"[^a-z0-9]", "", part.lower())
        forbidden = words & MUTABLE_FORBIDDEN_WORDS
        if index == len(parts) - 1 and compact in MUTABLE_USAGE_FIELDS:
            # Narrow known numeric duration counters are metadata even though
            # their labels mention API/tool execution. No generic numeric bypass.
            forbidden -= {"api", "tool"}
        if forbidden or compact in ("sessionid", "userid", "baseurl", "apikey", "authtoken"):
            raise PreservationError("Mutable metadata cannot exempt security/configuration fields: " + pointer)
    mutable_kind(parts[-1])
    return parts


def pointer_leaf(value, parts):
    current = value
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise PreservationError("Mutable metadata pointer must resolve through existing JSON objects")
        current = current[part]
    if not isinstance(current, dict) or parts[-1] not in current:
        raise PreservationError("Mutable metadata pointer must name an existing field")
    leaf = current[parts[-1]]
    if type(leaf) not in (str, int, float, bool, type(None)):
        raise PreservationError("Mutable metadata may exempt only existing scalar leaves")
    return current, parts[-1], leaf


def normalize_mutable(value, reference, pointers):
    normalized = copy.deepcopy(value)
    for pointer in pointers:
        parts = pointer_parts(pointer)
        _, _, before = pointer_leaf(reference, parts)
        parent, key, current = pointer_leaf(normalized, parts)
        if type(current) is not type(before):
            raise PreservationError("Mutable metadata must preserve scalar type: " + pointer)
        kind = mutable_kind(parts[-1])
        permitted = (int, float) if kind == "numeric-usage" else ((str,) if kind == "historical-session-id" else (str, int, float))
        if type(before) not in permitted:
            raise PreservationError("Mutable metadata type is not appropriate for its declared field kind: " + pointer)
        # An object marker cannot collide with a permitted scalar source value.
        parent[key] = {"$agenticReviewedMutableScalar": type(before).__name__}
    return normalized


def validate_plan(plan):
    if plan.get("schemaVersion") != SCHEMA:
        raise PreservationError("Preservation plan schemaVersion must be 1")
    if plan.get("discoveryComplete") is not True or not str(plan.get("discoveryEvidence", "")).strip():
        raise PreservationError("Inspect active profiles, launch flags/cwd, brain roots, and env sources; acknowledge discoveryComplete with discoveryEvidence")
    roots = plan.get("roots", [])
    if not roots:
        raise PreservationError("Preservation requires at least one explicit root")
    seen = set()
    for item in roots:
        path = str(absolute(item["path"]))
        if path in seen:
            raise PreservationError("Duplicate preservation root: " + path)
        seen.add(path)
        for pattern in item.get("exclude", []):
            if not isinstance(pattern, str) or not pattern or pattern.startswith("/") or ".." in Path(pattern).parts:
                raise PreservationError("Exclusions must be bounded root-relative patterns")
        if item.get("exclude") and not str(item.get("exclusionReason", "")).strip():
            raise PreservationError("Excluded mutable files require an explicit exclusionReason")
    for kind in ("additiveJson", "additiveToml"):
        for item in plan.get(kind, []):
            absolute(item["path"])
            pointers = item.get("allowedPointers", [])
            if not pointers or not all(isinstance(x, str) and len(x) > 1 and x.startswith("/") for x in pointers):
                raise PreservationError("Additive fields require specific non-root JSON-pointer paths")
            if not str(item.get("reason", "")).strip():
                raise PreservationError("Each additive scope requires a concrete review reason")
    mutable_paths = set()
    for item in plan.get("mutableJson", []):
        path = str(absolute(item["path"]))
        if path in mutable_paths:
            raise PreservationError("Duplicate mutable metadata file rule")
        mutable_paths.add(path)
        pointers = item.get("pointers", [])
        if not isinstance(pointers, list) or not pointers or len(pointers) != len(set(pointers)):
            raise PreservationError("Mutable metadata requires a nonempty unique literal pointers list")
        for pointer in pointers:
            pointer_parts(pointer)
        if not str(item.get("reason", "")).strip():
            raise PreservationError("Mutable metadata requires a factual field-specific reason")
    if mutable_paths & {item["path"] for item in plan.get("additiveToml", [])}:
        raise PreservationError("A file cannot be both mutable JSON and additive TOML")
    for name in plan.get("envNames", []):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise PreservationError("Invalid environment variable name")
    for item in plan.get("semanticEvidence", []):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(item.get("id", ""))):
            raise PreservationError("Invalid semantic evidence id")
        absolute(item["path"])
        if not isinstance(item.get("coveredPaths"), list) or not item["coveredPaths"]:
            raise PreservationError("Semantic evidence must name its coveredPaths before the baseline")
        for path in item["coveredPaths"]:
            absolute(path)
        if not str(item.get("coverage", "")).strip():
            raise PreservationError("Semantic evidence requires a coverage description")
    return plan


def excluded(relative, patterns):
    name = relative.as_posix()
    return any(fnmatch.fnmatchcase(name, p) or (p.endswith("/**") and name == p[:-3]) for p in patterns)


def collect(plan, save=None, forbidden=None):
    entries, contents, external, traversed = {}, {}, set(), set()
    total = 0
    max_file = int(plan.get("maxFileBytes", MAX_FILE))
    max_total = int(plan.get("maxTotalBytes", MAX_TOTAL))
    max_files = int(plan.get("maxFiles", MAX_FILES))
    if min(max_file, max_total, max_files) <= 0:
        raise PreservationError("Preservation limits must be positive")

    def add(path, value, data=None):
        nonlocal total
        key = str(path)
        if key in entries:
            if entries[key] != value:
                raise PreservationError("Overlapping preservation roots changed or disagree: " + key)
            return
        if len(entries) >= max_files:
            raise PreservationError("Preservation scope exceeds maxFiles; inspect declared roots")
        entries[key] = value
        if data is not None:
            total += len(data)
            if total > max_total:
                raise PreservationError("Preservation scope exceeds maxTotalBytes; inspect declared roots")
            contents[key] = data
            if save:
                save(value["sha256"], data)

    def ancestors(path):
        for parent in reversed(path.parents):
            try:
                info = parent.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode):
                add(parent, dict(type="symlink", target=os.readlink(parent), **metadata(info)))

    def visit(path, root, patterns, chain):
        if forbidden is not None and path.resolve(strict=False).is_relative_to(forbidden.resolve()):
            raise PreservationError("A protected root or followed symlink includes the preservation state")
        relative = path.relative_to(root)
        if relative != Path(".") and excluded(relative, patterns):
            return
        ancestors(path)
        try:
            info = path.lstat()
        except FileNotFoundError:
            add(path, {"type": "missing"})
            return
        value = metadata(info)
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            add(path, dict(type="symlink", target=target, **value))
            try:
                resolved = path.resolve(strict=False)
            except (OSError, RuntimeError):
                raise PreservationError("Unresolvable symlink in declared scope: " + str(path)) from None
            if str(resolved) in chain:
                raise PreservationError("Symlink directory cycle in declared scope: " + str(path))
            external.add(str(resolved))
            visit(resolved, resolved, patterns if path == root else [], chain + [str(resolved)])
        elif stat.S_ISDIR(info.st_mode):
            add(path, dict(type="directory", **value))
            identity = (str(path), str(root), tuple(patterns))
            if identity in traversed:
                return
            traversed.add(identity)
            for child in sorted(path.iterdir(), key=lambda p: p.name):
                visit(child, root, patterns, chain)
        elif stat.S_ISREG(info.st_mode):
            data, current = read_regular(path, max_file)
            add(path, dict(type="file", sha256=digest(data), size=len(data), **metadata(current)), data)
        else:
            raise PreservationError("Socket/device/FIFO in declared scope; explicitly exclude mutable runtime state: " + str(path))

    for root in plan["roots"]:
        path = absolute(root["path"])
        resolved = path.resolve(strict=False)
        if resolved != path:
            # A root may sit below a symlinked ancestor without being a symlink
            # itself. Protect its physical location from later cleanup too.
            external.add(str(resolved))
        visit(path, path, root.get("exclude", []), [str(path)])
    return entries, contents, sorted(external), total


def env_fingerprints(names, salt):
    result = {}
    for name in sorted(set(names)):
        value = os.environ.get(name)
        result[name] = {"present": value is not None,
                        "hmacSha256": hmac.new(salt, value.encode("utf-8", "surrogateescape"), hashlib.sha256).hexdigest() if value is not None else None}
    return result


def snapshot(plan_path, state):
    plan = validate_plan(read_json(plan_path))
    state = absolute(str(state))
    if os.path.lexists(state):
        private_dir(state)
        if list(state.iterdir()):
            raise PreservationError("Preservation state already exists; never rebaseline an active upgrade")
    else:
        private_dir(state, create=True)
    for root in plan["roots"]:
        resolved = absolute(root["path"]).resolve(strict=False)
        if state.resolve().is_relative_to(resolved):
            raise PreservationError("Preservation state must be outside every protected root")
    blobs = private_dir(state / "originals", create=True)

    def save(sha, data):
        path = blobs / sha
        if path.exists():
            if digest(read_regular(path, int(plan.get("maxFileBytes", MAX_FILE)))[0]) != sha:
                raise PreservationError("Original backup identity mismatch")
        else:
            write_private(path, data, mode=0o400)

    try:
        entries, contents, external, size = collect(plan, save, state)
        for item in plan.get("mutableJson", []):
            if entries.get(item["path"], {}).get("type") != "file":
                raise PreservationError("Mutable JSON must be an existing regular file inside the protected baseline")
            value = json_load(contents[item["path"]], "mutable metadata JSON")
            normalize_mutable(value, value, item["pointers"])
        semantic = {}
        for item in plan.get("semanticEvidence", []):
            if item["id"] in semantic:
                raise PreservationError("Duplicate semantic evidence id")
            data, _ = read_regular(item["path"])
            json_load(data, "semantic evidence")
            sha = digest(data)
            save(sha, data)
            covered = {}
            for path in item["coveredPaths"]:
                original = entries.get(path, {})
                if original.get("type") != "file":
                    raise PreservationError("Semantic evidence covers a file outside the exact protected baseline: " + path)
                covered[path] = original["sha256"]
            semantic[item["id"]] = {"sha256": sha, "coverage": item["coverage"], "path": item["path"],
                                    "coveredPaths": covered}
        again, _, _, _ = collect(plan, forbidden=state)
        if again != entries:
            raise PreservationError("Declared configuration changed during snapshot; quiesce config writes and use a fresh empty state")
        salt = secrets.token_bytes(32)
        manifest = {"schemaVersion": SCHEMA, "createdAt": now(), "operatorUid": os.getuid(),
                    "plan": plan, "planSha256": digest(canonical(plan)), "entries": entries,
                    "followedSymlinkTargets": external, "protectedBytes": size,
                    "environment": env_fingerprints(plan.get("envNames", []), salt),
                    "semanticEvidence": semantic}
        raw = canonical(manifest)
        write_private(state / "environment-salt", salt, mode=0o400)
        write_private(state / "baseline.json", raw, mode=0o400)
        write_private(state / "baseline.sha256", (digest(raw) + "\n").encode(), mode=0o400)
        return {"status": "snapshotted", "baselineSha256": digest(raw), "protectedEntries": len(entries),
                "protectedBytes": size, "state": str(state)}
    except Exception:
        # Leave a failed snapshot for inspection. Never silently delete evidence.
        raise


def load_baseline(state):
    state = private_dir(state)
    raw, _ = read_regular(state / "baseline.json", 128 * 1024 * 1024)
    expected = read_regular(state / "baseline.sha256")[0].decode().strip()
    if digest(raw) != expected:
        raise PreservationError("Baseline receipt identity mismatch")
    manifest = json_load(raw, "baseline receipt")
    if manifest.get("operatorUid") != os.getuid():
        raise PreservationError("Run preservation as the original operator")
    validate_plan(manifest["plan"])
    if digest(canonical(manifest["plan"])) != manifest["planSha256"]:
        raise PreservationError("Baseline plan identity mismatch")
    return manifest, expected


def pointer_child(pointer, key):
    return pointer + "/" + str(key).replace("~", "~0").replace("/", "~1")


def pointer_allowed(pointer, scopes):
    return any(scope == "" or pointer == scope or pointer.startswith(scope + "/") for scope in scopes)


def additive_preserved(old, new, scopes, pointer=""):
    # bool/int equality in Python must not accept JSON true -> 1.
    if type(old) is not type(new):
        return False
    if isinstance(old, dict):
        for key, value in old.items():
            if key not in new or not additive_preserved(value, new[key], scopes, pointer_child(pointer, key)):
                return False
        return all(key in old or pointer_allowed(pointer_child(pointer, key), scopes) for key in new)
    if isinstance(old, list):
        if not pointer_allowed(pointer, scopes):
            return exact_value(old, new)
        # Hook order and duplicates are preserved; only new intervening/appended
        # entries are allowed in a deliberately reviewed additive field.
        cursor = 0
        for item in new:
            if cursor < len(old) and exact_value(old[cursor], item):
                cursor += 1
        return cursor == len(old)
    return old == new


def exact_value(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(exact_value(left[x], right[x]) for x in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(exact_value(x, y) for x, y in zip(left, right))
    return left == right


def structured(data, format_name):
    if format_name == "json":
        return json_load(data)
    try:
        import tomllib
    except ImportError:
        raise PreservationError("Additive TOML verification requires Python 3.11+; use the supplied Python 3.12 runtime") from None
    try:
        return tomllib.loads(data.decode())
    except (UnicodeError, ValueError):
        raise PreservationError("Invalid TOML configuration") from None


def approvals(state, kind):
    directory = state / kind
    if not directory.exists():
        return []
    private_dir(directory)
    result = []
    for path in sorted(directory.iterdir()):
        if not re.fullmatch(r"[0-9a-f]{64}\.json", path.name):
            raise PreservationError("Unexpected file in preservation review ledger")
        raw, _ = read_regular(path)
        if digest(raw) != path.stem:
            raise PreservationError("Preservation review receipt changed")
        result.append(json_load(raw, "review receipt"))
    return result


def record_additions(state, spec_path):
    state = private_dir(state)
    baseline, identity = load_baseline(state)
    spec = read_json(spec_path)
    if spec.get("schemaVersion") != SCHEMA or not str(spec.get("reason", "")).strip():
        raise PreservationError("Addition review requires schemaVersion 1 and a concrete reason")
    current, _, _, _ = collect(baseline["plan"], forbidden=state)
    selected = {}
    for item in spec.get("entries", []):
        path = str(absolute(item["path"]))
        value = current.get(path)
        if value is None or value.get("type") == "missing" or baseline["entries"].get(path, {}).get("type") not in (None, "missing"):
            raise PreservationError("Reviewed additions must be new items inside declared roots: " + path)
        if item.get("identity") != value:
            raise PreservationError("Reviewed addition does not match its inspected exact identity: " + path)
        selected[path] = value
    if not selected:
        raise PreservationError("No exact additions selected for review")
    receipt = {"schemaVersion": SCHEMA, "baselineSha256": identity, "reviewedAt": now(),
               "reason": spec["reason"], "entries": selected}
    raw = canonical(receipt)
    path = state / "addition-reviews" / (digest(raw) + ".json")
    write_private(path, raw, mode=0o400)
    return {"status": "recorded", "entries": len(selected), "receipt": str(path)}


def record_migration(state, spec_path):
    state = private_dir(state)
    baseline, identity = load_baseline(state)
    spec = read_json(spec_path)
    if spec.get("schemaVersion") != SCHEMA or not str(spec.get("explanation", "")).strip():
        raise PreservationError("Migration review requires schemaVersion 1 and a concrete explanation")
    source = str(absolute(spec["sourcePath"]))
    destination = str(absolute(spec["destinationPath"]))
    retained = str(absolute(spec["retainedOriginalPath"]))
    before = baseline["entries"].get(source, {})
    if before.get("type") != "file" or before["sha256"] != spec.get("sourceSha256"):
        raise PreservationError("Migration source does not match the immutable baseline")
    if any(x["sourcePath"] == source for x in approvals(state, "migration-reviews")):
        raise PreservationError("This baseline source already has a recorded migration")
    current, _, _, _ = collect(baseline["plan"], forbidden=state)
    target = current.get(destination, {})
    if target.get("type") != "file" or target["sha256"] != spec.get("destinationSha256"):
        raise PreservationError("Migration destination is not its inspected exact file inside declared roots")
    if destination != source and baseline["entries"].get(destination, {}).get("type") not in (None, "missing"):
        raise PreservationError("Migration destination would overwrite another protected baseline item")
    old_data, retained_info = read_regular(retained, int(baseline["plan"].get("maxFileBytes", MAX_FILE)))
    if digest(old_data) != before["sha256"]:
        raise PreservationError("Retained original does not match the source backup")
    retained_identity = dict(type="file", sha256=before["sha256"], size=len(old_data), **metadata(retained_info))
    before_evidence = baseline.get("semanticEvidence", {}).get(spec.get("baselineSemanticEvidence"), {})
    if not before_evidence:
        raise PreservationError("Migration requires semantic evidence captured in the original baseline")
    if before_evidence.get("coveredPaths", {}).get(source) != before["sha256"]:
        raise PreservationError("Semantic evidence is not bound to this migration source in the original baseline")
    old_effective = read_regular(state / "originals" / before_evidence["sha256"])[0]
    if digest(old_effective) != before_evidence["sha256"]:
        raise PreservationError("Baseline semantic evidence identity mismatch")
    after_spec = spec.get("afterSemanticEvidence", {})
    new_effective = read_regular(absolute(after_spec["path"]))[0]
    if digest(new_effective) != after_spec.get("sha256"):
        raise PreservationError("After-migration semantic evidence identity mismatch")
    if canonical(json_load(old_effective)) != canonical(json_load(new_effective)):
        raise PreservationError("Migrated effective configuration is not semantically identical")
    evidence_sha = digest(new_effective)
    evidence_path = state / "migration-evidence" / evidence_sha
    if not evidence_path.exists():
        write_private(evidence_path, new_effective, mode=0o400)
    receipt = {"schemaVersion": SCHEMA, "baselineSha256": identity, "reviewedAt": now(),
               "sourcePath": source, "sourceSha256": before["sha256"], "destinationPath": destination,
               "destinationIdentity": target, "retainedOriginalPath": retained,
               "retainedOriginalIdentity": retained_identity, "baselineSemanticEvidence": spec["baselineSemanticEvidence"],
               "afterSemanticSha256": evidence_sha, "explanation": spec["explanation"],
               "semanticCoverage": before_evidence["coverage"]}
    raw = canonical(receipt)
    path = state / "migration-reviews" / (digest(raw) + ".json")
    write_private(path, raw, mode=0o400)
    return {"status": "recorded", "receipt": str(path), "sourcePath": source, "destinationPath": destination}


def verify(state, phase="unspecified"):
    state = private_dir(state)
    baseline, identity = load_baseline(state)
    plan = baseline["plan"]
    current, contents, external, _ = collect(plan, forbidden=state)
    errors, additions, structured_changes, mutable_changes = [], {}, [], []
    reviews = {}
    for receipt in approvals(state, "addition-reviews"):
        if receipt["baselineSha256"] != identity:
            raise PreservationError("Addition review belongs to another baseline")
        for path, item in receipt["entries"].items():
            if path in reviews and reviews[path] != item:
                raise PreservationError("Conflicting addition review identities")
            reviews[path] = item
    migrations, migration_entries = {}, {}
    for receipt in approvals(state, "migration-reviews"):
        if receipt["baselineSha256"] != identity:
            raise PreservationError("Migration review belongs to another baseline")
        source = receipt["sourcePath"]
        if source in migrations:
            raise PreservationError("Duplicate migration source")
        migrations[source] = receipt
        for path, item in [(receipt["destinationPath"], receipt["destinationIdentity"]),
                           (receipt["retainedOriginalPath"], receipt["retainedOriginalIdentity"])]:
            if path in migration_entries and migration_entries[path] != item:
                raise PreservationError("Conflicting migration identities")
            migration_entries[path] = item
        evidence = read_regular(state / "migration-evidence" / receipt["afterSemanticSha256"])[0]
        if digest(evidence) != receipt["afterSemanticSha256"]:
            raise PreservationError("Migration semantic evidence changed")
    structured_rules = {}
    for kind, fmt in [("additiveJson", "json"), ("additiveToml", "toml")]:
        for item in plan.get(kind, []):
            structured_rules[item["path"]] = (fmt, item["allowedPointers"])
    identity_entries = copy.deepcopy(current)
    mutable_values = {}
    for item in plan.get("mutableJson", []):
        path = item["path"]
        before_entry = baseline["entries"].get(path, {})
        after_entry = current.get(path, {})
        if before_entry.get("type") != "file" or after_entry.get("type") != "file":
            errors.append({"path": path, "reason": "mutable-metadata-file-missing-or-type-changed"})
            continue
        before_data = read_regular(state / "originals" / before_entry["sha256"])[0]
        if digest(before_data) != before_entry["sha256"]:
            raise PreservationError("Original mutable JSON backup changed")
        try:
            before_value = json_load(before_data, "original mutable metadata JSON")
            after_value = json_load(contents[path], "current mutable metadata JSON")
            before_normalized = normalize_mutable(before_value, before_value, item["pointers"])
            after_normalized = normalize_mutable(after_value, before_value, item["pointers"])
        except PreservationError:
            errors.append({"path": path, "reason": "mutable-metadata-presence-type-or-json-invalid"})
            continue
        mutable_values[path] = (before_normalized, after_normalized)
        normalized_bytes = canonical(after_normalized)
        identity_entries[path].update(sha256=digest(normalized_bytes), size=len(normalized_bytes),
                                      identityMode="json-with-reviewed-metadata-leaves")
        if before_entry != after_entry:
            mutable_changes.append({"path": path, "pointers": item["pointers"],
                                    "beforeSha256": before_entry["sha256"], "afterSha256": after_entry["sha256"]})
    for path, before in baseline["entries"].items():
        after = current.get(path, {"type": "missing"})
        if before == after:
            continue
        if before["type"] == "missing":
            if after["type"] != "missing":
                additions[path] = after
            continue
        migration = migrations.get(path)
        if migration:
            expected = migration["destinationIdentity"] if path == migration["destinationPath"] else {"type": "missing"}
            if after == expected:
                continue
        if path in mutable_values and all(before[key] == after[key] for key in ("mode", "uid", "gid")):
            old, new = mutable_values[path]
            if path not in structured_rules and exact_value(old, new):
                continue
        if path in structured_rules and before["type"] == after["type"] == "file":
            if all(before[key] == after[key] for key in ("mode", "uid", "gid")):
                old = read_regular(state / "originals" / before["sha256"])[0]
                if digest(old) != before["sha256"]:
                    raise PreservationError("Original configuration backup changed")
                fmt, scopes = structured_rules[path]
                old_value, new_value = mutable_values[path] if path in mutable_values else (structured(old, fmt), structured(contents[path], fmt))
                if additive_preserved(old_value, new_value, scopes):
                    structured_changes.append({"path": path, "format": fmt, "allowedPointers": scopes,
                                               "beforeSha256": before["sha256"], "afterSha256": after["sha256"]})
                    continue
        errors.append({"path": path, "reason": "existing-item-changed", "before": before, "after": after})
    for path, item in current.items():
        if path not in baseline["entries"] and item["type"] != "missing":
            additions[path] = item
    for path, item in migration_entries.items():
        if path in current:
            observed = current[path]
        else:
            try:
                data, info = read_regular(path)
                observed = dict(type="file", sha256=digest(data), size=len(data), **metadata(info))
            except PreservationError:
                observed = {"type": "missing"}
        if observed != item:
            errors.append({"path": path, "reason": "reviewed-migration-output-changed"})
    unreviewed = {path: item for path, item in additions.items()
                  if reviews.get(path) != item and migration_entries.get(path) != item}
    for path, item in reviews.items():
        if current.get(path) != item:
            errors.append({"path": path, "reason": "reviewed-addition-changed-or-removed"})
    salt = read_regular(state / "environment-salt")[0]
    actual_env = env_fingerprints(plan.get("envNames", []), salt)
    env_changes = [name for name in baseline["environment"] if baseline["environment"][name] != actual_env[name]]
    # Check every backup, even when the active file remains unchanged.
    for sha in sorted({x["sha256"] for x in baseline["entries"].values() if x["type"] == "file"} |
                      {x["sha256"] for x in baseline.get("semanticEvidence", {}).values()}):
        if digest(read_regular(state / "originals" / sha, int(plan.get("maxFileBytes", MAX_FILE)))[0]) != sha:
            raise PreservationError("Immutable original backup changed")
    return {"schemaVersion": SCHEMA, "status": "preserved" if not errors and not unreviewed and not env_changes else "blocked",
            "verifiedAt": now(), "phase": phase, "baselineSha256": identity, "planSha256": baseline["planSha256"],
            "configurationIdentity": digest(canonical({"entries": identity_entries, "environment": actual_env})),
            "protectedRoots": sorted({item["path"] for item in plan["roots"]} |
                                     set(baseline.get("followedSymlinkTargets", [])) | set(external)),
            "protectedEntries": len(baseline["entries"]), "errors": errors, "environmentChangedNames": env_changes,
            "structuredAdditiveChanges": structured_changes, "additions": additions, "unreviewedAdditions": unreviewed,
            "reviewedMutableJsonChanges": mutable_changes,
            "reviewedMigrations": len(migrations), "followedSymlinkTargets": external,
            "scope": "Declared configuration only; excluded live histories/DBs are neither deleted nor certified as consistent backups"}


def discover(home):
    home = absolute(str(home))
    config = absolute(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    data = absolute(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
    claude = absolute(os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude")))
    codex = absolute(os.environ.get("CODEX_HOME", str(home / ".codex")))
    # Match pinned OMP19 utils/src/dirs.ts. Node path.join appends an absolute
    # second argument; Python Path / would incorrectly discard the home prefix.
    omp_root = Path(os.path.normpath(str(home) + "/" + (os.environ.get("PI_CONFIG_DIR") or ".omp")))
    profile_value = os.environ.get("OMP_PROFILE", os.environ.get("PI_PROFILE", "")).strip()
    profile = None if profile_value in ("", "default") else profile_value
    if profile and (not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", profile) or profile in (".", "..")
                    or profile.endswith(".") or re.match(r"^(?:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?$", profile, re.I)):
        raise PreservationError("OMP profile environment is invalid for the pinned client; inspect current launch settings")
    if profile:
        omp = omp_root / "profiles" / profile / "agent"
    elif os.environ.get("PI_CODING_AGENT_DIR"):
        omp = Path(os.path.abspath(os.environ["PI_CODING_AGENT_DIR"]))
    else:
        omp = omp_root / "agent"
    roots = []
    def root(path, role, exclusions=None):
        item = {"path": str(path), "role": role, "exclude": exclusions or []}
        if exclusions:
            item["exclusionReason"] = "Suggested mutable logs/caches/session data; receiving agent must inspect exclusions, preserve these files in place and arrange supported live-state backups separately."
        roots.append(item)
    root(claude, "Claude configuration, skills, hooks, memory and agent instructions",
         ["debug/**", "telemetry/**", "statsig/**", "cache/**", "tmp/**", "todos/**", "tasks/**", "projects/**/*.jsonl", "history.jsonl"])
    root(home / ".claude.json", "Claude existing user/route state")
    root(codex, "Codex configuration, hooks, agents and instructions",
         ["sessions/**", "archived_sessions/**", "log/**", "logs/**", "tmp/**", "shell_snapshots/**", "history.jsonl", "state*.sqlite*", "models_cache.json", "version.json"])
    root(home / ".agents", "Shared Codex skills and agent instructions")
    root(omp, "Candidate OMP active profile; named profiles and launch flags must be inspected",
         ["sessions/**", "logs/**", "cache/**", "tmp/**", "history.jsonl", "*.sock", "*.lock"])
    root(config / "opencode", "OpenCode configuration, skills, plugins and instructions", ["node_modules/**", "cache/**"])
    root(data / "opencode/auth.json", "OpenCode existing credential configuration")
    for name in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR"):
        value = os.environ.get(name)
        if value and Path(value).is_absolute():
            root(Path(value), name + " explicit environment location")
    roots = list({item["path"]: item for item in roots}.values())
    env_names = {"CLAUDE_CONFIG_DIR", "CODEX_HOME", "PI_CODING_AGENT_DIR", "PI_CONFIG_DIR", "PI_CONFIG_FILES",
                 "OMP_PROFILE", "PI_PROFILE", "OMP_AGENT_DIR", "OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR",
                 "OPENCODE_CONFIG_CONTENT", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME",
                 "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL",
                 "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "SSL_CERT_FILE", "SSL_CERT_DIR",
                 "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY"}
    for name in os.environ:
        if re.search(r"(^|_)(API_KEY|AUTH_TOKEN|BASE_URL|ENDPOINT|MODEL|PROVIDER)(_|$)", name):
            env_names.add(name)
    return {"schemaVersion": SCHEMA, "operatorHome": str(home), "discoveryComplete": False,
            "discoveryEvidence": "", "roots": roots, "envNames": sorted(env_names),
            "additiveJson": [], "additiveToml": [], "mutableJson": [], "semanticEvidence": [],
            "maxFileBytes": MAX_FILE, "maxTotalBytes": MAX_TOTAL, "maxFiles": MAX_FILES,
            "requiredDiscovery": [
                "Inspect actual aliases/functions/wrappers, command-line --profile/--config/--agent-dir flags and cwd; a default directory is not proof of the active profile.",
                "Before invoking any new OMP binary, take the filesystem snapshot. Even new `omp config path` initializes settings and can migrate settings.json/config.yml/agent.db. Inspect current-version commands and copied-profile rehearsals for OMP_PROFILE, PI_PROFILE, PI_CONFIG_DIR, PI_CONFIG_FILES, named profiles and command-line overrides. Add every effective root/overlay.",
                "Inspect OMP_AGENT_DIR only if the installed fork actually consumes it; do not assume unsupported variables change the profile.",
                "Add project .omp/.claude/.codex/.opencode roots and all AGENTS.md, CLAUDE.md, SYSTEM.md, SYSTEM_TEMPLATE.md, APPEND_SYSTEM.md, RULES.md, memory/brain roots, managed-skills, extensions and custom hook targets that are actually consumed.",
                "Add referenced internal CA files and credential-source configuration; never put raw secret values into the handoff or the discoveryEvidence prose.",
                "Review every exclusion; mutable DB/session contents remain in place and need application-aware backups. Do not exclude config/brain directories to obtain a passing result.",
                "Before native format migrations, capture a private canonical effective-configuration JSON export as semanticEvidence; use copied-profile rehearsal and retain the original bytes.",
                "Declare only inspected additive JSON/TOML pointers with concrete reasons; protect existing route/auth/model/permission values. New files require exact addition review after installation.",
                "Use an operator-owned mode-0700 preservation state outside all protected roots. Acknowledge completeness only after all actual roots and launch contexts are identified."
            ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("discover")
    command.add_argument("--home", required=True)
    command.add_argument("--output", required=True)
    command = commands.add_parser("snapshot")
    command.add_argument("--plan", required=True)
    command.add_argument("--state", required=True)
    command = commands.add_parser("verify")
    command.add_argument("--state", required=True)
    command.add_argument("--report")
    command.add_argument("--phase", default="unspecified")
    for name in ("record-additions", "record-migration"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True)
        command.add_argument("--spec", required=True)
    args = parser.parse_args()
    if args.command == "discover":
        plan = discover(args.home)
        write_private(absolute(args.output), canonical(plan))
        result = {"status": "discovery-required", "plan": args.output, "candidateRoots": len(plan["roots"])}
    elif args.command == "snapshot":
        result = snapshot(absolute(args.plan), absolute(args.state))
    elif args.command == "record-additions":
        result = record_additions(absolute(args.state), absolute(args.spec))
    elif args.command == "record-migration":
        result = record_migration(absolute(args.state), absolute(args.spec))
    else:
        result = verify(absolute(args.state), args.phase)
        if args.report:
            write_private(absolute(args.report), canonical(result), exclusive=False)
            result = {"status": result["status"], "baselineSha256": result["baselineSha256"],
                      "configurationIdentity": result["configurationIdentity"],
                      "errors": len(result["errors"]), "unreviewedAdditions": len(result["unreviewedAdditions"]),
                      "environmentChangedNames": result["environmentChangedNames"], "report": args.report}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") not in ("blocked",) else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (PreservationError, OSError, KeyError, TypeError) as exc:
        # JSON decode snippets and environment values must not leak through errors.
        message = str(exc) if isinstance(exc, PreservationError) else type(exc).__name__
        print(json.dumps({"status": "error", "error": message}), file=sys.stderr)
        sys.exit(1)
