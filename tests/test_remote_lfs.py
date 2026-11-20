"""Streaming LFS verification uses local HTTP-response fixtures, never the network."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import threading
import unittest
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("remote_lfs", ROOT / "ci/remote_lfs.py")
lfs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lfs)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Response(io.BytesIO):
    def __init__(self, data, headers=None, read_sizes=None):
        super().__init__(data)
        self.headers = headers or {}
        self.read_sizes = read_sizes

    def read(self, size=-1):
        if self.read_sizes is not None:
            self.read_sizes.append(size)
        return super().read(size)


class LfsFixture:
    def __init__(self, data):
        self.data = data
        self.requests = []
        self.lock = threading.Lock()
        self.host = "github-cloud.githubusercontent.com"
        self.headers = {}
        self.corrupt = {}
        self.read_sizes = []
        self.fail_download = False

    def open(self, request, timeout=60):
        with self.lock:
            self.requests.append(request)
        if request.get_method() == "POST":
            body = json.loads(request.data)
            entries = [{"oid": item["oid"], "size": item["size"], "actions": {"download": {
                "href": "https://" + self.host + "/fixture/" + item["oid"] + "?signature=not-a-real-signature",
                "header": self.headers}}} for item in body["objects"]]
            return Response(json.dumps({"transfer": "basic", "objects": entries}).encode())
        oid = request.full_url.split("/fixture/", 1)[1].split("?", 1)[0]
        if self.fail_download:
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)
        data = self.corrupt.get(oid, self.data[oid])
        return Response(data, {"Content-Length": str(len(data))}, self.read_sizes)


class RemoteLfsTests(unittest.TestCase):
    def setUp(self):
        self.a = b"alpha"
        self.b = b"beta"
        self.data = {sha(self.a): self.a, sha(self.b): self.b}
        self.manifest = {"release": "fixture", "objects": {oid: {"bytes": len(data)} for oid, data in self.data.items()},
                         "files": {}}
        for path, parts in (("payload/ab", [self.a, self.b]), ("payload/ba", [self.b, self.a]),
                            ("payload/duplicate", [self.a, self.b]), ("payload/empty", [])):
            data = b"".join(parts)
            self.manifest["files"][path] = {"sha256": sha(data), "bytes": len(data), "mode": 0o644,
                                             "chunks": [sha(part) for part in parts]}

    def verifier(self, fixture):
        return lfs.RemoteLfs("Idoheled/agentic-foundry", "fixture-secret", "idoheled", "v0.1.0", opener=fixture)

    def test_all_objects_and_reconstructed_files_verify_with_bounded_cache(self):
        fixture = LfsFixture(self.data)
        verifier = self.verifier(fixture)
        result = verifier.verify(self.manifest, workers=4)
        self.assertTrue(result["passed"])
        self.assertEqual(result["files"], 4)
        self.assertEqual(result["uniqueFileReconstructions"], 3)
        self.assertEqual(result["objects"], 2)
        self.assertEqual(result["transferredBytes"], len(self.a) + len(self.b))
        self.assertEqual(sum(req.get_method() == "GET" for req in fixture.requests), 2)
        self.assertLessEqual(verifier.cached_bytes, lfs.CACHE_BYTES)

    def test_credentials_are_sent_only_to_exact_batch_endpoint(self):
        fixture = LfsFixture(self.data)
        self.verifier(fixture).verify(self.manifest)
        for request in fixture.requests:
            if request.get_method() == "POST":
                self.assertEqual(request.full_url, "https://github.com/Idoheled/agentic-foundry.git/info/lfs/objects/batch")
                self.assertTrue(request.get_header("Authorization").startswith("Basic "))
                self.assertEqual(json.loads(request.data)["ref"], {"name": "refs/tags/v0.1.0"})
            else:
                self.assertIsNone(request.get_header("Authorization"))
                self.assertNotIn("fixture-secret", request.full_url)

    def test_corrupt_object_blocks_verification(self):
        fixture = LfsFixture(self.data)
        fixture.corrupt[sha(self.a)] = b"wrong"
        with self.assertRaisesRegex(lfs.LfsBlocked, "byte/hash check"):
            self.verifier(fixture).verify(self.manifest)

    def test_chunk_reordering_fails_whole_file_hash(self):
        self.manifest["files"]["payload/ab"]["chunks"].reverse()
        with self.assertRaisesRegex(lfs.LfsBlocked, "Reconstructed remote payload file"):
            self.verifier(LfsFixture(self.data)).verify(self.manifest)

    def test_unreviewed_download_host_is_blocked_before_get(self):
        fixture = LfsFixture(self.data)
        fixture.host = "github-cloud.githubusercontent.com.invalid.example"
        with self.assertRaisesRegex(lfs.LfsBlocked, "reviewed GitHub host list"):
            self.verifier(fixture).verify(self.manifest)
        self.assertTrue(all(req.get_method() == "POST" for req in fixture.requests))

    def test_repository_credentials_cannot_be_forwarded_in_download_headers(self):
        fixture = LfsFixture(self.data)
        fixture.headers = {"Authorization": "Bearer fixture-secret"}
        with self.assertRaisesRegex(lfs.LfsBlocked, "Unexpected LFS header"):
            self.verifier(fixture).verify(self.manifest)
        self.assertTrue(all(req.get_method() == "POST" for req in fixture.requests))

    def test_large_object_is_streamed_and_not_cached(self):
        data = b"q" * (lfs.BLOCK_BYTES + 11)
        oid = sha(data)
        manifest = {"release": "fixture", "objects": {oid: {"bytes": len(data)}}, "files": {
            "payload/large": {"sha256": oid, "bytes": len(data), "mode": 0o755, "chunks": [oid]}}}
        fixture = LfsFixture({oid: data})
        verifier = self.verifier(fixture)
        self.assertTrue(verifier.verify(manifest)["passed"])
        self.assertEqual(verifier.cached_bytes, 0)
        self.assertGreater(len(fixture.read_sizes), 1)
        self.assertTrue(all(0 < size <= lfs.BLOCK_BYTES for size in fixture.read_sizes))

    def test_download_failure_does_not_expose_signed_url(self):
        fixture = LfsFixture(self.data)
        fixture.fail_download = True
        with self.assertRaises(lfs.LfsBlocked) as caught:
            self.verifier(fixture).verify(self.manifest)
        message = str(caught.exception)
        self.assertIn("HTTP 403", message)
        self.assertNotIn("signature", message)
        self.assertNotIn("https://", message)
        self.assertNotIn("fixture-secret", message)


if __name__ == "__main__":
    unittest.main()
