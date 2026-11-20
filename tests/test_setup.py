#!/usr/bin/env python3
"""Behavioral checks for bootstrap boundaries, preservation and safe resumption."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup_under_test", HERE / "scripts/setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
BASE = Path(os.environ.get("AGENTIC_TEST_BASE_KIT", str(HERE)))


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="setup-tests-", dir=os.environ.get("AGENTIC_TEST_TMPDIR"))
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.old_root = setup.ROOT
        setup.ROOT = BASE
        self.state = self.root / "setup-state"
        self.actual = {"system": "Linux", "architecture": "x86_64", "os": {"id": "debian", "versionID": "13"},
                       "libc": {"name": "glibc", "version": "2.36"}, "existingProfiles": []}
        self.host_plan = self.file("host-plan.json", {"schemaVersion": 1, "privateRepositoriesChecked": ["Inspected a test-only local repository."],
                                                     "tools": {"test-tool": {"source": "existing", "adequate": True}}})
        self.catalog = self.file("catalog.json", {"schemaVersion": 1, "tools": {}})
        self.installation = self.file("installation.json", {"schemaVersion": 1, "evidence": "Fixture inventory completed.",
                  "coordinatorState": str(self.root / "coordinator-state"),
                  "host": {"plan": str(self.host_plan), "state": str(self.root / "host-state"), "mode": "user", "catalog": str(self.catalog)},
                  "native": {"enabled": False}, "core": {"enabled": False}, "clients": {"enabled": False},
                  "profiles": {"enabled": False}, "modelSmoke": False, "retireOldTools": False})
        self.config = self.file("setup.json", {"schemaVersion": 1, "schemaKind": "setup", "evidence": "Fixture target inspected.",
                 "bootstrapMode": "fresh", "target": {"profile": "debian13-x86_64", "minimumGlibc": "2.28"},
                 "installation": str(self.installation), "productivity": {"enabled": False}, "enrollment": {"enabled": False}})

    def tearDown(self):
        setup.ROOT = self.old_root
        self.temporary.cleanup()

    def file(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, indent=2) + "\n")
        path.chmod(0o600)
        return path

    def change(self, path, **values):
        data = setup.read(path)
        data.update(values)
        path.write_text(json.dumps(data))

    def readonly(self, argv):
        self.assertNotIn("apply", argv)
        self.assertNotIn("install", argv)
        return {"argv": argv, "passed": True}

    def installer(self, state, name, argv, timeout=7200):
        self.assertEqual(name, "installation")
        result_path = Path(argv[argv.index("--result-json") + 1])
        report = self.file("installation-report.json", {"passed": True, "status": "requested_installer_steps_completed", "siteSha256": setup.sha(self.installation)})
        result_path.write_text(json.dumps({"passed": True, "status": "requested_installer_steps_completed", "report": str(report), "hostReceipt": str(self.root / "receipt.json")}))
        return {"name": name, "passed": True}

    def protected(self):
        profile = self.root / "client-profile"
        profile.mkdir(mode=0o700)
        route = profile / "route.json"
        route.write_text('{"baseUrl":"http://model.private/v1","keySource":"env:PRIVATE_KEY"}\n')
        route.chmod(0o600)
        plan = self.file("preserve.json", {"schemaVersion": 1, "discoveryComplete": True,
              "discoveryEvidence": "Inspected fixture profile and route source.",
              "roots": [{"path": str(profile), "role": "Existing client route and brain"}], "envNames": []})
        self.change(self.config, bootstrapMode="existing", preservation={"plan": str(plan), "state": str(self.root / "original-baseline")})
        self.actual["existingProfiles"] = [str(profile)]
        return profile, route

    def test_missing_config_does_not_create_state(self):
        with self.assertRaisesRegex(setup.Blocked, "private site configuration"):
            setup.main(["apply", "--state", str(self.state)])
        self.assertFalse(self.state.exists())

    def test_invalid_config_does_not_create_state_or_run_any_step(self):
        self.change(self.config, evidence="REPLACE_WITH_FINDING")
        with patch.object(setup, "run_private") as mutation:
            with self.assertRaises(setup.Blocked):
                setup.apply(self.config, self.state, actual=self.actual)
        mutation.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_plan_only_runs_readonly_validators_and_leaves_input_unchanged(self):
        before = {str(path): setup.sha(path) for path in self.root.iterdir() if path.is_file()}
        with patch.object(setup, "run_readonly", side_effect=self.readonly):
            result = setup.plan(self.config, self.state, actual=self.actual)
        self.assertTrue(result["passed"])
        self.assertFalse(result["machineChanged"])
        self.assertFalse(self.state.exists())
        self.assertEqual(before, {str(path): setup.sha(path) for path in self.root.iterdir() if path.is_file()})

    def test_wrong_architecture_and_musl_fail_before_installer(self):
        for change in ({"architecture": "aarch64"}, {"libc": {"name": "musl", "version": "1.2.5"}}):
            actual = {**self.actual, **change}
            with self.subTest(change=change), patch.object(setup, "run_private") as mutation:
                with self.assertRaises(setup.Blocked):
                    setup.apply(self.config, self.state, actual=actual)
                mutation.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_fresh_mode_refuses_existing_profiles_without_preservation(self):
        actual = {**self.actual, "existingProfiles": [str(self.root / "previous-client")]}
        with self.assertRaisesRegex(setup.Blocked, "preservation"):
            setup.validate(self.config, self.state, actual=actual)
        self.assertFalse(self.state.exists())

    def test_existing_omp_replacement_cannot_skip_phase_one(self):
        self.protected()
        self.change(self.host_plan, tools={"omp": {"source": "kit", "fallbackReason": "unavailable", "evidence": "Fixture missing internal candidate."}})
        with self.assertRaisesRegex(setup.Blocked, "Claude -> OMP"):
            setup.validate(self.config, self.state, actual=self.actual)

    def test_apply_resume_reverifies_instead_of_reinstalling_completed_stage(self):
        with patch.object(setup, "run_readonly", side_effect=self.readonly), patch.object(setup, "run_private", side_effect=self.installer) as mutation:
            first = setup.apply(self.config, self.state, actual=self.actual)
        self.assertEqual(first["status"], "requested_setup_steps_completed")
        self.assertEqual(mutation.call_count, 1)
        with patch.object(setup, "run_readonly", side_effect=self.readonly), patch.object(setup, "run_private") as mutation, patch.object(setup, "verify_coordinator", return_value=[]) as verify:
            second = setup.apply(self.config, self.state, actual=self.actual)
        mutation.assert_not_called()
        verify.assert_called_once()
        self.assertTrue(second["passed"])

    def test_bound_fresh_resume_allows_profiles_created_by_installation(self):
        with patch.object(setup, "run_readonly", side_effect=self.readonly), patch.object(setup, "run_private", side_effect=self.installer):
            setup.apply(self.config, self.state, actual=self.actual)
        after = {**self.actual, "existingProfiles": [str(self.root / "newly-installed-client")]}
        with patch.object(setup, "run_readonly", side_effect=self.readonly), patch.object(setup, "run_private") as mutation, patch.object(setup, "verify_coordinator", return_value=[]):
            result = setup.apply(self.config, self.state, actual=after)
        mutation.assert_not_called()
        self.assertTrue(result["passed"])

    def test_changed_input_blocks_resume_without_installation(self):
        with patch.object(setup, "run_readonly", side_effect=self.readonly), patch.object(setup, "run_private", side_effect=self.installer):
            setup.apply(self.config, self.state, actual=self.actual)
        self.change(self.host_plan, privateRepositoriesChecked=["Another inspection changes the pinned decision."])
        with patch.object(setup, "run_readonly", side_effect=self.readonly), patch.object(setup, "run_private") as mutation:
            with self.assertRaisesRegex(setup.Blocked, "inputs changed"):
                setup.apply(self.config, self.state, actual=self.actual)
        mutation.assert_not_called()

    def test_real_preservation_baseline_blocks_route_mutation(self):
        profile, route = self.protected()
        original = route.read_bytes()
        def alter(state, name, argv, timeout=7200):
            result = self.installer(state, name, argv, timeout)
            route.write_text('{"baseUrl":"http://changed.private/v1"}\n')
            return result
        with patch.object(setup, "run_readonly", side_effect=self.readonly), patch.object(setup, "run_private", side_effect=alter):
            with self.assertRaisesRegex(setup.Blocked, "Preservation verification blocked"):
                setup.apply(self.config, self.state, actual=self.actual)
        baseline = self.root / "original-baseline"
        recorded = setup.read(baseline / "baseline.json")
        self.assertEqual(recorded["entries"][str(route)]["sha256"], __import__("hashlib").sha256(original).hexdigest())
        self.assertEqual(setup.read(self.state / "progress.json")["status"], "blocked")

    def test_unrelated_state_and_symlink_state_are_preserved(self):
        self.state.mkdir()
        occupant = self.state / "unrelated.txt"
        occupant.write_text("keep me")
        with self.assertRaisesRegex(setup.Blocked, "unrelated"):
            setup.validate(self.config, self.state, actual=self.actual)
        self.assertEqual(occupant.read_text(), "keep me")
        link = self.root / "state-link"
        link.symlink_to(self.state, target_is_directory=True)
        with self.assertRaisesRegex(setup.Blocked, "symlink"):
            setup.validate(self.config, link, actual=self.actual)

    def test_docker_reuses_working_local_daemon(self):
        fake = types.SimpleNamespace(docker=lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="29.0.2\n"))
        site = {"core": {"config": "/private/site.json", "state": str(self.root / "core")}}
        with patch.object(setup, "module", return_value=fake), patch.object(setup, "run_private") as mutation:
            result = setup.docker_ready({"docker": {"enabled": True}}, site, self.state)
        self.assertEqual(result["source"], "existing-local-daemon")
        mutation.assert_not_called()

    def test_explicit_broken_docker_socket_does_not_create_another_daemon(self):
        fake = types.SimpleNamespace(docker=lambda *a, **k: types.SimpleNamespace(returncode=1, stdout=""))
        site = {"core": {"config": "/private/site.json", "state": str(self.root / "core"), "dockerHost": "unix:///run/selected.sock"}}
        with patch.object(setup, "module", return_value=fake), patch.object(setup, "run_private") as mutation:
            with self.assertRaisesRegex(setup.Blocked, "explicitly selected"):
                setup.docker_ready({"docker": {"enabled": True}}, site, self.state)
        mutation.assert_not_called()

    def test_minimal_compile_failure_does_not_create_setup_state(self):
        self.change(self.config, schemaKind="minimal")
        with patch.object(setup, "compile_minimal", side_effect=setup.Blocked("Missing factual private supply")):
            with self.assertRaisesRegex(setup.Blocked, "private supply"):
                setup.execute_config("apply", self.config, self.state, "all")
        self.assertFalse(self.state.exists())

    @unittest.skipUnless((BASE / "scripts/compile-site.py").exists(), "Requires the assembled r5 compiler")
    def test_actual_minimal_compiler_relocation_and_source_pin(self):
        # Exercise a real private-artifact plan without requiring large release bytes in source CI.
        fixture_binary = self.root / "private-jq-fixture"
        fixture_binary.write_text("#!/bin/sh\nprintf 'jq fixture\\n'\n")
        fixture_binary.chmod(0o755)
        supply_index = self.file("private-supply.json", {"schemaVersion": 1, "tools": {"jq": {
            "source": "internal", "path": str(fixture_binary), "sha256": setup.sha(fixture_binary), "format": "file",
            "evidence": "Disposable fixture executable for plan/compiler validation; no production adequacy claim."}}})
        minimal = self.file("minimal.json", {"schemaVersion": 1, "schemaKind": "minimal", "bootstrapMode": "fresh",
            "evidence": "Isolated controller integration fixture; no real machine installation.", "mode": "user",
            "stateRoot": str(self.root / "component-states"), "canonicalCommands": "none", "reuseExisting": False,
            "privateSupply": {"roots": [], "index": str(supply_index), "inspectionEvidence": "The isolated fixture supplies an explicit private executable index.",
                              "allowKitFallback": False},
            "tools": ["jq"], "nativePackages": {"enabled": False, "evidence": "Fixture requires only existing controller/base tools for read-only validation."},
            "core": {"enabled": False}, "profiles": {"enabled": False}, "productivity": {"enabled": False}})
        def installed(state, name, argv, timeout=7200):
            result_path = Path(argv[argv.index("--result-json") + 1])
            result_path.write_text(json.dumps({"passed": True, "status": "requested_installer_steps_completed", "report": str(self.root / "fixture-report.json"), "hostReceipt": str(self.root / "fixture-receipt.json")}))
            return {"passed": True}
        with patch.object(setup, "inventory", return_value=self.actual), patch.object(setup, "run_private", side_effect=installed):
            result = setup.execute_config("apply", minimal, self.state, "all")
        self.assertTrue(result["passed"])
        compiled = setup.read(self.state / "compiled/setup.json")
        self.assertEqual(compiled["installation"], str(self.state / "compiled/installation.json"))
        progress = setup.read(self.state / "progress.json")
        self.assertEqual(progress["inputSha256"][str(minimal)], setup.sha(minimal))
        self.change(minimal, evidence="Changed original site after compilation.")
        with patch.object(setup, "run_private") as mutation:
            with self.assertRaisesRegex(setup.Blocked, "changed since compilation"):
                setup.execute_config("apply", minimal, self.state, "all")
        mutation.assert_not_called()

    def test_existing_agent_delegates_phase_flow_and_preserves_config_context(self):
        self.change(self.config, bootstrapMode="existing", agent={"engine": "claude", "args": ["--profile", "internal"]})
        with patch.object(os, "execvpe") as launch:
            setup.agent(self.config, self.state)
        executable, argv, env = launch.call_args.args
        self.assertEqual(executable, str(BASE / "upgrade.sh"))
        self.assertEqual(argv[1], "start-claude")
        self.assertEqual(env["AGENTIC_SETUP_CONFIG"], str(self.config))
        self.assertEqual(env["AGENTIC_SETUP_STATE"], str(self.state))
        self.assertEqual(argv[-3:], ["--", "--profile", "internal"])


if __name__ == "__main__":
    unittest.main()
