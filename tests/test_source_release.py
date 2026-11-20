import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import offline_payload
import source_integrity

SPEC = importlib.util.spec_from_file_location("foundry_export_release", REPO / "build-tools/export-release.py")
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class SourceReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="foundry-source-test-")
        self.base = Path(self.temp.name); self.root = self.base / "repo"; self.source = self.base / "payload-source"
        self.root.mkdir(); self.source.mkdir()
        body = b"offline runtime fixture\n"
        path = self.source / "payload/bin/runtime"; path.parent.mkdir(parents=True); path.write_bytes(body); path.chmod(0o755)
        lock = json.dumps({"schemaVersion": 1, "release": "fixture-r5", "files": {
            "payload/bin/runtime": {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "mode": 0o755}}}) + "\n"
        for directory in (self.root, self.source):
            (directory / "payload.lock.json").write_text(lock)
        (self.root / "VERSION").write_text("0.1.0\n")
        (self.root / "README.md").write_text("# Fixture source\n")
        (self.root / ".gitignore").write_text("payload/\noffline/objects/\ndist/\nreports/\n")
        (self.root / "setup.sh").write_text("#!/bin/bash\nexit 0\n"); (self.root / "setup.sh").chmod(0o755)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        offline_payload.pack(self.root, self.source, chunk_bytes=8, reflink="never")
        self.original_lock = (self.root / "payload.lock.json").read_bytes()

    def tearDown(self):
        self.temp.cleanup()

    def commit(self, tag="v0.1.0"):
        source_integrity.refresh(self.root)
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Fixture source"], check=True)
        subprocess.run(["git", "-C", str(self.root), "tag", tag], check=True)

    def hydrate(self):
        offline_payload.hydrate(self.root, offline_payload.load(self.root))

    def test_source_only_refresh_and_check_preserve_payload_lock(self):
        report = source_integrity.refresh(self.root)
        self.assertFalse(report["payloadBytesChecked"])
        self.assertFalse((self.root / "payload").exists())
        self.assertEqual((self.root / "payload.lock.json").read_bytes(), self.original_lock)
        self.assertTrue(source_integrity.check(self.root)[0]["passed"])
        sums = (self.root / "SHA256SUMS").read_text()
        self.assertIn("  payload/bin/runtime\n", sums)
        self.assertIn("  SOURCE_MANIFEST.json\n", sums)
        self.assertNotIn("  SHA256SUMS\n", sums)
        self.assertNotIn("offline/objects/", sums)

    def test_source_change_is_detected(self):
        source_integrity.refresh(self.root)
        (self.root / "README.md").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "SOURCE_MANIFEST.json is stale"):
            source_integrity.check(self.root)

    def test_new_maintained_file_is_detected(self):
        source_integrity.refresh(self.root)
        (self.root / "new-code.py").write_text("print('new')\n")
        with self.assertRaisesRegex(ValueError, "SOURCE_MANIFEST.json is stale"):
            source_integrity.check(self.root)

    def test_generated_logs_do_not_create_circular_checksum(self):
        source_integrity.refresh(self.root)
        (self.root / "reports").mkdir(); (self.root / "reports/ci.log").write_text("generated\n")
        self.assertTrue(source_integrity.check(self.root)[0]["passed"])

    def test_checksum_file_tampering_detected(self):
        source_integrity.refresh(self.root)
        (self.root / "SHA256SUMS").write_text("0" * 64 + "  README.md\n")
        with self.assertRaisesRegex(ValueError, "SHA256SUMS is stale"):
            source_integrity.check(self.root)

    def test_hydrated_payload_optional_and_real(self):
        source_integrity.refresh(self.root)
        with self.assertRaisesRegex(ValueError, "Missing regular file"):
            source_integrity.check(self.root, with_payload=True)
        self.hydrate()
        self.assertTrue(source_integrity.check(self.root, with_payload=True)[0]["payloadBytesChecked"])
        (self.root / "payload/bin/runtime").write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "Preserving differing"):
            source_integrity.check(self.root, with_payload=True)

    def test_executable_bit_is_part_of_source_contract(self):
        source_integrity.refresh(self.root)
        (self.root / "setup.sh").chmod(0o644)
        with self.assertRaisesRegex(ValueError, "SOURCE_MANIFEST.json is stale"):
            source_integrity.check(self.root)

    def test_source_symlink_rejected(self):
        outside = self.base / "outside"; outside.write_text("outside\n")
        (self.root / "unsafe.md").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            source_integrity.refresh(self.root)

    def test_export_contains_source_and_one_payload_copy(self):
        self.hydrate(); self.commit()
        output = self.base / "release.tar.gz"
        report = exporter.export(self.root, output, "v0.1.0")
        self.assertTrue(report["passed"])
        self.assertEqual(report["payloadFiles"], 1)
        extracted = self.base / "extracted"; extracted.mkdir()
        names = []
        with tarfile.open(output) as archive:
            for member in archive:
                names.append(member.name)
                relative = Path(*Path(member.name).parts[1:])
                target = extracted / relative; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read()); target.chmod(member.mode)
        self.assertFalse(any("/.git/" in name or "/offline/objects/" in name for name in names))
        self.assertEqual(sum(name.endswith("/payload/bin/runtime") for name in names), 1)
        self.assertEqual(stat.S_IMODE((extracted / "setup.sh").stat().st_mode), 0o755)
        self.assertTrue(source_integrity.check(extracted, with_payload=True)[0]["passed"])
        self.assertEqual(report["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertTrue(Path(str(output) + ".sha256").exists())
        self.assertTrue(Path(str(output) + ".validation.json").exists())

    def test_export_refuses_dirty_source(self):
        self.hydrate(); self.commit()
        (self.root / "README.md").write_text("dirty\n")
        with self.assertRaisesRegex(ValueError, "clean source"):
            exporter.export(self.root, self.base / "release.tar.gz", "v0.1.0")

    def test_export_refuses_mismatched_tag_head(self):
        self.hydrate(); self.commit()
        (self.root / "README.md").write_text("second\n")
        source_integrity.refresh(self.root)
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Second"], check=True)
        with self.assertRaisesRegex(ValueError, "HEAD differs"):
            exporter.export(self.root, self.base / "release.tar.gz", "v0.1.0")

    def test_export_refuses_missing_payload(self):
        self.commit()
        with self.assertRaisesRegex(ValueError, "Missing regular file"):
            exporter.export(self.root, self.base / "release.tar.gz", "v0.1.0")

    def test_export_preserves_existing_output(self):
        self.hydrate(); self.commit()
        output = self.base / "release.tar.gz"; output.write_bytes(b"previous export")
        with self.assertRaisesRegex(ValueError, "Preserving existing export"):
            exporter.export(self.root, output, "v0.1.0")
        self.assertEqual(output.read_bytes(), b"previous export")

    def test_exported_tree_cannot_regenerate_its_source_authority(self):
        source_integrity.refresh(self.root)
        shutil.rmtree(self.root / ".git")
        self.assertTrue(source_integrity.check(self.root)[0]["passed"])
        with self.assertRaisesRegex(ValueError, "Git checkout"):
            source_integrity.refresh(self.root)


if __name__ == "__main__":
    unittest.main()
