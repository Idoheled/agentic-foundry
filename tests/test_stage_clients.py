"""Tiny complete-tree staging fixtures; no Docker, model calls or host-global writes."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/stage-clients.py"
spec = importlib.util.spec_from_file_location("stage_clients", SCRIPT)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class ClientStagingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "core-state"
        self.state.mkdir()
        (self.state / "agentic-install.json").write_text(json.dumps({"uid": os.getuid(), "gid": os.getgid(), "kitVersion": "fixture"}))
        self.source = self.root / "qualified-tree"
        (self.source / "bin").mkdir(parents=True)
        (self.source / "lib").mkdir()
        (self.source / "bin/sample").write_text("#!/bin/sh\necho fixture\n")
        (self.source / "bin/sample").chmod(0o755)
        (self.source / "bin/alias").symlink_to("sample")
        (self.source / "lib/dependency").write_text("full closure fixture")
        self.receipt_path = self.root / "host-receipt.json"
        self.receipt = {"schemaVersion": 1, "operatorUid": os.getuid(), "status": "installed_and_verified", "verification": {"passed": True},
            "tools": {"sample": {"selection": {"source": "internal", "version": "1.0", "commands": {"sample": {"path": "bin/sample"}},
                "catalog": {"requiredPaths": ["lib/dependency"]}},
                "staged": {"reuse": False, "installPath": str(self.source), "treeSha256": s.hostctl.tree_identity(self.source)}}}}
        self.save()

    def save(self):
        self.receipt_path.write_text(json.dumps(self.receipt))

    def test_complete_tree_preserved_container_paths_reported_and_idempotent(self):
        report = s.stage(self.receipt_path, self.state, ["sample"])
        client = report["clients"]["sample"]
        destination = Path(client["destination"])
        self.assertEqual((destination / "lib/dependency").read_text(), "full closure fixture")
        self.assertEqual(os.readlink(destination / "bin/alias"), "sample")
        self.assertTrue(client["containerCommands"]["sample"].startswith("/opt/agentic/clients/sample/1.0-"))
        self.assertFalse(client["containerExecutionQualified"])
        self.assertTrue(s.stage(self.receipt_path, self.state, ["sample"])["passed"])
        self.assertEqual(s.hostctl.tree_identity(destination), self.receipt["tools"]["sample"]["staged"]["treeSha256"])
        self.assertEqual((self.state / "reports/client-runtime.json").stat().st_mode & 0o777, 0o600)

    def test_changed_source_missing_client_and_bare_reuse_are_blockers(self):
        with self.assertRaisesRegex(RuntimeError, "missing from"):
            s.stage(self.receipt_path, self.state, ["absent"])
        self.receipt["tools"]["sample"]["staged"]["reuse"] = True
        self.save()
        with self.assertRaisesRegex(RuntimeError, "bare executable"):
            s.stage(self.receipt_path, self.state, ["sample"])
        self.receipt["tools"]["sample"]["staged"]["reuse"] = False
        self.save()
        (self.source / "lib/dependency").write_text("changed")
        with self.assertRaisesRegex(RuntimeError, "host tree changed"):
            s.stage(self.receipt_path, self.state, ["sample"])
        self.assertFalse((self.state / "reports/client-runtime.json").exists())

    def test_foreign_destination_and_escaping_source_link_are_preserved(self):
        report = s.stage(self.receipt_path, self.state, ["sample"])
        destination = Path(report["clients"]["sample"]["destination"])
        (destination / "lib/dependency").write_text("independent change")
        with self.assertRaisesRegex(RuntimeError, "foreign or changed"):
            s.stage(self.receipt_path, self.state, ["sample"])
        self.assertEqual((destination / "lib/dependency").read_text(), "independent change")
        (self.source / "escape").symlink_to("../../outside")
        self.receipt["tools"]["sample"]["staged"]["treeSha256"] = s.hostctl.tree_identity(self.source)
        self.save()
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            s.stage(self.receipt_path, self.state, ["sample"])

    def test_core_marker_owner_and_qualified_receipt_are_required(self):
        marker = self.state / "agentic-install.json"
        marker.write_text(json.dumps({"uid": os.getuid() + 1}))
        with self.assertRaisesRegex(RuntimeError, "different operator"):
            s.stage(self.receipt_path, self.state, ["sample"])
        marker.write_text(json.dumps({"uid": os.getuid()}))
        self.receipt["verification"]["passed"] = False
        self.save()
        with self.assertRaisesRegex(RuntimeError, "not passed"):
            s.stage(self.receipt_path, self.state, ["sample"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
