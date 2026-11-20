import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/payload.py"


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.checkout = self.root / "checkout"; self.checkout.mkdir()
        self.mirror = self.root / "mirror"; (self.mirror / "payload/tools").mkdir(parents=True)
        self.data = b"verified runtime fixture"
        (self.mirror / "payload/tools/demo.bin").write_bytes(self.data)
        self.lock = {"schemaVersion": 1, "files": {"payload/tools/demo.bin": {"sha256": hashlib.sha256(self.data).hexdigest(), "bytes": len(self.data), "mode": 0o755}}}
        (self.checkout / "payload.lock.json").write_text(json.dumps(self.lock))

    def call(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--root", str(self.checkout)], capture_output=True, text=True)

    def test_private_mirror_hydration_and_verify(self):
        self.assertEqual(self.call("hydrate", "--from-dir", str(self.mirror)).returncode, 0)
        self.assertEqual(self.call("verify").returncode, 0)
        self.assertEqual(self.call("hydrate", "--from-dir", str(self.mirror)).returncode, 0)

    def test_differing_file_is_preserved(self):
        target = self.checkout / "payload/tools/demo.bin"; target.parent.mkdir(parents=True); target.write_bytes(b"private modification")
        self.assertEqual(self.call("hydrate", "--from-dir", str(self.mirror)).returncode, 2)
        self.assertEqual(target.read_bytes(), b"private modification")

    def test_hash_verified_archive_and_missing_file(self):
        archive = self.root / "release.tar.gz"
        with tarfile.open(archive, "w:gz") as out:
            info = tarfile.TarInfo("release/payload/tools/demo.bin"); info.size = len(self.data)
            out.addfile(info, io.BytesIO(self.data))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(self.call("hydrate", "--archive", str(archive), "--sha256", "0" * 64).returncode, 2)
        self.assertFalse((self.checkout / "payload").exists())
        self.assertEqual(self.call("hydrate", "--archive", str(archive), "--sha256", digest).returncode, 0)

    def test_archive_traversal_is_rejected(self):
        archive = self.root / "bad.tar"
        with tarfile.open(archive, "w") as out:
            info = tarfile.TarInfo("../escape"); info.size = 1; out.addfile(info, io.BytesIO(b"x"))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(self.call("hydrate", "--archive", str(archive), "--sha256", digest).returncode, 2)
        self.assertFalse((self.root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
