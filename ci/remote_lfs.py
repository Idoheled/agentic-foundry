#!/usr/bin/env python3
"""Verify a complete GitHub LFS payload by streaming bytes without a full checkout."""
import base64
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
import hashlib
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

# Observed from this repository's authenticated, genuine Git LFS batch response.
# Expanding this list is a reviewed source change, never an arbitrary URL option.
DOWNLOAD_HOSTS = frozenset({"github-cloud.githubusercontent.com"})
BLOCK_BYTES = 4 * 1024 * 1024
SMALL_OBJECT_BYTES = 2 * 1024 * 1024
CACHE_BYTES = 32 * 1024 * 1024
BATCH_OBJECTS = 100
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class LfsBlocked(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise LfsBlocked(message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LfsBlocked("Git LFS verification does not follow redirects")


class RemoteLfs:
    def __init__(self, repository, token, username, tag, *, opener=None):
        need(REPOSITORY.fullmatch(repository) and ".." not in repository, "Invalid GitHub repository")
        need(token and username and ":" not in username and not any(c in username for c in "\r\n"), "GitHub LFS credentials are missing or invalid")
        self.repository = repository
        self.token = token
        self.tag = tag
        self.batch_url = "https://github.com/" + repository + ".git/info/lfs/objects/batch"
        self.auth = "Basic " + base64.b64encode((username + ":" + token).encode()).decode()
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        self.cached_bytes = 0
        self.pending = {}
        self.verified = set()
        self.transferred_bytes = 0

    def batch(self, objects):
        need(0 < len(objects) <= BATCH_OBJECTS, "Invalid LFS batch size")
        body = {"operation": "download", "transfers": ["basic"], "ref": {"name": "refs/tags/" + self.tag},
                "objects": [{"oid": oid, "size": size} for oid, size in objects.items()]}
        request = urllib.request.Request(self.batch_url, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": self.auth, "Accept": "application/vnd.git-lfs+json",
            "Content-Type": "application/vnd.git-lfs+json", "User-Agent": "agentic-foundry-release"})
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
            need(len(raw) <= 16 * 1024 * 1024, "LFS batch response is too large")
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise LfsBlocked("GitHub LFS batch returned HTTP " + str(exc.code)) from exc
        except (OSError, ValueError) as exc:
            raise LfsBlocked("GitHub LFS batch request did not complete") from exc
        need(isinstance(result, dict) and result.get("transfer", "basic") == "basic", "Unsupported LFS transfer protocol")
        entries = result.get("objects")
        need(isinstance(entries, list), "LFS batch response has no object list")
        actions = {}
        for entry in entries:
            need(isinstance(entry, dict), "Invalid LFS object response")
            oid = entry.get("oid")
            need(oid in objects and oid not in actions and entry.get("size") == objects[oid], "LFS batch object identity differs")
            need(not entry.get("error"), "Remote LFS object is unavailable: " + oid)
            action = entry.get("actions", {}).get("download")
            need(isinstance(action, dict), "Remote LFS object has no download action: " + oid)
            actions[oid] = self.checked_action(action)
        need(set(actions) == set(objects), "LFS batch did not return every requested object")
        return actions

    def checked_action(self, action):
        href = action.get("href")
        need(isinstance(href, str) and len(href) <= 16384, "Invalid LFS download action")
        need(self.token not in href and self.auth not in href, "LFS download URL would forward repository credentials")
        try:
            parsed = urllib.parse.urlsplit(href)
            valid = (parsed.scheme == "https" and parsed.hostname in DOWNLOAD_HOSTS and parsed.port in (None, 443)
                     and parsed.username is None and parsed.password is None and not parsed.fragment)
        except ValueError:
            valid = False
        need(valid, "LFS download host is not in the reviewed GitHub host list")
        headers = action.get("header", {})
        need(isinstance(headers, dict) and len(headers) <= 24, "Invalid LFS download headers")
        checked = {"Accept-Encoding": "identity", "User-Agent": "agentic-foundry-release"}
        for name, value in headers.items():
            need(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9-]+", name) and isinstance(value, str), "Invalid LFS header")
            need(name.lower() not in ("host", "cookie", "authorization", "proxy-authorization", "content-length", "transfer-encoding"), "Unexpected LFS header")
            need("\r" not in value and "\n" not in value and self.token not in value and self.auth not in value,
                 "LFS download headers would forward repository credentials")
            checked[name] = value
        return {"href": href, "headers": checked}

    def stream(self, oid, size, action, consumer):
        # This request deliberately has no repository Authorization header. Only a
        # checked temporary action supplied by the exact authenticated batch is used.
        request = urllib.request.Request(action["href"], headers=action["headers"], method="GET")
        digest = hashlib.sha256()
        count = 0
        try:
            with self.opener.open(request, timeout=60) as response:
                encoding = response.headers.get("Content-Encoding", "identity")
                need(encoding in ("", "identity"), "Encoded LFS download is not accepted")
                length = response.headers.get("Content-Length")
                if length is not None:
                    need(int(length) == size, "Remote LFS object length differs: " + oid)
                while True:
                    block = response.read(min(BLOCK_BYTES, size - count + 1))
                    if not block:
                        break
                    count += len(block)
                    need(count <= size, "Remote LFS object has excess bytes: " + oid)
                    digest.update(block)
                    consumer(block)
        except urllib.error.HTTPError as exc:
            raise LfsBlocked("GitHub LFS download returned HTTP " + str(exc.code) + " for object " + oid) from exc
        except (OSError, ValueError) as exc:
            raise LfsBlocked("GitHub LFS download did not complete for object " + oid) from exc
        need(count == size and digest.hexdigest() == oid, "Remote LFS object failed its byte/hash check: " + oid)
        with self.lock:
            self.verified.add(oid)
            self.transferred_bytes += count

    def small(self, oid, size, action):
        with self.lock:
            if oid in self.cache:
                self.cache.move_to_end(oid)
                return self.cache[oid]
            pending = self.pending.get(oid)
            owner = pending is None
            if owner:
                pending = Future()
                self.pending[oid] = pending
        if not owner:
            return pending.result()
        try:
            buffer = bytearray()
            self.stream(oid, size, action, buffer.extend)
            data = bytes(buffer)
            with self.lock:
                while self.cache and self.cached_bytes + len(data) > CACHE_BYTES:
                    _, retired = self.cache.popitem(last=False)
                    self.cached_bytes -= len(retired)
                self.cache[oid] = data
                self.cached_bytes += len(data)
                del self.pending[oid]
                pending.set_result(data)
            return data
        except BaseException as exc:
            with self.lock:
                self.pending.pop(oid, None)
                pending.set_exception(exc)
            raise

    def file(self, entry, objects, actions):
        digest = hashlib.sha256()
        count = 0
        for oid in entry["chunks"]:
            size = objects[oid]["bytes"]
            if size <= SMALL_OBJECT_BYTES:
                digest.update(self.small(oid, size, actions[oid]))
            else:
                self.stream(oid, size, actions[oid], digest.update)
            count += size
        need(count == entry["bytes"] and digest.hexdigest() == entry["sha256"], "Reconstructed remote payload file failed its hash/size check")

    def verify(self, manifest, workers=4, progress=None):
        need(type(workers) is int and 1 <= workers <= 8, "Remote verification workers must be between 1 and 8")
        files = manifest["files"]
        objects = manifest["objects"]
        # Identical complete files share one streaming proof. Different file hashes
        # or chunk order require independent reconstruction. Small shared chunks use
        # a bounded in-memory cache; large objects never accumulate in memory.
        groups = OrderedDict()
        for path, entry in files.items():
            identity = (entry["sha256"], entry["bytes"], tuple(entry["chunks"]))
            groups.setdefault(identity, {"entry": entry, "paths": []})["paths"].append(path)
        waves = []
        wave = []
        wave_ids = set()
        for group in groups.values():
            ids = set(group["entry"]["chunks"])
            if wave and len(wave_ids | ids) > BATCH_OBJECTS:
                waves.append(wave)
                wave = []
                wave_ids = set()
            wave.append(group)
            wave_ids.update(ids)
        if wave:
            waves.append(wave)
        complete = 0
        for wave in waves:
            ids = sorted({oid for group in wave for oid in group["entry"]["chunks"]})
            actions = {}
            for offset in range(0, len(ids), BATCH_OBJECTS):
                selected = ids[offset:offset + BATCH_OBJECTS]
                actions.update(self.batch({oid: objects[oid]["bytes"] for oid in selected}))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(self.file, group["entry"], objects, actions): group for group in wave}
                for future in as_completed(futures):
                    group = futures[future]
                    future.result()
                    complete += len(group["paths"])
                    if progress is not None:
                        progress(complete, len(files))
        need(self.verified == set(objects), "Not every declared LFS object was verified")
        return {"passed": True, "operation": "verify", "payloadSource": "remote",
                "files": len(files), "objects": len(objects), "payloadBytes": sum(entry["bytes"] for entry in files.values()),
                "objectBytes": sum(entry["bytes"] for entry in objects.values()), "transferredBytes": self.transferred_bytes,
                "uniqueFileReconstructions": len(groups), "release": manifest["release"],
                "scope": "Live GitHub LFS object bytes and reconstructed payload-file hashes; no target-machine execution"}
