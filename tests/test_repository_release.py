"""Release publication boundaries; all network responses are explicit fixtures."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("foundry_release", ROOT / "ci/release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ApiFixture:
    def __init__(self, commit, *, corrupt_asset=False, wrong_upload=False):
        self.commit = commit
        self.corrupt_asset = corrupt_asset
        self.wrong_upload = wrong_upload
        self.calls = []
        self.assets = []
        self.draft = True

    def request(self, method, path, value=None, missing_ok=False):
        self.calls.append((method, path, value))
        if path.endswith("/git/ref/tags/v0.1.0"):
            return {"object": {"type": "tag", "sha": "1" * 40}}
        if "/git/tags/" in path:
            return {"object": {"type": "commit", "sha": self.commit}}
        if path.endswith("/releases/tags/v0.1.0"):
            return None
        if method == "POST" and path.endswith("/releases"):
            self.created = value
            return {"id": 1, "draft": True, "upload_url": (
                "https://invalid.example/assets{?name,label}" if self.wrong_upload else
                "https://uploads.github.com/repos/example/foundry/releases/1/assets{?name,label}")}
        if method == "PATCH":
            self.draft = value["draft"]
        return {"id": 1, "tag_name": "v0.1.0", "draft": self.draft, "assets": self.assets}

    def upload(self, url, path):
        self.calls.append(("UPLOAD", path.name, None))
        result = {"name": path.name, "size": path.stat().st_size, "state": "uploaded",
                  "digest": "sha256:" + ("0" * 64 if self.corrupt_asset else hashlib.sha256(path.read_bytes()).hexdigest())}
        self.assets.append(result)
        return result


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="foundry-release-test-")
        self.root = Path(self.tmp.name)
        files = {
            "VERSION": "0.1.0\n",
            "releases/v0.1.0.md": "# Release\n\nFixture release notes.\n",
            "offline/manifest.json": json.dumps({"objects": {"a" * 64: {"bytes": 100}}}),
            "payload.lock.json": "{}\n",
            "scripts/offline_payload.py": (
                "import json, pathlib, sys\n"
                "if pathlib.Path('payload-missing').exists():\n"
                " print('Missing actual fixture object', file=sys.stderr)\n"
                " sys.exit(2)\n"
                "print(json.dumps({'passed':True,'operation':sys.argv[-1],'files':1,'objects':1,'objectBytes':100,'payloadBytes':100}))\n"),
        }
        for name, content in files.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture Maintainer")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")
        self.git("add", ".")
        self.git("commit", "-qm", "Fixture source")
        self.git("tag", "-a", "v0.1.0", "-m", "Fixture release")
        self.commit = self.git("rev-parse", "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, text=True,
                              capture_output=True).stdout.strip()

    def publish(self, api):
        with contextlib.redirect_stderr(io.StringIO()):
            return release.publish(self.root, "v0.1.0", self.commit, "example/foundry", api)

    def test_annotated_tag_binds_committed_version_and_notes(self):
        result = release.validate(self.root, "v0.1.0", self.commit)
        self.assertEqual(result["commit"], self.commit)
        self.assertEqual(result["version"], "0.1.0")

    def test_lightweight_tag_is_rejected(self):
        self.git("tag", "-d", "v0.1.0")
        self.git("tag", "v0.1.0")
        with self.assertRaisesRegex(release.Blocked, "annotated"):
            release.validate(self.root, "v0.1.0")

    def test_dirty_source_and_changed_tag_are_rejected(self):
        with self.assertRaisesRegex(release.Blocked, "Tag changed"):
            release.validate(self.root, "v0.1.0", "0" * 40)
        (self.root / "VERSION").write_text("0.2.0\n")
        with self.assertRaisesRegex(release.Blocked, "committed and unchanged"):
            release.validate(self.root, "v0.1.0")

    def test_missing_payload_prevents_every_api_call(self):
        (self.root / "payload-missing").touch()
        api = ApiFixture(self.commit)
        with self.assertRaisesRegex(release.Blocked, "payload verify failed"):
            self.publish(api)
        self.assertEqual(api.calls, [])

    def test_moved_remote_tag_prevents_release_creation(self):
        api = ApiFixture("0" * 40)
        with self.assertRaisesRegex(release.Blocked, "Remote tag differs"):
            self.publish(api)
        self.assertFalse(any(call[0] in ("POST", "PATCH", "UPLOAD") for call in api.calls))

    def test_corrupt_uploaded_asset_never_publishes_draft(self):
        api = ApiFixture(self.commit, corrupt_asset=True)
        with self.assertRaisesRegex(release.Blocked, "digest differs"):
            self.publish(api)
        self.assertTrue(api.draft)
        self.assertFalse(any(call[0] == "PATCH" for call in api.calls))

    def test_upload_destination_is_bound_to_repository(self):
        api = ApiFixture(self.commit, wrong_upload=True)
        with self.assertRaisesRegex(release.Blocked, "upload destination"):
            self.publish(api)
        self.assertFalse(any(call[0] in ("UPLOAD", "PATCH") for call in api.calls))

    def test_complete_asset_set_is_verified_before_publish(self):
        api = ApiFixture(self.commit)
        result = self.publish(api)
        self.assertTrue(result["passed"])
        self.assertFalse(api.draft)
        self.assertEqual(set(result["assets"]), {
            "agentic-foundry-v0.1.0-source.tar.gz", "offline-manifest.json", "payload.lock.json",
            "RELEASE-VERIFICATION.json", "SHA256SUMS"})
        methods = [call[0] for call in api.calls]
        self.assertEqual(methods.count("UPLOAD"), 5)
        self.assertGreater(methods.index("PATCH"), max(i for i, value in enumerate(methods) if value == "UPLOAD"))
        self.assertTrue(api.created["draft"])
        self.assertIn("not the offline object bytes", api.created["body"])

    def test_capacity_accounts_for_cache_and_working_tree(self):
        with mock.patch.object(release.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(1, 1, 1)):
            with self.assertRaisesRegex(release.Blocked, "runner with sufficient disk"):
                release.capacity(self.root)
        with mock.patch.object(release.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(10**12, 1, 10**12-1)):
            report = release.capacity(self.root)
        self.assertEqual(report["requiredFreeBytes"], 200 + 2 * 1024**3)


if __name__ == "__main__":
    unittest.main()
