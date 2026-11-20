import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "offline_payload.py"
SPEC = importlib.util.spec_from_file_location("foundry_offline_payload", MODULE)
offline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(offline)


class OfflinePayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="foundry-payload-test-")
        self.base = Path(self.temp.name)
        self.source = self.base / "release"; self.root = self.base / "repo"
        self.source.mkdir(); self.root.mkdir()
        self.data = {"payload/bin/tool": (b"#!/bin/sh\necho hello\n", 0o755),
                     "payload/archive.bin": (b"abcdefghi123456789abcdefgh", 0o644),
                     "payload/duplicate.bin": (b"abcdefghi123456789abcdefgh", 0o644),
                     "payload/empty": (b"", 0o644)}
        files = {}
        for name, (content, mode) in self.data.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content); path.chmod(mode)
            files[name] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content), "mode": mode}
        lock = json.dumps({"schemaVersion": 1, "release": "fixture-r5", "files": files}, indent=2) + "\n"
        (self.source / "payload.lock.json").write_text(lock); (self.root / "payload.lock.json").write_text(lock)

    def tearDown(self):
        self.temp.cleanup()

    def pack(self, **kwargs):
        offline.pack(self.root, self.source, reflink="never", **kwargs)
        return offline.load(self.root)

    def save_manifest(self, manifest):
        (self.root / "offline" / "manifest.json").write_text(json.dumps(manifest))

    def test_roundtrip_split_duplicate_and_empty(self):
        manifest = self.pack(chunk_bytes=8)
        self.assertEqual(manifest["files"]["payload/archive.bin"]["chunks"], manifest["files"]["payload/duplicate.bin"]["chunks"])
        self.assertEqual(manifest["files"]["payload/empty"]["chunks"], [])
        self.assertTrue(offline.verify(self.root, manifest)["passed"])
        self.assertFalse((self.root / "payload").exists())
        self.assertEqual(offline.hydrate(self.root, manifest)["hydrated"], 4)
        for name, (data, mode) in self.data.items():
            self.assertEqual((self.root / name).read_bytes(), data)
            self.assertEqual(stat.S_IMODE((self.root / name).stat().st_mode), mode)
        again = offline.hydrate(self.root, manifest)
        self.assertEqual(again["hydrated"], 0); self.assertEqual(again["reused"], 4)

    def test_source_only_validation_does_not_need_blobs(self):
        manifest = self.pack()
        for path in (self.root / "offline" / "objects" / "sha256").iterdir():
            path.unlink()
        self.assertEqual(len(offline.load(self.root)["files"]), 4)
        with self.assertRaisesRegex(ValueError, "Missing regular file"):
            offline.verify(self.root, manifest)

    def test_hardlinks_preserve_source_mode(self):
        manifest = self.pack(link_source=True)
        source = self.source / "payload/bin/tool"
        obj = offline.object_path(self.root, manifest["files"]["payload/bin/tool"]["chunks"][0])
        self.assertEqual(source.stat().st_ino, obj.stat().st_ino)
        self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o755)
        result = offline.hydrate(self.root, manifest, link_objects=True)
        self.assertEqual(result["linked"], 3)
        self.assertEqual(source.stat().st_ino, (self.root / "payload/bin/tool").stat().st_ino)

    def test_hydration_does_not_chmod_object_with_different_mode(self):
        manifest = self.pack()
        obj = offline.object_path(self.root, manifest["files"]["payload/bin/tool"]["chunks"][0])
        self.assertEqual(stat.S_IMODE(obj.stat().st_mode), 0o644)
        offline.hydrate(self.root, manifest, link_objects=True)
        self.assertEqual(stat.S_IMODE(obj.stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE((self.root / "payload/bin/tool").stat().st_mode), 0o755)
        self.assertNotEqual(obj.stat().st_ino, (self.root / "payload/bin/tool").stat().st_ino)

    def test_existing_content_conflict_preserved_before_writes(self):
        manifest = self.pack()
        target = self.root / "payload/duplicate.bin"
        target.parent.mkdir(); target.write_bytes(b"private existing")
        with self.assertRaisesRegex(ValueError, "Preserving differing"):
            offline.hydrate(self.root, manifest)
        self.assertEqual(target.read_bytes(), b"private existing")
        self.assertFalse((self.root / "payload/bin/tool").exists())

    def test_existing_mode_conflict_preserved(self):
        manifest = self.pack()
        target = self.root / "payload/archive.bin"
        target.parent.mkdir(); target.write_bytes(self.data["payload/archive.bin"][0]); target.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "mode"):
            offline.hydrate(self.root, manifest)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_partial_chunk_rejected_without_final_file(self):
        manifest = self.pack()
        oid = manifest["files"]["payload/archive.bin"]["chunks"][0]
        offline.object_path(self.root, oid).write_bytes(b"partial")
        with self.assertRaisesRegex(ValueError, "wrong object size"):
            offline.hydrate(self.root, manifest)
        self.assertFalse((self.root / "payload/archive.bin").exists())
        self.assertEqual(list((self.root / "payload").glob(".foundry-payload-*")), [])

    def test_same_size_tamper_rejected(self):
        manifest = self.pack()
        oid = manifest["files"]["payload/archive.bin"]["chunks"][0]
        path = offline.object_path(self.root, oid); path.write_bytes(b"X" * path.stat().st_size)
        with self.assertRaisesRegex(ValueError, "checksum differs"):
            offline.verify(self.root, manifest)

    def test_lfs_pointer_is_not_payload(self):
        manifest = self.pack()
        oid = next(iter(manifest["objects"]))
        offline.object_path(self.root, oid).write_text("version https://git-lfs.github.com/spec/v1\noid sha256:" + oid + "\nsize 100\n")
        with self.assertRaisesRegex(ValueError, "LFS bytes"):
            offline.verify(self.root, manifest)

    def test_symlink_object_rejected(self):
        manifest = self.pack()
        oid = next(iter(manifest["objects"]))
        obj = offline.object_path(self.root, oid); other = self.base / "outside"
        obj.rename(other); obj.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "symlink"):
            offline.verify(self.root, manifest)

    def test_symlink_destination_ancestor_rejected(self):
        manifest = self.pack()
        external = self.base / "external"; external.mkdir()
        (self.root / "payload").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            offline.hydrate(self.root, manifest)
        self.assertEqual(list(external.iterdir()), [])

    def test_traversal_rejected(self):
        manifest = self.pack()
        manifest["files"]["payload/../escape"] = manifest["files"].pop("payload/empty")
        manifest["supplementalFiles"] = ["payload/../escape"]
        self.save_manifest(manifest)
        with self.assertRaises(ValueError):
            offline.load(self.root)
        for name in ("payload/../x", "/payload/x", "payload//x", "payload/./x", "payload\\x", "payload/x\x00y"):
            with self.assertRaises(ValueError):
                offline.safe_name(name)

    def test_duplicate_json_object_id_rejected(self):
        self.pack()
        path = self.root / "offline" / "manifest.json"
        path.write_text('{"schemaVersion":1,"objects":{"' + 'a'*64 + '":{"bytes":1},"' + 'a'*64 + '":{"bytes":2}}}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            offline.load(self.root)

    def test_malformed_hash_reference_rejected(self):
        manifest = self.pack()
        manifest["files"]["payload/archive.bin"]["chunks"] = ["../../evil"]
        self.save_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "chunk reference"):
            offline.load(self.root)

    def test_lock_binding_rejected(self):
        self.pack()
        path = self.root / "payload.lock.json"; path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "does not match"):
            offline.load(self.root)

    def test_metadata_cannot_change_locked_file(self):
        manifest = self.pack()
        manifest["files"]["payload/archive.bin"]["sha256"] = "a" * 64
        self.save_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "changes locked"):
            offline.load(self.root)

    def test_reordered_chunks_fail_full_file_hash(self):
        manifest = self.pack(chunk_bytes=8)
        manifest["files"]["payload/archive.bin"]["chunks"].reverse()
        self.save_manifest(manifest)
        loaded = offline.load(self.root)
        with self.assertRaisesRegex(ValueError, "Reconstructed"):
            offline.verify(self.root, loaded)

    def test_unreferenced_object_rejected(self):
        manifest = self.pack()
        manifest["objects"]["a"*64] = {"bytes": 1}
        self.save_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "unreferenced"):
            offline.load(self.root)

    def test_boolean_size_rejected(self):
        manifest = self.pack()
        manifest["files"]["payload/empty"]["bytes"] = False
        self.save_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "size/mode"):
            offline.load(self.root)

    def test_source_tampering_prevents_manifest(self):
        (self.source / "payload/archive.bin").write_bytes(b"bad")
        with self.assertRaisesRegex(ValueError, "Source differs"):
            self.pack()
        self.assertFalse((self.root / "offline" / "manifest.json").exists())

    def test_supplemental_source_is_included(self):
        extra = self.source / "payload/sources/integration.bundle"
        extra.parent.mkdir(); extra.write_bytes(b"source history")
        manifest = self.pack()
        self.assertEqual(manifest["supplementalFiles"], ["payload/sources/integration.bundle"])
        offline.hydrate(self.root, manifest)
        self.assertEqual((self.root / "payload/sources/integration.bundle").read_bytes(), b"source history")

    def test_pack_is_idempotent_and_preserves_conflicting_manifest(self):
        self.pack()
        self.pack()
        target = self.root / "offline" / "manifest.json"; target.write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "Preserving differing offline manifest"):
            self.pack()
        self.assertEqual(target.read_text(), "{}\n")

    def test_reflink_auto_falls_back_to_copy(self):
        with mock.patch.object(offline, "clone_range", side_effect=OSError("unsupported")):
            result = offline.pack(self.root, self.source, chunk_bytes=8, reflink="auto")
        self.assertGreater(result["storageMethods"]["copy"], 0)

    def test_forced_reflink_failure_is_explicit(self):
        with mock.patch.object(offline, "clone_range", side_effect=OSError("unsupported")):
            with self.assertRaisesRegex(ValueError, "cannot reflink"):
                offline.pack(self.root, self.source, chunk_bytes=8, reflink="always")

    def test_manifest_only_matches_full_pack_without_objects(self):
        result = offline.pack(self.root, self.source, chunk_bytes=8, manifest_only=True)
        self.assertTrue(result["manifestOnly"])
        self.assertFalse(result["objectBytesWritten"])
        self.assertFalse((self.root / "offline" / "objects").exists())
        before = (self.root / "offline" / "manifest.json").read_bytes()
        self.pack(chunk_bytes=8)
        self.assertEqual((self.root / "offline" / "manifest.json").read_bytes(), before)
        self.assertTrue(offline.verify(self.root, offline.load(self.root))["passed"])

    def test_manifest_only_rejects_source_changes(self):
        with mock.patch.object(offline, "inventory_chunks", return_value=([("a"*64, 24)], "b"*64)):
            with self.assertRaisesRegex(ValueError, "Source changed"):
                offline.pack(self.root, self.source, chunk_bytes=8, manifest_only=True)
        self.assertFalse((self.root / "offline" / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
