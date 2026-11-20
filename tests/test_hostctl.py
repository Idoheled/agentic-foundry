import argparse
import importlib.util
import io
import json
import os
import pathlib
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("hostctl", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "hostctl.py")
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)


class HostProvisionerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.prefix = self.root / "fake-host"
        self.prefix.mkdir()
        self.payload = self.root / "kit"
        self.payload.mkdir()
        self.internal = self.root / "internal"
        self.internal.mkdir()
        self.artifact = self.internal / "demo"
        self.artifact.write_text("#!/bin/sh\nprintf 'fixture 1.0\\n'\n")
        self.artifact.chmod(0o755)
        self.old = self.prefix / "wrong/place/demo"
        self.old.parent.mkdir(parents=True)
        self.old.write_text("#!/bin/sh\nprintf 'fixture 0.1\\n'\n")
        self.old.chmod(0o755)
        self.canonical = self.prefix / "usr/local/bin/demo"
        self.canonical.parent.mkdir(parents=True)
        self.canonical.symlink_to(self.old)
        self.catalog = {"schemaVersion": 1, "tools": {"demo": {
            "version": "1.0", "commands": {"demo": {"path": "bin/demo", "verifyArgs": ["--version"], "verifyPattern": "fixture 1.0"}},
            "artifact": {"path": "demo", "sha256": h.digest(self.artifact), "format": "file"}}}}
        self.plan = {"schemaVersion": 1, "privateRepositoriesChecked": ["Fixture approved internal source inspected"], "tools": {"demo": {
            "source": "internal", "path": str(self.artifact), "sha256": h.digest(self.artifact), "evidence": "Internal fixture has the required version and capabilities",
            "canonicalLinks": [{"path": "/usr/local/bin/demo", "command": "demo", "expected": h.snapshot(self.canonical), "replaceReason": "Inspected old command has the wrong version and location"}],
            "retire": [{"path": "/wrong/place/demo", "expected": h.snapshot(self.old), "unreferencedWithinInspectedScope": True,
                        "consumersChecked": ["Fixture command links and service configuration inspected; canonical link will be migrated"], "evidence": "Exact old unmanaged artifact can be quarantined after replacement verifies"}]}}}
        self.catalog_path = self.root / "catalog.json"
        self.plan_path = self.root / "plan.json"
        self.args = argparse.Namespace(catalog=str(self.catalog_path), plan=str(self.plan_path), payload_root=str(self.payload),
            state=str(self.prefix / "operator-state"), mode="system", prefix=str(self.prefix), package_owners=None,
            operator_uid=None, operator_gid=None, operator_home="/home/operator", receipt=None, output=None)
        self.write_inputs()
        self.host = h.Host(self.args)

    def write_inputs(self):
        self.catalog_path.write_text(json.dumps(self.catalog))
        self.plan_path.write_text(json.dumps(self.plan))

    def test_wrong_path_migration_verification_retirement_and_rollback(self):
        original = self.old.read_bytes()
        original_link = os.readlink(self.canonical)
        result = self.host.apply()
        self.assertTrue(result["passed"])
        self.assertTrue(self.host.verify()["passed"])
        self.assertEqual(self.canonical.resolve().name, "agentic-demo")
        receipt_path, receipt = self.host.receipt()
        installed = self.host.path(receipt["tools"]["demo"]["staged"]["installPath"])
        self.assertTrue(str(installed).startswith(str(self.prefix / "opt/agentic-stack/tools/demo")))
        self.assertEqual((installed / "bin/demo").read_bytes(), self.artifact.read_bytes())
        retired = self.host.retire()
        self.assertTrue(retired["passed"])
        self.assertFalse(self.old.exists())
        quarantine = self.host.path(retired["retired"][0]["quarantinePath"])
        self.assertEqual(quarantine.read_bytes(), original)
        self.assertTrue(self.host.verify()["passed"])
        self.assertTrue(self.host.retire()["passed"])
        self.assertTrue(self.host.rollback()["passed"])
        self.assertEqual(self.old.read_bytes(), original)
        self.assertEqual(os.readlink(self.canonical), original_link)
        self.assertFalse((self.canonical.parent / "agentic-demo").exists())
        self.assertTrue(installed.is_dir())
        self.assertEqual(h.read_json(receipt_path)["status"], "rolled_back")

    def test_existing_adequate_reuse_does_not_copy_and_cannot_retire_its_dependency(self):
        self.old.write_bytes(self.artifact.read_bytes())
        choice = self.plan["tools"]["demo"]
        choice.update(source="existing", path="/wrong/place/demo", sha256=h.digest(self.old), adequate=True)
        choice["retire"][0]["expected"] = h.snapshot(self.old)
        self.write_inputs()
        self.assertTrue(self.host.apply()["passed"])
        self.assertFalse((self.prefix / "opt/agentic-stack/tools").exists())
        retired = self.host.retire()
        self.assertFalse(retired["passed"])
        self.assertIn("still depends", retired["blockers"][0]["reason"])
        self.assertTrue(self.old.exists())

    def test_existing_file_can_be_normalized_and_retired_after_verification(self):
        self.old.write_bytes(self.artifact.read_bytes())
        choice = self.plan["tools"]["demo"]
        choice.update(source="existing", path="/wrong/place/demo", sha256=h.digest(self.old), normalizePath=True)
        choice["retire"][0]["expected"] = h.snapshot(self.old)
        self.write_inputs()
        self.assertTrue(self.host.apply()["passed"])
        self.assertTrue(self.host.retire()["passed"])
        self.assertFalse(self.old.exists())
        self.assertTrue(self.host.verify()["passed"])

    def test_missing_private_search_or_fallback_reason_rejects_before_mutation(self):
        self.plan["privateRepositoriesChecked"] = []
        self.write_inputs()
        with self.assertRaisesRegex(h.Blocked, "private repositories"):
            self.host.apply()
        self.plan["privateRepositoriesChecked"] = ["Internal repository inspected"]
        self.plan["tools"]["demo"]["source"] = "kit"
        self.write_inputs()
        with self.assertRaisesRegex(h.Blocked, "fallback requires"):
            self.host.apply()
        self.assertFalse((self.canonical.parent / "agentic-demo").exists())

    def test_changed_or_package_owned_canonical_command_is_preserved(self):
        self.canonical.unlink()
        self.canonical.write_text("preserve unrelated occupant")
        with self.assertRaisesRegex(h.Blocked, "inspection snapshot"):
            self.host.apply()
        self.assertEqual(self.canonical.read_text(), "preserve unrelated occupant")
        owners = self.root / "owners.json"
        owners.write_text(json.dumps({"/usr/local/bin/demo": "fixture-package: /usr/local/bin/demo"}))
        self.args.package_owners = str(owners)
        self.plan["tools"]["demo"]["canonicalLinks"][0]["expected"] = h.snapshot(self.canonical)
        self.write_inputs()
        with self.assertRaisesRegex(h.Blocked, "Package-owned"):
            self.host.apply()

    def test_whole_tree_relative_symlinks_and_dependency_layout_are_preserved(self):
        archive = self.internal / "tool.tar.gz"
        script = b'#!/bin/sh\ntest -f "$(dirname "$0")/../lib/dependency.txt" || exit 9\nprintf "fixture 1.0\\n"\n'
        with tarfile.open(archive, "w:gz") as bundle:
            for name, data, mode in [("tool/bin/demo", script, 0o755), ("tool/lib/dependency.txt", b"required library", 0o644)]:
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(data), mode
                bundle.addfile(member, io.BytesIO(data))
            member = tarfile.TarInfo("tool/bin/demo-alias")
            member.type, member.linkname = tarfile.SYMTYPE, "demo"
            bundle.addfile(member)
        tool = self.catalog["tools"]["demo"]
        tool["requiredPaths"] = ["lib/dependency.txt"]
        tool["commands"]["demo-alias"] = {"path": "bin/demo-alias", "verifyArgs": ["--version"]}
        choice = self.plan["tools"]["demo"]
        choice.update(path=str(archive), sha256=h.digest(archive), format="tar", stripComponents=1)
        self.write_inputs()
        self.assertTrue(self.host.apply()["passed"])
        _, receipt = self.host.receipt()
        installed = self.host.path(receipt["tools"]["demo"]["staged"]["installPath"])
        self.assertEqual((installed / "lib/dependency.txt").read_bytes(), b"required library")
        self.assertEqual(os.readlink(installed / "bin/demo-alias"), "demo")
        self.assertTrue(self.host.verify()["passed"])

    def test_archive_traversal_and_escaping_symlinks_are_rejected(self):
        for link in (False, True):
            with self.subTest(link=link):
                archive = self.internal / ("bad-link.tar" if link else "bad-path.tar")
                with tarfile.open(archive, "w") as bundle:
                    member = tarfile.TarInfo("link" if link else "../outside")
                    if link:
                        member.type, member.linkname = tarfile.SYMTYPE, "../../outside"
                        bundle.addfile(member)
                    else:
                        member.size = 3
                        bundle.addfile(member, io.BytesIO(b"bad"))
                with self.assertRaises(h.Blocked):
                    h.archive_tree(archive, self.root / ("unpacked-link" if link else "unpacked-path"), "tar")
                self.assertFalse((self.root / "outside").exists())

    def test_second_apply_and_rollback_restore_prior_managed_entry_points(self):
        first = self.host.apply()
        second = self.host.apply()
        self.assertTrue(second["passed"])
        self.assertTrue(self.host.rollback()["passed"])
        self.assertTrue((self.canonical.parent / "agentic-demo").exists())
        self.args.receipt = first["receipt"]
        self.assertTrue(self.host.verify()["passed"])
        self.assertTrue(self.host.rollback()["passed"])
        self.assertEqual(self.canonical.resolve(), self.old)

    def test_retirement_without_reference_evidence_leaves_explicit_blocker(self):
        self.plan["tools"]["demo"]["retire"][0]["consumersChecked"] = []
        self.write_inputs()
        self.host.apply()
        result = self.host.retire()
        self.assertFalse(result["passed"])
        self.assertIn("Consumer inspection", result["blockers"][0]["reason"])
        self.assertTrue(self.old.exists())

    def test_changed_promoted_command_blocks_rollback_without_overwriting_it(self):
        self.host.apply()
        launcher = self.canonical.parent / "agentic-demo"
        launcher.write_text("new independent work")
        with self.assertRaisesRegex(h.Blocked, "changed since installation"):
            self.host.rollback()
        self.assertEqual(launcher.read_text(), "new independent work")

    def test_unrelated_state_directory_is_preserved(self):
        self.host.state.mkdir()
        unrelated = self.host.state / "unrelated-work"
        unrelated.write_text("keep")
        with self.assertRaisesRegex(h.Blocked, "unrelated nonempty"):
            self.host.apply()
        self.assertEqual(unrelated.read_text(), "keep")
        self.assertFalse((self.canonical.parent / "agentic-demo").exists())

    def test_state_symlink_is_rejected_before_privilege_reexecution(self):
        target = self.root / "unrelated-state-target"
        target.mkdir()
        link = self.root / "state-link"
        link.symlink_to(target, target_is_directory=True)
        argv = ["apply", "--catalog", str(self.catalog_path), "--plan", str(self.plan_path),
                "--payload-root", str(self.payload), "--state", str(link)]
        with patch.object(h.os, "geteuid", return_value=1000), patch.object(h.subprocess, "run") as run:
            with self.assertRaisesRegex(h.Blocked, "State directory must not be a symlink"):
                h.main(argv)
            run.assert_not_called()
        self.assertFalse(any(target.iterdir()))

    def test_asset_tree_installs_and_verifies_without_command_shims(self):
        archive = self.internal / "profiles.tar.gz"
        contents = {"profiles/install.py": b"# actual installer is invoked separately with selected Python\n",
                    "profiles/skills/example/SKILL.md": b"# Example fixture skill\n"}
        with tarfile.open(archive, "w:gz") as bundle:
            for name, data in contents.items():
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(data), 0o644
                bundle.addfile(member, io.BytesIO(data))
        self.catalog["tools"] = {"native-profiles": {"kind": "asset-tree", "version": "1.0", "commands": {},
            "requiredPaths": ["install.py", "skills/example/SKILL.md"],
            "artifact": {"format": "tar", "path": "profiles.tar.gz", "sha256": h.digest(archive), "stripComponents": 1}}}
        self.plan["tools"] = {"native-profiles": {"source": "internal", "path": str(archive), "sha256": h.digest(archive),
            "evidence": "Complete synthetic internal profile asset tree inspected"}}
        self.write_inputs()
        first = self.host.apply()
        self.assertTrue(first["passed"])
        _, receipt = self.host.receipt()
        staged = receipt["tools"]["native-profiles"]["staged"]
        root = self.host.path(staged["installPath"])
        self.assertTrue(root.is_relative_to(self.prefix / "opt/agentic-stack/tools/native-profiles"))
        self.assertEqual((root / "install.py").read_bytes(), contents["profiles/install.py"])
        self.assertFalse(receipt["actions"])
        self.assertFalse(staged["checks"])
        self.assertTrue(self.host.verify()["passed"])
        self.assertTrue(self.host.apply()["passed"])
        _, second_receipt = self.host.receipt()
        self.assertEqual(second_receipt["tools"]["native-profiles"]["staged"]["installPath"], staged["installPath"])
        self.assertFalse(list(self.canonical.parent.glob("agentic-*")))
        (root / "install.py").write_text("changed after installation")
        self.assertFalse(self.host.verify()["passed"])

    def test_literal_catalog_environment_reaches_checks_and_launcher(self):
        literal = "offline; literal $NOT_EXPANDED"
        self.artifact.write_text("#!/bin/sh\ntest \"$HOSTCTL_FIXTURE_MODE\" = '" + literal + "' || exit 8\n"
                                 "test \"$HOSTCTL_EXISTING_ROUTE\" = 'preserved' || exit 9\nprintf 'fixture 1.0\\n'\n")
        self.catalog["tools"]["demo"]["environment"] = {"HOSTCTL_FIXTURE_MODE": literal, "PYTHONDONTWRITEBYTECODE": "1"}
        self.catalog["tools"]["demo"]["artifact"]["sha256"] = h.digest(self.artifact)
        self.plan["tools"]["demo"]["sha256"] = h.digest(self.artifact)
        self.write_inputs()
        with patch.dict(os.environ, {"HOSTCTL_EXISTING_ROUTE": "preserved"}):
            self.assertTrue(self.host.apply()["passed"])
            self.assertTrue(self.host.verify()["passed"])
        launcher = (self.canonical.parent / "agentic-demo").read_text()
        self.assertIn("export HOSTCTL_FIXTURE_MODE='" + literal + "'", launcher)
        self.catalog["tools"]["demo"]["environment"] = {"INVALID-KEY": "value"}
        self.write_inputs()
        with self.assertRaisesRegex(h.Blocked, "Catalog environment"):
            self.host.validate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
