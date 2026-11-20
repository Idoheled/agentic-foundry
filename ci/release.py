#!/usr/bin/env python3
"""Validate release identity and publish only after full offline-payload verification."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request

TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?")
SHA = re.compile(r"[a-f0-9]{40}|[a-f0-9]{64}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class Blocked(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise Blocked(message)


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)
    need(result.returncode == 0, "Git could not validate release identity: " + result.stderr.strip())
    return result.stdout.strip()


def regular(root, relative):
    path = root / relative
    need(not path.is_symlink() and path.is_file(), "Missing regular release file: " + relative)
    need(path.resolve().is_relative_to(root.resolve()), "Release file leaves the repository: " + relative)
    return path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(root, tag, expected_sha=None):
    need(TAG.fullmatch(tag), "Use an exact semantic-version tag such as v0.1.0")
    need(Path(git(root, "rev-parse", "--show-toplevel")).resolve() == root.resolve(), "Run from the repository root")
    need(not git(root, "status", "--porcelain", "--untracked-files=no"), "Tracked release files must be committed and unchanged")
    version = regular(root, "VERSION").read_text().strip()
    need(tag == "v" + version, "Tag and VERSION do not match")
    notes = regular(root, "releases/" + tag + ".md")
    need(notes.read_text().strip(), "Release notes are empty")
    git(root, "ls-files", "--error-unmatch", "VERSION", "releases/" + tag + ".md", "offline/manifest.json", "payload.lock.json")
    need(git(root, "cat-file", "-t", "refs/tags/" + tag) == "tag", "Release tags must be annotated and already exist")
    commit = git(root, "rev-parse", "--verify", "refs/tags/" + tag + "^{commit}")
    need(SHA.fullmatch(commit), "Invalid tag commit")
    need(git(root, "rev-parse", "HEAD") == commit, "The checkout must be exactly the selected release commit")
    if expected_sha is not None:
        need(SHA.fullmatch(expected_sha) and expected_sha == commit, "Tag changed after source validation")
    return {"passed": True, "tag": tag, "version": version, "commit": commit, "notes": str(notes)}


def payload_check(root, operation):
    result = subprocess.run([sys.executable, "-B", str(regular(root, "scripts/offline_payload.py")), operation],
                            cwd=root, text=True, capture_output=True, check=False)
    need(result.returncode == 0, "Offline payload " + operation + " failed: " + result.stderr.strip()[-2000:])
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise Blocked("Payload verifier did not return complete JSON") from exc
    need(isinstance(report, dict) and report.get("passed") is True, "Payload verification did not pass")
    return report


def remote_payload_check(root, repository, tag, token, username, workers=4):
    payload_check(root, "validate")
    manifest = json.loads(regular(root, "offline/manifest.json").read_text())
    source = Path(__file__).with_name("remote_lfs.py")
    spec = importlib.util.spec_from_file_location("foundry_remote_lfs", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    last_reported = 0

    def progress(complete, total):
        nonlocal last_reported
        if complete - last_reported >= 50 or complete == total:
            print("Remote payload verification: " + str(complete) + "/" + str(total) + " files", file=sys.stderr, flush=True)
            last_reported = complete

    try:
        verifier = module.RemoteLfs(repository, token, username, tag)
        return verifier.verify(manifest, workers=workers, progress=progress)
    except module.LfsBlocked as exc:
        raise Blocked(str(exc)) from None


def capacity(root):
    payload_check(root, "validate")
    manifest = json.loads(regular(root, "offline/manifest.json").read_text())
    sizes = [entry["bytes"] for entry in manifest["objects"].values()]
    need(all(type(size) is int and size >= 0 for size in sizes), "Invalid object size")
    objects = sum(sizes)
    required = objects * 2 + 2 * 1024 ** 3
    available = shutil.disk_usage(root).free
    result = {"passed": available >= required, "objectBytes": objects,
              "requiredFreeBytes": required, "availableFreeBytes": available,
              "scope": "Git LFS cache plus checked-out objects and 2 GiB working margin; no payload hydration"}
    need(result["passed"], "LFS release verification needs at least " + str(required) + " free bytes; only " +
         str(available) + " available. Select a runner with sufficient disk space.")
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Blocked("Authenticated release API redirects are not followed")


class Github:
    def __init__(self, token):
        need(token, "GH_TOKEN is required only for publication")
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, value=None, missing_ok=False, file=None):
        url = path if path.startswith("https://") else "https://api.github.com" + path
        parsed = urllib.parse.urlsplit(url)
        need(parsed.scheme == "https" and parsed.hostname in ("api.github.com", "uploads.github.com") and
             parsed.username is None and parsed.password is None and parsed.port in (None, 443), "Unexpected release API host")
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "agentic-foundry-release"}
        data = None
        if value is not None:
            data = json.dumps(value).encode()
            headers["Content-Type"] = "application/json"
        stream = None
        if file is not None:
            stream = file.open("rb")
            data = stream
            headers["Content-Type"] = "application/octet-stream"
            headers["Content-Length"] = str(file.stat().st_size)
        try:
            req = urllib.request.Request(url, method=method, headers=headers, data=data)
            with self.opener.open(req, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            raise Blocked("GitHub release API returned HTTP " + str(exc.code) + "; inspect the retained release state before retrying") from exc
        except (OSError, ValueError) as exc:
            raise Blocked("GitHub release request did not complete; inspect the remote state before retrying") from exc
        finally:
            if stream:
                stream.close()

    def upload(self, upload_url, path):
        return self.request("POST", upload_url + "?name=" + urllib.parse.quote(path.name), file=path)


def remote_commit(api, repository, tag):
    base = "/repos/" + repository
    current = api.request("GET", base + "/git/ref/tags/" + urllib.parse.quote(tag, safe=""))["object"]
    for _ in range(8):
        if current.get("type") == "commit":
            return current.get("sha")
        need(current.get("type") == "tag" and SHA.fullmatch(current.get("sha", "")), "Unexpected remote tag identity")
        current = api.request("GET", base + "/git/tags/" + current["sha"])["object"]
    raise Blocked("Remote tag has too many indirections")


def source_archive(root, commit, tag, destination):
    """Archive raw committed blobs; never run archive conversion or LFS filters."""
    need(SHA.fullmatch(commit) and TAG.fullmatch(tag), "Invalid source archive identity")
    need(not destination.exists() and not destination.is_symlink(), "Preserving an existing source archive")
    # A partial clone must fail on a missing Git object, not fetch it. Clear Git
    # caller overrides and prohibit every transport as a second independent gate.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1", GIT_ALLOW_PROTOCOL="",
               GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS="0", GIT_LFS_SKIP_SMUDGE="1")
    command = ["git", "--no-replace-objects", "-c", "protocol.allow=never", "-C", str(root)]
    tree = subprocess.run([*command, "ls-tree", "-r", "-l", "-z", "--full-tree", commit],
                          env=env, capture_output=True, check=False)
    need(tree.returncode == 0, "Cannot read the committed source tree without fetching Git objects")
    entries = {}
    for record in tree.stdout.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, oid, raw_size = metadata.split()
        path = raw_path.decode("utf-8")
        parts = PurePosixPath(path)
        need(not parts.is_absolute() and ".." not in parts.parts and ".git" not in parts.parts,
             "Unsafe committed source path")
        need(kind == b"blob" and mode in (b"100644", b"100755"),
             "Source archive requires regular files; symlinks and submodules are not expanded")
        need(raw_size.isdigit(), "A required source Git object is unavailable locally")
        entries[path] = (mode, oid.decode("ascii"), int(raw_size))
    need(entries and sum(entry[2] for entry in entries.values()) < 2 * 1024 ** 3,
         "Committed source blobs exceed the source-asset budget; large artifacts must be Git LFS pointers")
    need("offline/manifest.json" in entries, "The committed source has no offline manifest")
    need("payload.lock.json" in entries and entries["payload.lock.json"][0] == b"100644",
         "The committed source has no regular payload lock")
    need(entries["offline/manifest.json"][0] == b"100644" and entries["offline/manifest.json"][2] <= 16 * 1024 ** 2,
         "Invalid committed offline manifest")

    class Blob:
        def __init__(self, pipe, oid, size):
            self.pipe, self.oid, self.remaining = pipe, oid, size
            self.digest = hashlib.sha1() if len(oid) == 40 else hashlib.sha256()
            self.digest.update(b"blob " + str(size).encode() + b"\0")
            self.content_digest = hashlib.sha256()

        def read(self, size=-1):
            data = self.pipe.read(self.remaining if size < 0 else min(size, self.remaining))
            self.remaining -= len(data)
            self.digest.update(data)
            self.content_digest.update(data)
            return data

        def finish(self):
            need(self.remaining == 0 and self.digest.hexdigest() == self.oid,
                 "Raw source blob failed its committed Git identity check")
            need(self.pipe.read(1) == b"\n", "Malformed raw Git object stream")

    committed_assets = {}
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([*command, "cat-file", "--batch"], env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)

        def blob(entry):
            _, oid, size = entry
            process.stdin.write(oid.encode() + b"\n")
            process.stdin.flush()
            header = process.stdout.readline(256).strip().split()
            need(header == [oid.encode(), b"blob", str(size).encode()],
                 "A required source Git object is unavailable without network access")
            return Blob(process.stdout, oid, size)

        created_archive = False
        try:
            manifest_blob = blob(entries["offline/manifest.json"])
            manifest = json.loads(manifest_blob.read())
            manifest_blob.finish()
            objects = manifest.get("objects")
            need(isinstance(objects, dict), "Invalid committed LFS object manifest")
            pointer_paths = {"offline/objects/sha256/" + oid + ".chunk" for oid in objects}
            observed = {path for path in entries if path.startswith("offline/objects/")}
            need(observed == pointer_paths, "Committed LFS pointer paths differ from the offline manifest")
            with destination.open("xb") as raw:
                created_archive = True
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0) as compressed:
                    with tarfile.open(mode="w|", fileobj=compressed, format=tarfile.PAX_FORMAT) as archive:
                        for path, entry in sorted(entries.items()):
                            mode, _, size = entry
                            source = blob(entry)
                            member = tarfile.TarInfo("agentic-foundry-" + tag + "/" + path)
                            member.mode = 0o755 if mode == b"100755" else 0o644
                            member.uid = member.gid = member.mtime = 0
                            member.size = size
                            if path in pointer_paths:
                                need(mode == b"100644" and size <= 256, "An LFS source entry is not a canonical pointer")
                                oid = PurePosixPath(path).stem
                                declared_size = objects[oid].get("bytes")
                                need(re.fullmatch(r"[a-f0-9]{64}", oid) and type(declared_size) is int and declared_size >= 0,
                                     "Invalid committed LFS object identity")
                                pointer = source.read()
                                expected = ("version https://git-lfs.github.com/spec/v1\noid sha256:" + oid +
                                            "\nsize " + str(declared_size) + "\n").encode()
                                need(pointer == expected, "Committed LFS pointer differs from its manifest identity")
                                archive.addfile(member, io.BytesIO(pointer))
                            else:
                                archive.addfile(member, source)
                            source.finish()
                            if path in ("offline/manifest.json", "payload.lock.json"):
                                committed_assets[path] = source.content_digest.hexdigest()
            process.stdin.close()
            need(process.wait(timeout=30) == 0, "Raw Git object reader failed")
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.wait()
            if created_archive:
                destination.unlink(missing_ok=True)
            raise
        finally:
            process.stdout.close()
            if not process.stdin.closed:
                process.stdin.close()
    return {"files": len(entries), "lfsPointers": len(pointer_paths), "bytes": destination.stat().st_size,
            "committedAssetSha256": committed_assets}


def publish(root, tag, expected_sha, repository, api, prerelease=False, payload_source="local", github_user=None, workers=4):
    need(REPOSITORY.fullmatch(repository) and ".." not in repository, "Use an owner/repository name")
    identity = validate(root, tag, expected_sha)
    # Full data verification precedes every remote mutation. This does not install tools.
    need(payload_source in ("local", "remote"), "Unknown payload verification source")
    if payload_source == "remote":
        verification = remote_payload_check(root, repository, tag, api.token,
                                            github_user or repository.split("/")[0].lower(), workers)
    else:
        verification = payload_check(root, "verify")
    print("Payload verification complete: " + str(verification.get("files", "?")) + " files, " +
          str(verification.get("objects", "?")) + " objects", file=sys.stderr, flush=True)
    need(remote_commit(api, repository, tag) == identity["commit"], "Remote tag differs from the verified commit")
    base = "/repos/" + repository
    existing = api.request("GET", base + "/releases/tags/" + urllib.parse.quote(tag, safe=""), missing_ok=True)
    need(existing is None, "Release already exists; this workflow never overwrites a draft or published release")
    created = None
    try:
        with tempfile.TemporaryDirectory(prefix="agentic-foundry-release-") as scratch:
            output = Path(scratch)
            archive = output / ("agentic-foundry-" + tag + "-source.tar.gz")
            print("Creating source archive from committed Git blobs and LFS pointers; no hydration or network", file=sys.stderr, flush=True)
            archive_report = source_archive(root, identity["commit"], tag, archive)
            print("Source archive complete: " + str(archive_report["files"]) + " files, " +
                  str(archive_report["lfsPointers"]) + " LFS pointers, " + str(archive_report["bytes"]) +
                  " bytes", file=sys.stderr, flush=True)
            for source_name, asset_name in (("offline/manifest.json", "offline-manifest.json"),
                                            ("payload.lock.json", "payload.lock.json")):
                asset = output / asset_name
                shutil.copyfile(regular(root, source_name), asset)
                need(sha256(asset) == archive_report["committedAssetSha256"][source_name],
                     "Release asset differs from its committed source: " + source_name)
            report = {"schemaVersion": 1, "tag": tag, "commit": identity["commit"],
                      "verifiedAt": datetime.now(timezone.utc).isoformat(),
                      "scope": "Release identity and full LFS payload integrity; not target-machine acceptance",
                      "payloadVerification": verification,
                      "manifestSha256": archive_report["committedAssetSha256"]["offline/manifest.json"],
                      "payloadLockSha256": archive_report["committedAssetSha256"]["payload.lock.json"]}
            (output / "RELEASE-VERIFICATION.json").write_text(json.dumps(report, indent=2) + "\n")
            assets = sorted(output.iterdir())
            sums = output / "SHA256SUMS"
            sums.write_text("".join(sha256(path) + "  " + path.name + "\n" for path in assets))
            assets.append(sums)
            need(all(path.stat().st_size < 2 * 1024 ** 3 for path in assets), "A release asset exceeds the 2 GiB asset limit")
            notes = Path(identity["notes"]).read_text()
            notes += ("\n\n### Release contents\n\n"
                      "The source archive contains Git LFS pointers, not the offline object bytes. "
                      "Clone this exact tag with Git LFS and follow the repository's payload instructions "
                      "to obtain the complete offline kit. The manifest, payload lock, verification report "
                      "and asset checksums bind this release to its supplied files.\n")
            created = api.request("POST", base + "/releases", {"tag_name": tag, "target_commitish": identity["commit"],
                                   "name": "Agentic Foundry " + tag, "body": notes, "draft": True,
                                   "prerelease": prerelease, "generate_release_notes": False})
            release_id = created.get("id")
            need(type(release_id) is int and release_id > 0 and created.get("draft") is True, "GitHub did not confirm the draft release")
            upload_url = created.get("upload_url", "").split("{", 1)[0]
            expected_upload = "https://uploads.github.com" + base + "/releases/" + str(release_id) + "/assets"
            need(upload_url == expected_upload, "Unexpected release upload destination")
            recorded = {}
            for path in assets:
                actual = api.upload(upload_url, path)
                expected_digest = "sha256:" + sha256(path)
                need(actual.get("name") == path.name and actual.get("size") == path.stat().st_size and
                     actual.get("state") == "uploaded", "GitHub did not confirm the complete release asset: " + path.name)
                if actual.get("digest") is not None:
                    need(actual["digest"] == expected_digest, "Remote asset digest differs: " + path.name)
                recorded[path.name] = {"bytes": path.stat().st_size, "sha256": expected_digest[7:]}
            draft = api.request("GET", base + "/releases/" + str(release_id))
            need(draft.get("draft") is True and draft.get("tag_name") == tag, "Draft release changed before publication")
            seen = {entry.get("name"): entry for entry in draft.get("assets", [])}
            need(set(seen) == set(recorded), "Draft assets differ from the completed upload set")
            for name, entry in recorded.items():
                need(seen[name].get("state") == "uploaded" and seen[name].get("size") == entry["bytes"], "Incomplete draft asset: " + name)
                if seen[name].get("digest") is not None:
                    need(seen[name]["digest"] == "sha256:" + entry["sha256"], "Draft asset digest changed: " + name)
            need(remote_commit(api, repository, tag) == identity["commit"], "Remote tag changed before publication")
            api.request("PATCH", base + "/releases/" + str(release_id), {"draft": False})
            published = api.request("GET", base + "/releases/" + str(release_id))
            need(published.get("draft") is False and published.get("tag_name") == tag, "Publication outcome was not confirmed")
            return {"passed": True, "tag": tag, "commit": identity["commit"], "releaseId": release_id,
                    "url": "https://github.com/" + repository + "/releases/tag/" + tag, "assets": recorded,
                    "scope": "Published source and payload-integrity evidence; target acceptance remains separate"}
    except BaseException:
        if created is not None:
            print("A release was created or publication was attempted. Inspect its current state before retrying: " +
                  "https://github.com/" + repository + "/releases/tag/" + tag, file=sys.stderr)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "capacity", "publish"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tag")
    parser.add_argument("--expected-sha")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--prerelease", choices=("true", "false"), default="true")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--payload-source", choices=("local", "remote"), default="local")
    parser.add_argument("--github-user")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "capacity":
        result = capacity(root)
    else:
        need(args.tag, "An exact existing release tag is required")
        if args.command == "validate":
            result = validate(root, args.tag, args.expected_sha)
            if args.github_output:
                with args.github_output.open("a") as stream:
                    stream.write("tag=" + result["tag"] + "\ncommit=" + result["commit"] + "\n")
        else:
            need(args.repository and args.expected_sha, "Publication requires repository and validated commit identity")
            result = publish(root, args.tag, args.expected_sha, args.repository,
                             Github(os.environ.get("GH_TOKEN", "")), args.prerelease == "true",
                             args.payload_source, args.github_user, args.workers)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Blocked, OSError, ValueError, KeyError, TypeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        sys.exit(2)
