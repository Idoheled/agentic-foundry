"""Tests of phase control/evidence, using local fixtures, never real model qualification."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "upgrade-flow.py"
SPEC = importlib.util.spec_from_file_location("upgrade_flow_under_test", SCRIPT)
flow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flow)


PROOF_SCRIPT = r'''import hashlib,json,os,pathlib,sys
mode=sys.argv[1]
target=pathlib.Path(os.environ["AGENTIC_UPGRADE_PROOF_PATH"])
if mode=="fail":
    raise SystemExit(7)
if mode=="no-proof":
    raise SystemExit(0)
payload={"schemaVersion":1,"passed":True,
 "runToken":os.environ["AGENTIC_UPGRADE_PROBE_TOKEN"],
 "phase":os.environ["AGENTIC_UPGRADE_PHASE"],
 "check":os.environ["AGENTIC_UPGRADE_CHECK"],
 "observations":["Local test fixture wrote and read its isolated canary; no model call was made."]}
if mode=="stale": payload["runToken"]="old-run-token"
if mode=="wrong-gate": payload["check"]="different-gate"
if mode=="empty-findings": payload["observations"]=[]
if mode=="bad-attachment":
    payload["evidenceFiles"]=[{"path":str(pathlib.Path(__file__).resolve()),"sha256":"0"*64}]
target.write_text(json.dumps(payload))
'''


class UpgradeFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="upgrade-flow-test-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "kit"
        self.root.mkdir()
        (self.root / "config").mkdir()
        self.dump(self.root / "config/host-catalog.json", {"tools": {"omp": {}, "claude": {}}})
        self.root_patch = mock.patch.object(flow, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.state = self.base / "state"
        self.state.mkdir(mode=0o700)
        self.cwd = self.base / "project with spaces"
        self.cwd.mkdir()
        self.command = self.base / "bin" / "omp"
        self.command.parent.mkdir()
        self.command.write_text("#!/bin/sh\nexit 0\n")
        self.command.chmod(0o755)
        self.other_command = self.base / "bin" / "claude"
        self.other_command.write_text("#!/bin/sh\nexit 0\n")
        self.other_command.chmod(0o755)
        self.proof_script = self.base / "proof.py"
        self.proof_script.write_text(PROOF_SCRIPT)
        self.preservation_plan = self.base / "preservation-plan.json"
        self.dump(self.preservation_plan, {"schemaVersion": 1, "roots": []})
        self.saved_plan = self.state / "upgrade-plan.json"
        self.dump(self.saved_plan, {"schemaVersion": 1, "evidence": "Inspected local test fixtures."})
        self.preservation_report = self.state / "preservation-fixture.json"
        self.dump(self.preservation_report, {"passed": True,
                  "configurationIdentity": hashlib.sha256(b"isolated-configuration-fixture").hexdigest(),
                  "protectedRoots": [str(self.cwd), str(self.base / "external-brain")]})
        self.preserve_patch = mock.patch.object(flow, "preserve", return_value=flow.binding(self.preservation_report))
        self.mock_preserve = self.preserve_patch.start()
        self.addCleanup(self.preserve_patch.stop)
        self.receipt = self.state / "omp-host-receipt.json"
        self.receipt_document = self.make_receipt("omp", self.command)
        self.dump(self.receipt, self.receipt_document)
        self.value = {
            "schemaVersion": 1, "operatorUid": os.getuid(), "kitRoot": str(self.root),
            "stage": "phase1", "plan": flow.binding(self.saved_plan),
            "preservationPlan": flow.binding(self.preservation_plan),
            "ompContext": {"command": str(self.command), "cwd": str(self.cwd),
                           "arguments": ["--profile", "my-internal-profile"]},
            "expectedOmpVersion": "19.0.1-offline.1", "checks": {"omp": {}, "stack": {}},
            "phase2Runs": [],
            "phase1Install": {"result": {"passed": True}, "host": {
                "site": {"host": {}}, "inputs": [], "receipt": str(self.receipt), "tools": ["omp"]}},
        }
        flow.save(self.state, self.value)

    def dump(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2))
        return path

    def make_receipt(self, name, command):
        return {"status": "installed_and_verified", "verification": {"passed": True},
                "operatorUid": os.getuid(),
                "tools": {name: {"selection": {"version": "19.0.1-offline.1",
                                                 "commands": {name: "bin/" + name}},
                                 "staged": {"reuse": False}}},
                "actions": [{"tool": name, "command": name, "path": str(command)}]}

    def spec(self, mode="pass", cwd=None, name="probe"):
        return self.dump(self.base / (name + ".json"), {
            "schemaVersion": 1,
            "purpose": "Execute an isolated proof-token fixture; this does not qualify a model.",
            "argv": [str(Path(sys.executable).resolve()), str(self.proof_script), mode],
            "cwd": str(cwd or self.cwd), "timeoutSeconds": 10})

    def record(self, name="profile-rehearsal", mode="pass", phase="omp"):
        return flow.record_check(self.state, self.value, phase, name,
                                 self.spec(mode, name=phase + "-" + name + "-" + mode))

    def fill_gates(self, phase="omp"):
        for name in flow.OMP_GATES if phase == "omp" else flow.STACK_GATES:
            self.record(name, phase=phase)

    def accepted(self, phase="omp"):
        # Booleans exercise schema control only; these are never delivered as target evidence.
        return self.dump(self.base / (phase + "-acceptance.json"), {
            "schemaVersion": 1, "passed": True, "summary": "Test-only acceptance document.",
            "oldToolDisposition": "No old tool is removed by this isolated test fixture.",
            "realInternalEndpoints": True, "preservedExistingConfiguration": True,
            "checks": {name: {"passed": True, "evidence": "Fixture command and bound proof inspected."}
                       for name in (flow.OMP_GATES if phase == "omp" else flow.STACK_GATES)}})

    def which(self, command):
        return {"omp": str(self.command), "claude": str(self.other_command)}.get(command)

    def finish_omp(self):
        self.fill_gates()
        with mock.patch.object(flow, "verified_host", return_value=self.receipt_document), \
             mock.patch.object(flow, "preserve", return_value=flow.binding(self.preservation_report)), \
             mock.patch.object(flow.shutil, "which", side_effect=self.which):
            return flow.complete_omp(self.state, self.value, self.accepted())

    def make_site(self, tools=None):
        host_plan = self.dump(self.base / "host-plan.json", {"tools": tools or {"omp": {}}})
        site = {"schemaVersion": 1, "retireOldTools": False, "modelSmoke": False,
                "host": {"plan": str(host_plan), "state": str(self.state / "host"), "mode": "system"},
                "native": {"enabled": False}, "core": {"enabled": False},
                "clients": {"enabled": False}, "profiles": {"enabled": False}}
        return self.dump(self.base / "site.json", site), site

    def prepare_stack_fixture(self):
        self.finish_omp()
        self.value["stage"] = "phase2"
        with mock.patch.object(flow, "readonly_host", return_value={"passed": True}), \
             mock.patch.object(flow.shutil, "which", side_effect=self.which):
            self.fill_gates("stack")
        receipt = self.state / "stack-host-receipt.json"
        document = self.make_receipt("claude", self.other_command)
        self.dump(receipt, document)
        profile = self.dump(self.base / "native-profile-plan.json", {
            "clients": {"omp": {}, "claude": {}, "codex": {}}})
        core = self.dump(self.base / "core-site.json", {"schemaVersion": 1})
        log = self.state / "stack-install-fixture.log"
        log.write_text("Mocked installer fixture; no host transaction/model qualification performed.\n")
        site = {"host": {}, "core": {"enabled": True, "config": str(core)},
                "profiles": {"enabled": True, "plan": str(profile)}}
        self.value["phase2Host"] = {"receipt": str(receipt), "site": site,
                                    "inputs": [flow.binding(profile), flow.binding(core)],
                                    "tools": ["claude"]}
        self.value["phase2Runs"] = [{"scope": "all", "site": site,
                                     "inputs": [flow.binding(profile), flow.binding(core)],
                                     "result": {"passed": True, "log": flow.binding(log)}}]
        self.dump(self.state / "preservation/baseline.json", {
            "plan": {"roots": [{"path": str(self.cwd)}]},
            "followedSymlinkTargets": [str(self.base / "external-brain")],
        })
        return document

    def complete_stack_fixture(self, document):
        with mock.patch.object(flow, "readonly_host", return_value={"passed": True}), \
             mock.patch.object(flow, "verified_host", return_value=document), \
             mock.patch.object(flow, "preserve", return_value=flow.binding(self.preservation_report)), \
             mock.patch.object(flow.shutil, "which", side_effect=self.which):
            return flow.complete_stack(self.state, self.value, self.accepted("stack"))

    def prepare_reinstallation(self):
        self.fill_gates()
        rehearsal = self.value["checks"]["omp"]["profile-rehearsal"]
        proof_path = Path(rehearsal["proof"]["path"])
        proof = flow.read(proof_path)
        artifact = flow.binding(self.command)
        proof["evidenceFiles"] = [artifact]
        self.dump(proof_path, proof)
        rehearsal["proof"] = flow.binding(proof_path)
        rehearsal["evidenceFiles"] = [artifact]
        flow.save(self.state, self.value)
        path, site = self.make_site()
        host = mock.Mock()
        host.load_inputs.return_value = ({}, {}, {"omp": {"reuse": True,
            "executables": {"omp": {"path": str(self.command)}}}})
        return path, site, host

    def prepare_cleanup_fixture(self):
        other_receipt = self.dump(self.state / "other-host-receipt.json", self.make_receipt("claude", self.other_command))
        self.value["phase1Install"]["host"]["site"]["host"] = {
            "state": str(self.state / "phase1-host"), "mode": "system"}
        self.value["phase2Host"] = {"receipt": str(other_receipt),
                                    "site": {"host": {"state": str(self.state / "phase2-host"), "mode": "system"}}}
        completion = self.dump(self.state / "completion.json", {
            "schemaVersion": 1, "status": "completed", "passed": True,
            "hostReceipts": [flow.binding(self.receipt), flow.binding(other_receipt)],
            "protectedRoots": [str(self.cwd)]})
        self.value.update(stage="completed", completion=flow.binding(completion))
        flow.save(self.state, self.value)
        return completion

    def test_phase1_rejects_other_host_tools_and_enabled_profiles(self):
        path, site = self.make_site({"omp": {}, "claude": {}})
        with self.assertRaisesRegex(RuntimeError, "only OMP"):
            flow.site_inputs(path, "omp", "host")
        path, site = self.make_site()
        site["profiles"]["enabled"] = True
        self.dump(path, site)
        with self.assertRaisesRegex(RuntimeError, "cannot enable profiles"):
            flow.site_inputs(path, "omp", "host")

    def test_phase1_rejects_broad_coordinator_and_early_retirement(self):
        path, site = self.make_site()
        with self.assertRaisesRegex(RuntimeError, "host upgrade only"):
            flow.site_inputs(path, "omp", "all")
        site["retireOldTools"] = True
        self.dump(path, site)
        with self.assertRaisesRegex(RuntimeError, "Defer retirement"):
            flow.site_inputs(path, "omp", "host")

    def test_phase2_rejects_running_omp_replacement(self):
        path, _ = self.make_site({"omp": {}, "claude": {}})
        with self.assertRaisesRegex(RuntimeError, "running qualified OMP"):
            flow.site_inputs(path, "stack", "host")

    def test_live_install_requires_profile_rehearsal(self):
        path, _ = self.make_site()
        with mock.patch.object(flow, "run_private") as runner, \
             mock.patch.object(flow, "preserve") as preservation:
            with self.assertRaisesRegex(RuntimeError, "[Rr]ehears"):
                flow.install(self.state, self.value, path, "omp", "host")
            runner.assert_not_called()
            preservation.assert_not_called()

    def test_live_install_rejects_changed_rehearsal_evidence(self):
        self.record()
        proof = Path(self.value["checks"]["omp"]["profile-rehearsal"]["proof"]["path"])
        proof.write_text("changed rehearsal evidence")
        path, _ = self.make_site()
        with mock.patch.object(flow, "run_private") as runner, \
             mock.patch.object(flow, "preserve"):
            with self.assertRaisesRegex(RuntimeError, "changed|rehearsal|evidence"):
                flow.install(self.state, self.value, path, "omp", "host")
            runner.assert_not_called()

    def test_runtime_probe_cannot_precede_installation(self):
        self.value.pop("phase1Install")
        with self.assertRaisesRegex(RuntimeError, "Install OMP"):
            self.record("internal-model")

    def test_real_fixture_records_unique_proof_and_private_permissions(self):
        first = self.record()
        second = self.record()
        self.assertNotEqual(first["proof"]["path"], second["proof"]["path"])
        one, two = flow.read(first["proof"]["path"]), flow.read(second["proof"]["path"])
        self.assertNotEqual(one["runToken"], two["runToken"])
        self.assertEqual(stat.S_IMODE(Path(second["proof"]["path"]).stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(Path(second["log"]["path"]).stat().st_mode), 0o600)

    def test_acceptance_probe_checks_preservation_before_and_after(self):
        self.record()
        labels = [call.args[2] for call in self.mock_preserve.call_args_list]
        self.assertTrue(any(label.endswith("-before") for label in labels))
        self.assertTrue(any(label.endswith("-after") for label in labels))

    def test_post_probe_preservation_failure_leaves_gate_failed(self):
        with mock.patch.object(flow, "preserve", side_effect=[flow.binding(self.preservation_report),
                                RuntimeError("profile changed during probe")]):
            with self.assertRaises(RuntimeError):
                self.record()
        saved = flow.read(self.state / "workflow.json")
        self.assertFalse(saved["checks"]["omp"]["profile-rehearsal"]["passed"])

    def test_stale_wrong_gate_empty_and_unbound_proofs_fail(self):
        for mode in ("stale", "wrong-gate", "empty-findings", "bad-attachment", "no-proof"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(RuntimeError, "Gate failed"):
                    self.record(mode=mode)
                self.assertFalse(self.value["checks"]["omp"]["profile-rehearsal"]["passed"])

    def test_failed_command_rerun_invalidates_prior_pass(self):
        self.record()
        with self.assertRaisesRegex(RuntimeError, "Gate failed"):
            self.record(mode="fail")
        self.assertFalse(flow.read(self.state / "workflow.json")["checks"]["omp"]["profile-rehearsal"]["passed"])

    def test_invalid_spec_rerun_invalidates_prior_pass(self):
        self.record()
        spec = self.spec()
        content = flow.read(spec)
        content["argv"] = [str(self.base / "missing-command")]
        self.dump(spec, content)
        with self.assertRaises((RuntimeError, OSError)):
            flow.record_check(self.state, self.value, "omp", "profile-rehearsal", spec)
        self.assertFalse(flow.read(self.state / "workflow.json")["checks"]["omp"]["profile-rehearsal"]["passed"])

    def test_execution_error_rerun_invalidates_prior_pass(self):
        self.record()
        nonexec = self.base / "not-executable"
        nonexec.write_text("not an executable")
        spec = self.spec()
        content = flow.read(spec)
        content["argv"] = [str(nonexec)]
        self.dump(spec, content)
        with self.assertRaises((RuntimeError, OSError)):
            flow.record_check(self.state, self.value, "omp", "profile-rehearsal", spec)
        self.assertFalse(flow.read(self.state / "workflow.json")["checks"]["omp"]["profile-rehearsal"]["passed"])

    def test_effective_project_cwd_is_required_for_model_probe(self):
        spec = self.spec(cwd=self.base)
        with self.assertRaisesRegex(RuntimeError, "preserved project"):
            flow.record_check(self.state, self.value, "omp", "internal-model", spec)

    def test_missing_gate_cannot_create_handoff(self):
        with mock.patch.object(flow, "verified_host") as verifier:
            with self.assertRaisesRegex(RuntimeError, "Missing or failed"):
                flow.complete_omp(self.state, self.value, self.accepted())
            verifier.assert_not_called()
        self.assertEqual(self.value["stage"], "phase1")
        self.assertFalse((self.state / "OMP_HANDOFF.md").exists())

    def test_changed_proof_blocks_completion(self):
        self.fill_gates()
        proof = Path(self.value["checks"]["omp"]["tool-roundtrip"]["proof"]["path"])
        proof.write_text("modified after execution")
        with self.assertRaisesRegex(RuntimeError, "changed"):
            flow.acceptance(self.value, "omp", self.accepted())

    def test_acceptance_requires_real_route_and_preservation_assertions(self):
        self.fill_gates()
        for key in ("realInternalEndpoints", "preservedExistingConfiguration"):
            path = self.accepted()
            data = flow.read(path)
            data[key] = False
            self.dump(path, data)
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                flow.acceptance(self.value, "omp", path)

    def test_canonical_old_path_is_rejected_even_when_command_exists(self):
        old = self.base / "old-omp"
        old.write_text("#!/bin/sh\nexit 0\n")
        old.chmod(0o755)
        with mock.patch.object(flow.shutil, "which", return_value=str(old)):
            with self.assertRaisesRegex(RuntimeError, "unqualified/old"):
                flow.canonical_bindings(self.receipt_document, self.value["ompContext"])

    def test_phase1_finishes_at_manual_boundary_without_launching_omp(self):
        with mock.patch.object(flow.os, "execvpe") as executor:
            result = self.finish_omp()
            executor.assert_not_called()
        self.assertEqual(result["stage"], "awaiting_omp")
        self.assertEqual(self.value["stage"], "awaiting_omp")
        self.assertTrue((self.state / "OMP_HANDOFF.md").is_file())
        self.assertEqual(result["nextArgv"][-2:], ["--state", str(self.state)])

    def test_continuation_restores_cwd_and_named_profile_arguments(self):
        self.finish_omp()
        with mock.patch.object(flow.shutil, "which", side_effect=self.which), \
             mock.patch.object(flow, "preserve", return_value=flow.binding(self.preservation_report)), \
             mock.patch.object(flow, "readonly_host", return_value={"passed": True}):
            argv, cwd = flow.prepare_omp(self.state, self.value)
        self.assertEqual(cwd, str(self.cwd))
        self.assertEqual(argv[:3], [str(self.command), "--profile", "my-internal-profile"])
        self.assertEqual(argv[3:6], ["--approval-mode", "yolo", "-p"])
        self.assertEqual(self.value["stage"], "phase2")

    def test_continuation_reverifies_complete_omp_runtime(self):
        self.finish_omp()
        with mock.patch.object(flow.shutil, "which", side_effect=self.which), \
             mock.patch.object(flow, "preserve", return_value=flow.binding(self.preservation_report)), \
             mock.patch.object(flow, "readonly_host", side_effect=RuntimeError("OMP runtime tree changed")) as verifier:
            with self.assertRaisesRegex(RuntimeError, "runtime tree changed"):
                flow.prepare_omp(self.state, self.value)
            verifier.assert_called()
        self.assertEqual(self.value["stage"], "awaiting_omp")

    def test_continuation_rejects_changed_handoff(self):
        self.finish_omp()
        (self.state / "OMP_HANDOFF.md").write_text("changed")
        with self.assertRaisesRegex(RuntimeError, "changed"):
            flow.prepare_omp(self.state, self.value)

    def test_continuation_rejects_changed_phase1_host_receipt(self):
        self.finish_omp()
        self.receipt.write_text("changed installed-runtime receipt")
        with mock.patch.object(flow, "readonly_host") as verifier:
            with self.assertRaisesRegex(RuntimeError, "changed"):
                flow.prepare_omp(self.state, self.value)
            verifier.assert_not_called()

    def test_rehearsal_must_bind_the_selected_omp_artifact(self):
        self.record()
        path, _ = self.make_site()
        host = mock.Mock()
        host.load_inputs.return_value = ({}, {}, {"omp": {"reuse": True,
            "executables": {"omp": {"path": str(self.command)}}}})
        with mock.patch.object(flow, "preserve"), \
             mock.patch.object(flow, "host_instance", return_value=host), \
             mock.patch.object(flow, "run_private") as runner:
            with self.assertRaisesRegex(RuntimeError, "exact selected OMP"):
                flow.install(self.state, self.value, path, "omp", "host")
            runner.assert_not_called()

    def test_post_install_input_conflict_invalidates_previous_runtime_gates(self):
        path, site, host = self.prepare_reinstallation()

        def installer_mutated_input(*args, **kwargs):
            site["evidence"] = "Changed during the mocked installation."
            self.dump(path, site)
            return {"passed": True, "exitCode": 0}

        with mock.patch.object(flow, "preserve"), \
             mock.patch.object(flow, "host_instance", return_value=host), \
             mock.patch.object(flow, "run_private", side_effect=installer_mutated_input):
            with self.assertRaisesRegex(RuntimeError, "changed"):
                flow.install(self.state, self.value, path, "omp", "host")
        saved = flow.read(self.state / "workflow.json")
        self.assertFalse(saved["checks"]["omp"].get("internal-model", {}).get("passed", False))

    def test_wrong_installed_version_is_persisted_as_failed_attempt(self):
        path, site, host = self.prepare_reinstallation()
        changed_receipt = dict(self.receipt_document)
        changed_receipt["tools"] = {"omp": {"selection": {"version": "unexpected-version"}}}
        self.dump(self.receipt, changed_receipt)
        selected = {"site": site, "inputs": [], "receipt": str(self.receipt), "tools": ["omp"]}

        def successful_installer_with_result(*args, **kwargs):
            argv = args[2]
            target = Path(argv[argv.index("--result-json") + 1])
            self.dump(target, {"passed": True, "hostReceipt": str(self.receipt)})
            return {"passed": True, "exitCode": 0}

        with mock.patch.object(flow, "preserve"), \
             mock.patch.object(flow, "host_instance", return_value=host), \
             mock.patch.object(flow, "host_record", return_value=selected), \
             mock.patch.object(flow, "run_private", side_effect=successful_installer_with_result):
            with self.assertRaisesRegex(RuntimeError, "version differs"):
                flow.install(self.state, self.value, path, "omp", "host")
        saved = flow.read(self.state / "workflow.json")
        self.assertFalse(saved["phase1Install"]["result"]["passed"])
        self.assertFalse(saved["checks"]["omp"].get("internal-model", {}).get("passed", False))

    def test_load_rejects_changed_preservation_plan(self):
        self.dump(self.preservation_plan, {"schemaVersion": 1, "roots": [{"path": "/changed"}]})
        with self.assertRaisesRegex(RuntimeError, "changed"):
            flow.load(self.state)

    def test_omp_launcher_unavailable_before_handoff(self):
        with self.assertRaisesRegex(RuntimeError, "only after phase 1"):
            flow.prepare_omp(self.state, self.value)

    def test_stack_install_unavailable_before_manual_continuation(self):
        self.finish_omp()
        path, _ = self.make_site({"claude": {}})
        with mock.patch.object(flow, "run_private") as runner:
            with self.assertRaisesRegex(RuntimeError, "Wrong phase"):
                flow.install(self.state, self.value, path, "stack", "host")
            runner.assert_not_called()

    def test_success_handoff_requires_preservation_to_pass(self):
        self.fill_gates()
        with mock.patch.object(flow, "verified_host", return_value=self.receipt_document), \
             mock.patch.object(flow.shutil, "which", side_effect=self.which), \
             mock.patch.object(flow, "preserve", side_effect=RuntimeError("preservation failed")):
            with self.assertRaisesRegex(RuntimeError, "preservation failed"):
                flow.complete_omp(self.state, self.value, self.accepted())
        self.assertEqual(self.value["stage"], "phase1")
        self.assertFalse((self.state / "OMP_HANDOFF.md").exists())

    def test_bound_host_plan_changes_block_verification_before_commands(self):
        source = self.dump(self.base / "bound-host-plan.json", {"tools": {"omp": {}}})
        record = {"inputs": [flow.binding(source)], "site": {}, "receipt": str(self.receipt)}
        source.write_text("modified selection")
        with mock.patch.object(flow, "run_private") as runner:
            with self.assertRaisesRegex(RuntimeError, "changed"):
                flow.verified_host(self.state, record, "test-binding")
            runner.assert_not_called()

    def test_stack_completion_requires_all_catalog_tools(self):
        document = self.prepare_stack_fixture()
        self.dump(self.root / "config/host-catalog.json", {"tools": {"omp": {}, "claude": {}, "node": {}}})
        with self.assertRaisesRegex(RuntimeError, "omits catalog tools.*node"):
            self.complete_stack_fixture(document)
        self.assertFalse((self.state / "completion.json").exists())

    def test_stack_completion_requires_recorded_core_and_native_profiles(self):
        document = self.prepare_stack_fixture()
        self.value["phase2Runs"][0]["scope"] = "host"
        with self.assertRaisesRegex(RuntimeError, "No successful core"):
            self.complete_stack_fixture(document)
        self.value["phase2Runs"][0]["scope"] = "all"
        self.value["phase2Runs"][0]["site"]["profiles"]["enabled"] = False
        with self.assertRaisesRegex(RuntimeError, "Native profile installation is not recorded"):
            self.complete_stack_fixture(document)

    def test_stack_completion_rejects_changed_install_evidence(self):
        document = self.prepare_stack_fixture()
        Path(self.value["phase2Runs"][0]["result"]["log"]["path"]).write_text("mutated installer log")
        with self.assertRaisesRegex(RuntimeError, "changed"):
            self.complete_stack_fixture(document)
        self.assertEqual(self.value["stage"], "phase2")

    def test_stack_completion_records_bound_receipts_and_protected_roots(self):
        document = self.prepare_stack_fixture()
        result = self.complete_stack_fixture(document)
        self.assertEqual(result["stage"], "completed")
        report = flow.read(self.state / "completion.json")
        self.assertEqual(len(report["hostReceipts"]), 2)
        for bound in report["hostReceipts"]:
            flow.check_binding(bound)
        self.assertEqual(set(report["canonicalCommands"]), {"omp", "claude"})
        self.assertIn(str(self.cwd), report["protectedRoots"])
        self.assertIn(str(self.base / "external-brain"), report["protectedRoots"])
        self.assertEqual(flow.read(self.state / "workflow.json")["stage"], "completed")

    def test_cleanup_refuses_before_both_phases_complete(self):
        with mock.patch.object(flow, "run_private") as runner:
            with self.assertRaisesRegex(RuntimeError, "only after both phases"):
                flow.cleanup_old(self.state, self.value)
            runner.assert_not_called()

    def test_cleanup_rejects_changed_completion_or_host_receipt(self):
        completion = self.prepare_cleanup_fixture()
        original = completion.read_bytes()
        completion.write_text("changed acceptance")
        with mock.patch.object(flow, "run_private") as runner:
            with self.assertRaisesRegex(RuntimeError, "changed"):
                flow.cleanup_old(self.state, self.value)
            runner.assert_not_called()
            completion.write_bytes(original)
            self.receipt.write_text("changed host receipt")
            with self.assertRaisesRegex(RuntimeError, "does not bind"):
                flow.cleanup_old(self.state, self.value)
            runner.assert_not_called()

    def test_cleanup_passes_exact_two_bound_receipts_without_changing_completion(self):
        completion = self.prepare_cleanup_fixture()
        original = completion.read_bytes()
        original_binding = dict(self.value["completion"])
        with mock.patch.object(flow, "run_private", return_value={"passed": True, "exitCode": 0}) as runner:
            result = flow.cleanup_old(self.state, self.value)
        self.assertTrue(result["passed"])
        self.assertEqual(result["status"], "completed")
        calls = runner.call_args_list
        self.assertEqual(len(calls), 2)
        receipts = flow.read(completion)["hostReceipts"]
        for index, call in enumerate(calls):
            argv = call.args[2]
            self.assertEqual(argv[1:3], [str(self.root / "scripts/cleanup-retired.py"), "apply"])
            self.assertEqual(argv[argv.index("--host-receipt") + 1], receipts[index]["path"])
            self.assertEqual(argv[argv.index("--host-receipt-sha256") + 1], receipts[index]["sha256"])
            self.assertEqual(argv[argv.index("--completion") + 1], str(completion))
            self.assertEqual(argv[argv.index("--completion-sha256") + 1], original_binding["sha256"])
            self.assertEqual(argv[argv.index("--host-state") + 1], str(self.state / ("phase" + str(index + 1) + "-host")))
            self.assertEqual(argv[argv.index("--mode") + 1], "system")
            self.assertEqual(argv[argv.index("--state") + 1], str(self.state / "final-cleanup"))
        self.assertEqual(completion.read_bytes(), original)
        self.assertEqual(self.value["completion"], original_binding)
        flow.check_binding(self.value["completion"])

    def test_cleanup_failure_retains_acceptance_and_can_resume(self):
        completion = self.prepare_cleanup_fixture()
        original = completion.read_bytes()
        outcomes = [{"passed": True, "exitCode": 0}, {"passed": False, "exitCode": 2}]
        with mock.patch.object(flow, "run_private", side_effect=outcomes):
            with self.assertRaisesRegex(RuntimeError, "cleanup is blocked"):
                flow.cleanup_old(self.state, self.value)
        saved = flow.read(self.state / "workflow.json")
        self.assertEqual(saved["stage"], "completed")
        self.assertFalse(saved["cleanup"]["passed"])
        self.assertEqual(len(saved["cleanup"]["runs"]), 2)
        self.assertEqual(completion.read_bytes(), original)
        with mock.patch.object(flow, "run_private", return_value={"passed": True, "exitCode": 0}) as runner:
            resumed = flow.cleanup_old(self.state, saved)
        self.assertEqual(runner.call_count, 2)
        self.assertTrue(resumed["passed"])
        self.assertEqual(completion.read_bytes(), original)

    def test_main_complete_stack_automatically_runs_cleanup_after_completion(self):
        events = []

        def completed(state, value, evidence):
            events.append("completion")
            value["stage"] = "completed"
            return {"stage": "completed", "passed": True}

        def cleaned(state, value):
            self.assertEqual(value["stage"], "completed")
            events.append("cleanup")
            return {"passed": True, "status": "completed"}

        output = io.StringIO()
        with mock.patch.object(flow, "complete_stack", side_effect=completed) as complete, \
             mock.patch.object(flow, "cleanup_old", side_effect=cleaned) as cleanup, \
             mock.patch("sys.stdout", output):
            self.assertEqual(flow.main(["complete-stack", "--state", str(self.state),
                                        "--evidence", str(self.base / "acceptance.json")]), 0)
        self.assertEqual(events, ["completion", "cleanup"])
        complete.assert_called_once()
        cleanup.assert_called_once()
        self.assertTrue(json.loads(output.getvalue())["cleanup"]["passed"])

    def test_main_cleanup_old_retries_without_repeating_completion(self):
        self.prepare_cleanup_fixture()
        output = io.StringIO()
        with mock.patch.object(flow, "complete_stack") as complete, \
             mock.patch.object(flow, "cleanup_old", return_value={"passed": True}) as cleanup, \
             mock.patch("sys.stdout", output):
            self.assertEqual(flow.main(["cleanup-old", "--state", str(self.state)]), 0)
        complete.assert_not_called()
        cleanup.assert_called_once()
        self.assertTrue(json.loads(output.getvalue())["cleanup"]["passed"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process-group fixture")
    def test_timeout_terminates_child_even_when_parent_exits_on_term(self):
        pidfile = self.base / "timeout-child.pid"
        child_code = ("import os,signal,time,pathlib;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                      "pathlib.Path(" + repr(str(pidfile)) + ").write_text(str(os.getpid()));time.sleep(60)")
        parent = self.base / "timeout-parent.py"
        parent.write_text("import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c'," + repr(child_code) + "])\ntime.sleep(60)\n")
        child_pid = None
        try:
            result = flow.run_private(self.state, "timeout-fixture", [str(Path(sys.executable).resolve()), str(parent)],
                                      cwd=str(self.cwd), timeout=1)
            self.assertEqual(result["exitCode"], 124)
            self.assertFalse(result["passed"])
            self.assertTrue(pidfile.exists(), "Child fixture did not start before its timeout")
            child_pid = int(pidfile.read_text())
            deadline = time.monotonic() + 1
            alive = True
            while time.monotonic() < deadline:
                status = Path("/proc") / str(child_pid) / "stat"
                try:
                    alive = status.read_text().split(") ", 1)[1].split()[0] != "Z"
                except FileNotFoundError:
                    alive = False
                if not alive:
                    break
                time.sleep(0.02)
            self.assertFalse(alive, "Timed-out probe left a SIGTERM-ignoring child running")
        finally:
            if child_pid is None and pidfile.exists():
                child_pid = int(pidfile.read_text())
            if child_pid is not None:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    unittest.main()
