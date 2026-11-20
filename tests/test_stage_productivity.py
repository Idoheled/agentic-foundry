#!/usr/bin/env python3
"""Real isolated filesystem staging with mocked container probes; no Docker or model use."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get("AGENTIC_TEST_BASE_KIT", str(HERE)))


def load(name):
    spec = importlib.util.spec_from_file_location("stage_fixture_" + name.replace("-", "_"), BASE / "scripts" / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", [str(BASE / "scripts"), *sys.path]):
        spec.loader.exec_module(value)
    return value


@unittest.skipUnless((BASE / "scripts/stage-productivity.py").exists(), "Requires the assembled r5 staging script")
class StageProductivityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="stage-productivity-tests-", dir=os.environ.get("AGENTIC_TEST_TMPDIR"))
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.delivery = load("stage-productivity")
        self.stage = load("stage-clients")
        self.core = self.root / "core"
        self.core.mkdir(mode=0o700)
        self.json(self.core / "agentic-install.json", {"uid": os.getuid(), "gid": os.getgid(), "kitVersion": "test"})
        self.source = self.root / "source-runtime"
        (self.source / "bin").mkdir(parents=True)
        command = self.source / "bin/wt"
        command.write_text("#!/bin/sh\nprintf 'fixture-worktrunk 1.0\\n'\n")
        command.chmod(0o755)
        self.receipt = self.root / "host-receipt.json"
        self.json(self.receipt, {"schemaVersion": 1, "operatorUid": os.getuid(), "status": "installed_and_verified",
            "verification": {"passed": True}, "tools": {"worktrunk": {
                "selection": {"version": "1.0", "source": "kit",
                    "commands": {"wt": {"path": "bin/wt", "verifyArgs": ["--version"], "verifyPattern": r"fixture-worktrunk 1\.0", "verifyTimeoutSeconds": 1}},
                    "catalog": {"environment": {"FIXTURE_LITERAL": "fixture value with spaces"}, "requiredPaths": ["bin/wt"]}},
                "staged": {"reuse": False, "installPath": str(self.source), "treeSha256": self.stage.hostctl.tree_identity(self.source)}}}})

    def tearDown(self):
        self.temporary.cleanup()

    def json(self, path, value):
        path.write_text(json.dumps(value, indent=2) + "\n")
        path.chmod(0o600)

    def read(self, path):
        return json.loads(path.read_text())

    @property
    def record(self):
        return self.core / "reports/productivity-commands.json"

    def invoke(self, command="apply", result=None, error=None):
        result = result or types.SimpleNamespace(returncode=0, stdout="fixture-worktrunk 1.0\n", stderr="")
        argv = ["stage-productivity.py", command, "--host-receipt", str(self.receipt), "--core-state", str(self.core), "--names", "worktrunk"]
        output = io.StringIO()
        with patch.object(self.delivery, "module", return_value=self.stage), patch.object(self.stage.core, "exec_worker", return_value=result, side_effect=error) as probe, patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            code = self.delivery.main()
        return code, json.loads(output.getvalue()), probe

    def rejected_without_probe(self, command="verify"):
        argv = ["stage-productivity.py", command, "--host-receipt", str(self.receipt), "--core-state", str(self.core), "--names", "worktrunk"]
        success = types.SimpleNamespace(returncode=0, stdout="fixture-worktrunk 1.0\n", stderr="")
        with patch.object(self.delivery, "module", return_value=self.stage), patch.object(self.stage.core, "exec_worker", return_value=success) as probe, patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises((ValueError, RuntimeError, OSError)):
                self.delivery.main()
        probe.assert_not_called()

    def test_complete_tree_and_wrappers_are_staged_and_probe_result_is_scoped(self):
        code, record, probe = self.invoke()
        self.assertEqual(code, 0)
        self.assertTrue(record["containerExecutionQualified"])
        self.assertIn("real model", record["scope"])
        staged = self.read(self.core / "reports/productivity-runtime.json")["clients"]["worktrunk"]
        self.assertEqual(self.stage.hostctl.tree_identity(staged["destination"]), self.stage.hostctl.tree_identity(self.source))
        wrapper = (self.core / "runtime/bin/agentic-wt").read_text()
        self.assertIn("export FIXTURE_LITERAL='fixture value with spaces'", wrapper)
        self.assertIn('/opt/agentic/clients/worktrunk/', wrapper)
        self.assertEqual(probe.call_count, 1)
        self.assertEqual(probe.call_args.args[1], ["/opt/agentic/bin/agentic-wt", "--version"])
        second, _, verify_probe = self.invoke("verify")
        self.assertEqual(second, 0)
        self.assertEqual(verify_probe.call_count, 1)

    def test_existing_untracked_wrapper_is_preserved_before_any_command_write(self):
        directory = self.core / "runtime/bin"
        directory.mkdir(parents=True)
        occupied = directory / "wt"
        occupied.write_text("keep existing local tool\n")
        self.rejected_without_probe("apply")
        self.assertEqual(occupied.read_text(), "keep existing local tool\n")
        self.assertFalse((directory / "agentic-wt").exists())
        self.assertFalse(self.record.exists())

    def test_changed_wrapper_blocks_verify(self):
        self.invoke()
        entry = self.core / "runtime/bin/agentic-wt"
        entry.write_text("changed after installation\n")
        self.rejected_without_probe()
        self.assertEqual(entry.read_text(), "changed after installation\n")

    def test_changed_staged_tree_blocks_verify(self):
        self.invoke()
        staged = self.read(self.core / "reports/productivity-runtime.json")["clients"]["worktrunk"]
        (Path(staged["destination"]) / "bin/wt").write_text("changed runtime\n")
        self.rejected_without_probe()

    def test_same_path_receipt_tampering_cannot_change_probe_policy(self):
        self.invoke()
        receipt = self.read(self.receipt)
        receipt["tools"]["worktrunk"]["selection"]["commands"]["wt"]["verifyPattern"] = ".*"
        self.json(self.receipt, receipt)
        self.rejected_without_probe()

    def test_failed_container_probe_is_not_reported_as_qualified(self):
        code, record, _ = self.invoke(result=types.SimpleNamespace(returncode=17, stdout="fixture-worktrunk 1.0\n", stderr="fixture runtime failure"))
        self.assertEqual(code, 2)
        self.assertFalse(record["containerExecutionQualified"])
        self.assertFalse(self.read(self.record)["containerExecutionQualified"])

    def test_wrong_version_output_is_not_reported_as_qualified(self):
        code, record, _ = self.invoke(result=types.SimpleNamespace(returncode=0, stdout="wrong-tool 8.0\n", stderr=""))
        self.assertEqual(code, 2)
        self.assertFalse(record["containerExecutionQualified"])

    def test_timed_out_reverify_clears_prior_qualification(self):
        self.invoke()
        try:
            code, _, _ = self.invoke("verify", error=subprocess.TimeoutExpired(["fixture-container-probe"], 1))
        except (ValueError, RuntimeError, subprocess.TimeoutExpired):
            pass
        else:
            self.assertNotEqual(code, 0)
        self.assertFalse(self.read(self.record)["containerExecutionQualified"])

    def test_changed_core_operator_marker_blocks_verify(self):
        self.invoke()
        self.json(self.core / "agentic-install.json", {"uid": os.getuid() + 1, "gid": os.getgid(), "kitVersion": "test"})
        self.rejected_without_probe()

    def test_symlinked_report_parent_blocks_verify(self):
        self.invoke()
        original = self.root / "original-reports"
        (self.core / "reports").rename(original)
        (self.core / "reports").symlink_to(original, target_is_directory=True)
        self.rejected_without_probe()


if __name__ == "__main__":
    unittest.main()
