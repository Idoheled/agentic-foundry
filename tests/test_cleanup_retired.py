import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "scripts/hostctl.py"
if not HOST.is_file():
    HOST = ROOT.parents[1] / "kit-r3/scripts/hostctl.py"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


CLEAN = module("cleanup_retired", ROOT / "scripts/cleanup-retired.py")
HOSTCTL = module("fixture_hostctl", HOST)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prefix = self.root / "filesystem"
        self.prefix.mkdir()
        self.host_state = self.root / "host-state"
        self.host_state.mkdir()
        (self.host_state / "hostctl-state.json").write_text(json.dumps({"schemaVersion": 1, "operatorUid": os.getuid(), "mode": "system"}))
        (self.host_state / "receipts").mkdir()
        self.host_receipt = self.host_state / "receipts/test-receipt.json"
        self.completion = self.root / "completion.json"
        self.old = Path("/legacy/bin/omp")
        self.quarantine = Path("/opt/agentic-stack/quarantine/test-receipt/0-omp")
        self.runtime = Path("/opt/agentic-stack/tools/omp/new-0123456789ab")
        runtime = self.physical(self.runtime)
        (runtime / "bin").mkdir(parents=True)
        executable = runtime / "bin/omp"
        executable.write_text("#!/bin/sh\necho new-omp-version\n")
        executable.chmod(0o755)
        launcher = self.physical("/usr/local/bin/agentic-omp")
        launcher.parent.mkdir(parents=True)
        launcher.write_text("#!/bin/sh\nexec " + str(executable) + ' "$@"\n')
        launcher.chmod(0o755)
        self.qfile = self.physical(self.quarantine)
        self.qfile.parent.mkdir(parents=True)
        self.qfile.write_text("old executable bytes\n")
        self.qfile.chmod(0o755)
        before = HOSTCTL.snapshot(self.qfile)
        request = {"path": str(self.old), "expected": before, "unreferencedWithinInspectedScope": True,
                   "consumersChecked": ["Fixture consumer search found no dependencies"], "evidence": "Fixture upgrade verified"}
        self.data = {
            "schemaVersion": 1, "id": "test-receipt", "operatorUid": os.getuid(), "operatorGid": os.getgid(),
            "mode": "system", "status": "installed_and_verified", "verification": {"passed": True}, "blockers": [],
            "actions": [], "retirementResult": {"passed": True},
            "tools": {"omp": {"selection": {"catalog": {}, "choice": {"retire": [request]},
                     "commands": {"omp": {"path": "bin/omp", "verifyArgs": ["--version"], "verifyPattern": "new-omp-version"}}},
                     "staged": {"reuse": False, "installPath": str(self.runtime), "treeSha256": HOSTCTL.tree_identity(runtime)}}},
            "retirements": [{"tool": "omp", "path": str(self.old), "quarantinePath": str(self.quarantine), "before": before,
                             "consumersChecked": request["consumersChecked"], "evidence": request["evidence"]}]
        }
        self.preservation = self.root / "preservation.json"
        self.acceptance = self.root / "acceptance.json"
        for file in (self.preservation, self.acceptance):
            file.write_text('{"passed":true}\n')
        self.completion_data = {"schemaVersion": 1, "status": "completed", "passed": True,
            "protectedRoots": ["/home/operator/private-profile"],
            "preservationReport": {"path": str(self.preservation), "sha256": CLEAN.sha(self.preservation)},
            "acceptanceEvidence": {"path": str(self.acceptance), "sha256": CLEAN.sha(self.acceptance)}}
        self.write_inputs()

    def physical(self, logical):
        return self.prefix / str(logical).lstrip("/")

    def write_inputs(self):
        self.host_receipt.write_text(json.dumps(self.data, indent=2))
        self.completion_data["hostReceipts"] = [{"path": str(self.host_receipt), "sha256": CLEAN.sha(self.host_receipt)}]
        self.completion.write_text(json.dumps(self.completion_data, indent=2))
        self.args = argparse.Namespace(command="apply", host_receipt=str(self.host_receipt), host_receipt_sha256=CLEAN.sha(self.host_receipt),
            completion=str(self.completion), completion_sha256=CLEAN.sha(self.completion), host_state=str(self.host_state),
            state=str(self.root / "cleanup-state"), mode="system", prefix=str(self.prefix), package_owners=None,
            operator_uid=os.getuid(), operator_gid=os.getgid(), operator_home="/home/operator")

    def cleanup(self):
        return CLEAN.Cleanup(self.args, HOSTCTL)

    def test_actual_delete_verified_backup_and_idempotence(self):
        cleanup = self.cleanup()
        self.assertTrue(cleanup.plan()["passed"])
        result = cleanup.apply()
        self.assertTrue(result["passed"])
        self.assertFalse(self.qfile.exists())
        self.assertTrue(cleanup.archive.is_file())
        self.assertEqual(cleanup.archive.stat().st_mode & 0o777, 0o600)
        self.assertEqual(cleanup.state.stat().st_mode & 0o777, 0o700)
        self.assertTrue(self.physical(self.runtime / "bin/omp").exists())
        self.assertTrue(cleanup.apply()["alreadyCompleted"])

    def test_symlink_is_archived_as_link_without_reading_target(self):
        target = self.root / "must-stay-secret"
        target.write_text("PRIVATE_PAYLOAD_NEVER_ARCHIVED")
        self.qfile.unlink()
        self.qfile.symlink_to(target)
        before = HOSTCTL.snapshot(self.qfile)
        self.data["retirements"][0]["before"] = before
        self.data["tools"]["omp"]["selection"]["choice"]["retire"][0]["expected"] = before
        self.write_inputs()
        cleanup = self.cleanup()
        cleanup.apply()
        self.assertFalse(self.qfile.is_symlink())
        self.assertEqual(target.read_text(), "PRIVATE_PAYLOAD_NEVER_ARCHIVED")
        cleanup.restore()
        self.assertTrue(self.qfile.is_symlink())
        self.assertEqual(os.readlink(self.qfile), str(target))

    def test_changed_receipt_hash_blocks(self):
        self.host_receipt.write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "hash changed"):
            self.cleanup()
        self.assertTrue(self.qfile.exists())

    def test_incomplete_final_acceptance_blocks(self):
        self.completion_data["status"] = "blocked"
        self.write_inputs()
        with self.assertRaisesRegex(RuntimeError, "acceptance has not completed"):
            self.cleanup()

    def test_quarantine_escape_blocks(self):
        self.data["retirements"][0]["quarantinePath"] = "/somewhere/omp"
        self.write_inputs()
        with self.assertRaisesRegex(RuntimeError, "outside its exact receipt"):
            self.cleanup().apply()
        self.assertTrue(self.qfile.exists())

    def test_profile_file_never_deleted(self):
        old = "/home/operator/private-profile/hooks/run"
        self.data["retirements"][0]["path"] = old
        self.data["tools"]["omp"]["selection"]["choice"]["retire"][0]["path"] = old
        self.write_inputs()
        with self.assertRaisesRegex(RuntimeError, "Protected profile"):
            self.cleanup().apply()
        self.assertTrue(self.qfile.exists())

    def test_changed_runtime_blocks_cleanup(self):
        self.physical(self.runtime / "bin/omp").write_text("#!/bin/sh\nexit 1\n")
        with self.assertRaisesRegex(RuntimeError, "Fresh replacement host verification failed"):
            self.cleanup().apply()
        self.assertTrue(self.qfile.exists())

    def test_changed_quarantine_blocks_cleanup(self):
        self.qfile.write_text("later user edits")
        with self.assertRaisesRegex(RuntimeError, "Quarantined file changed"):
            self.cleanup().apply()
        self.assertEqual(self.qfile.read_text(), "later user edits")

    def test_package_owned_original_blocks_cleanup(self):
        owners = self.root / "owners.json"
        owners.write_text(json.dumps({str(self.old): "distribution-package"}))
        self.args.package_owners = str(owners)
        with self.assertRaisesRegex(RuntimeError, "Package-owned paths"):
            self.cleanup().apply()
        self.assertTrue(self.qfile.exists())

    def test_running_retired_binary_blocks_cleanup(self):
        shutil.copy2("/bin/sleep", self.qfile)
        before = HOSTCTL.snapshot(self.qfile)
        self.data["retirements"][0]["before"] = before
        self.data["tools"]["omp"]["selection"]["choice"]["retire"][0]["expected"] = before
        self.write_inputs()
        process = subprocess.Popen([str(self.qfile), "30"])
        try:
            with self.assertRaisesRegex(RuntimeError, "running process"):
                self.cleanup().apply()
            self.assertTrue(self.qfile.exists())
        finally:
            process.terminate()
            process.wait(timeout=10)

    def test_interruption_after_unlink_recovers_from_archive(self):
        cleanup = self.cleanup()
        real_unlink = os.unlink
        def interrupted(path, *args, **kwargs):
            result = real_unlink(path, *args, **kwargs)
            if str(path) == self.qfile.name and kwargs.get("dir_fd") is not None:
                raise RuntimeError("simulated process interruption after unlink")
            return result
        with mock.patch.object(CLEAN.os, "unlink", side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError, "simulated process interruption"):
                cleanup.apply()
        self.assertFalse(self.qfile.exists())
        self.assertTrue(cleanup.apply()["passed"])
        cleanup.restore()
        self.assertEqual(HOSTCTL.snapshot(self.qfile), self.data["retirements"][0]["before"])

    def test_restore_preserves_new_quarantine_occupant(self):
        cleanup = self.cleanup()
        cleanup.apply()
        self.qfile.write_text("new unrelated content")
        with self.assertRaisesRegex(RuntimeError, "Quarantined file changed"):
            cleanup.restore()
        self.assertEqual(self.qfile.read_text(), "new unrelated content")

    def test_tampered_archive_blocks_restore(self):
        cleanup = self.cleanup()
        cleanup.apply()
        cleanup.archive.write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "Rollback archive changed"):
            cleanup.restore()
        self.assertFalse(self.qfile.exists())

    def test_reused_original_active_path_blocks_cleanup(self):
        old = self.physical(self.old)
        old.parent.mkdir(parents=True)
        old.write_text("new occupant")
        with self.assertRaisesRegex(RuntimeError, "Old active path has been reused"):
            self.cleanup().apply()
        self.assertEqual(old.read_text(), "new occupant")


if __name__ == "__main__":
    unittest.main()
