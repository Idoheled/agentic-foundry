"""Coordinator ordering/identity contracts; child installers are mocked except wrapper plan output."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

KIT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installation_coordinator", KIT / "scripts/install-stack.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
hspec = importlib.util.spec_from_file_location("coordinator_test_hostctl", KIT / "scripts/hostctl.py")
h = importlib.util.module_from_spec(hspec)
hspec.loader.exec_module(h)


class InstallationCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.kit = self.root / "kit"
        (self.kit / "scripts").mkdir(parents=True)
        shutil.copy2(KIT / "scripts/hostctl.py", self.kit / "scripts/hostctl.py")
        self.catalog = self.root / "catalog.json"
        self.catalog.write_text("{}")
        self.host_plan = self.root / "host.json"
        self.native_plan = self.root / "native.json"
        self.artifact_plan = self.root / "artifacts.json"
        for path in (self.host_plan, self.native_plan, self.artifact_plan):
            path.write_text(json.dumps({"privateRepositoriesChecked": ["Synthetic repository inspection fixture"]}))
        self.core_config = self.root / "core.json"
        self.core_config.write_text(json.dumps({"artifactPlan": str(self.artifact_plan)}))
        self.host_state = self.root / "host-state"
        (self.host_state / "receipts").mkdir(parents=True)
        self.assets = self.root / "permanent/native-profiles/1.0"
        self.assets.mkdir(parents=True)
        (self.assets / "install_profiles.py").write_text("# synthetic installer; never executed in this test\n")
        self.python_root = self.root / "permanent/python/1.0"
        (self.python_root / "bin").mkdir(parents=True)
        self.python = self.python_root / "bin/python3"
        self.python.write_text("#!/bin/sh\nexit 0\n")
        self.python.chmod(0o755)
        self.receipt_path = self.host_state / "receipts/new.json"
        self.receipt = {"schemaVersion": 1, "operatorUid": os.getuid(), "status": "installed_and_verified", "verification": {"passed": True},
            "tools": {
                "native-profiles": {"selection": {"commands": {}}, "staged": {"reuse": False, "installPath": str(self.assets), "treeSha256": h.tree_identity(self.assets)}},
                "python": {"selection": {"commands": {"python3": {"path": "bin/python3"}}},
                           "staged": {"reuse": False, "installPath": str(self.python_root), "treeSha256": h.tree_identity(self.python_root)}}}}
        self.receipt_path.write_text(json.dumps(self.receipt))
        (self.host_state / "latest.json").write_text(json.dumps({"receipt": str(self.host_state / "receipts/not-the-returned-receipt.json")}))
        self.profile_plan = self.root / "profiles.json"
        self.profile = {"schemaVersion": 1, "assetRoot": str(self.assets), "python": str(self.python), "pythonSha256": c.sha(self.python),
            "auditDirectory": str(self.root / "audit"), "receiptDirectory": str(self.root / "profile-receipts"),
            "clients": {"claude": {"configDir": str(self.root / "claude")},
                        "codex": {"home": str(self.root / "codex"), "skillsDir": str(self.root / "skills"), "activateReviewedHooks": False},
                        "omp": {"agentDir": str(self.root / "omp")}}}
        self.profile_plan.write_text(json.dumps(self.profile))
        self.site_path = self.root / "site installation.json"
        self.site = {"schemaVersion": 1, "evidence": "Synthetic inspected installation fixture", "coordinatorState": str(self.root / "coordinator-state"),
            "native": {"enabled": True, "plan": str(self.native_plan), "state": str(self.root / "native-state")},
            "host": {"plan": str(self.host_plan), "state": str(self.host_state), "catalog": str(self.catalog), "mode": "system"},
            "core": {"enabled": True, "config": str(self.core_config), "state": str(self.root / "core-state")},
            "clients": {"enabled": True, "names": ["codex", "claude", "python", "native-profiles"]},
            "profiles": {"enabled": True, "plan": str(self.profile_plan), "pythonCommand": "python3"},
            "modelSmoke": True, "retireOldTools": True}
        self.site_path.write_text(json.dumps(self.site))
        self.root_patch = patch.object(c, "ROOT", self.kit)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.calls = []

    def fake_run(self, argv, **kwargs):
        self.calls.append(argv)
        self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertNotIn("shell", kwargs)
        if len(argv) > 2 and Path(argv[1]).name == "hostctl.py" and argv[2] == "apply":
            return subprocess.CompletedProcess(argv, 0, json.dumps({"receipt": str(self.receipt_path), "passed": True}), "")
        return subprocess.CompletedProcess(argv, 0, "PRIVATE_SYNTHETIC_DETAIL\n", "")

    def prepared(self):
        site = c.load_site(self.site_path, "all")
        return site, c.steps_for(site, "all")

    def test_complete_sequence_uses_exact_receipt_and_retires_only_after_verification(self):
        site, steps = self.prepared()
        names = [step["name"] for step in steps]
        self.assertLess(names.index("host.apply"), names.index("core.install"))
        self.assertLess(names.index("core.install"), names.index("clients.stage"))
        self.assertLess(names.index("clients.stage"), names.index("profiles.apply"))
        self.assertEqual(names[-2:], ["core.model-smoke", "host.retire"])
        original_profile = self.profile_plan.read_bytes()
        output = io.StringIO()
        with patch.object(c.subprocess, "run", side_effect=self.fake_run), contextlib.redirect_stdout(output):
            result = c.apply(site, steps, "all", self.site_path)
        self.assertTrue(result["passed"])
        self.assertEqual(result["hostReceipt"], str(self.receipt_path))
        self.assertNotIn("PRIVATE_SYNTHETIC_DETAIL", output.getvalue())
        self.assertEqual(self.profile_plan.read_bytes(), original_profile)
        for argv in self.calls:
            if "--receipt" in argv:
                self.assertEqual(argv[argv.index("--receipt") + 1], str(self.receipt_path))
            self.assertNotIn("seed", argv)
            self.assertNotIn("enable-agent", argv)
        report = c.read(result["report"])
        self.assertEqual(report["status"], "requested_installer_steps_completed")
        self.assertEqual(Path(report["steps"][0]["log"]).stat().st_mode & 0o777, 0o600)

    def test_profile_failure_stops_model_probe_and_retirement_without_secret_output(self):
        site, steps = self.prepared()
        def fail_profile(argv, **kwargs):
            if len(argv) > 1 and Path(argv[1]).name == "install_profiles.py" and "--apply" in argv:
                self.calls.append(argv)
                return subprocess.CompletedProcess(argv, 2, "PRIVATE_SYNTHETIC_DETAIL", "policy blocker")
            return self.fake_run(argv, **kwargs)
        output = io.StringIO()
        with patch.object(c.subprocess, "run", side_effect=fail_profile), contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, "profiles.apply failed"):
                c.apply(site, steps, "all", self.site_path)
        self.assertFalse(any("retire" in argv or "model-smoke" in argv for argv in self.calls))
        self.assertNotIn("PRIVATE_SYNTHETIC_DETAIL", output.getvalue())
        report_path = next(Path(site["coordinatorState"]).glob("*/installation-report.json"))
        self.assertEqual(c.read(report_path)["status"], "blocked")

    def test_profile_binding_rejects_different_asset_path_or_python_identity(self):
        c.profile_binding(self.site, self.receipt_path)
        self.profile["assetRoot"] = str(self.root / "temporary-assets")
        self.profile_plan.write_text(json.dumps(self.profile))
        with self.assertRaisesRegex(RuntimeError, "assetRoot"):
            c.profile_binding(self.site, self.receipt_path)
        self.profile["assetRoot"] = str(self.assets)
        self.profile["pythonSha256"] = "0" * 64
        self.profile_plan.write_text(json.dumps(self.profile))
        with self.assertRaisesRegex(RuntimeError, "Python path/hash"):
            c.profile_binding(self.site, self.receipt_path)

    def test_unreviewed_hook_activation_and_incomplete_private_sources_are_rejected(self):
        self.profile["clients"]["codex"]["activateReviewedHooks"] = True
        self.profile_plan.write_text(json.dumps(self.profile))
        with self.assertRaisesRegex(RuntimeError, "reviewed asset manifest"):
            c.load_site(self.site_path, "all")
        self.host_plan.write_text(json.dumps({"privateRepositoriesChecked": []}))
        with self.assertRaisesRegex(RuntimeError, "private repository"):
            c.load_site(self.site_path, "all")

    def test_plan_is_read_only_and_focused_wrappers_do_not_retire(self):
        self.site["retireOldTools"] = False
        self.site_path.write_text(json.dumps(self.site))
        output = io.StringIO()
        with patch.object(sys, "argv", ["install-stack", "plan", "--site", str(self.site_path)]), \
                patch.object(c.subprocess, "run") as run, contextlib.redirect_stdout(output):
            c.main()
            run.assert_not_called()
        self.assertIn("@HOST_RECEIPT@", json.loads(output.getvalue())["dynamicArguments"])
        self.assertFalse(Path(self.site["coordinatorState"]).exists())
        for only in ("host", "native", "profiles"):
            names = [step["name"] for step in c.steps_for(c.load_site(self.site_path, only), only)]
            self.assertNotIn("host.retire", names)
            self.assertNotIn("core.install", names)

    def test_native_state_cannot_pollute_uninitialized_core_state(self):
        self.site["native"]["state"] = str(Path(self.site["core"]["state"]) / "native-packages")
        self.site_path.write_text(json.dumps(self.site))
        with self.assertRaisesRegex(RuntimeError, "non-nested state"):
            c.load_site(self.site_path, "all")

    def test_all_wrapper_preserves_site_argument_with_spaces(self):
        result = subprocess.run(["/bin/bash", str(KIT / "install-all.sh"), "plan", "--site", str(self.site_path)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["scope"], "all")
        self.assertFalse(Path(self.site["coordinatorState"]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
