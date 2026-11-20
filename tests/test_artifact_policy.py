#!/usr/bin/env python3
"""Private-source and preservation contracts, using tiny local fixtures only."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

KIT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("artifact_controller", KIT / "scripts/agenticctl.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
policy_module = sys.modules[c.ArtifactPolicy.__module__]


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ArtifactSourceContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name)
        self.kit = self.base / "kit"
        self.internal = self.base / "internal"
        self.internal.mkdir()
        (self.kit / "provenance").mkdir(parents=True)
        (self.kit / "payload/manifests").mkdir(parents=True)
        self.state = self.base / "state"
        for part in ("tools", "runtime/bin", "runtime/adapters", "reports", "backups"):
            (self.state / part).mkdir(parents=True, exist_ok=True)
        self.lock = {"paperclip": {"configDigest": "sha256:" + "a" * 64},
                     "postgres": {"configDigest": "sha256:" + "b" * 64}}
        (self.kit / "provenance/image-lock.json").write_text(json.dumps(self.lock))
        self.plan = {"schemaVersion": 1,
                     "privateRepositoriesChecked": ["Fixture internal repository inspected; all required artifacts available"],
                     "approvedInternalRegistries": ["registry.internal:5443"], "files": {}, "images": {}}
        self.opencode = b"#!/bin/sh\nprintf 'fixture opencode\\n'\n"
        bodies = {
            "docker": self.archive({"docker/docker": b"#!/bin/sh\nexit 0\n"}),
            "compose": b"#!/bin/sh\nprintf 'fixture compose\\n'\n",
            "omp": b"#!/bin/sh\nprintf 'fixture omp\\n'\n",
            "herdr": b"#!/bin/sh\nprintf 'fixture herdr\\n'\n",
            "opencode": self.archive({"opencode": self.opencode}),
            "ompAdapter": self.archive({"package.json": b"{}", "dist/server/index.js": b"export {};\n"})}
        sums = []
        for name, data in bodies.items():
            path = self.internal / (name + ".staged")
            path.write_bytes(data)
            path.chmod(0o755)
            relative, fmt = policy_module.FILES[name]
            sums.append(sha(data) + "  " + relative)
            self.plan["files"][name] = {"source": "internal", "path": str(path), "sha256": sha(data),
                                         "format": fmt, "evidence": "Verified internal fixture matching the baseline"}
        (self.kit / "SHA256SUMS").write_text("\n".join(sums) + "\n")
        (self.kit / "payload/manifests/worker-artifacts.json").write_text(json.dumps({
            "workers": [{"name": "opencode", "installed_binary": {"sha256": sha(self.opencode)}}]}))
        for index, name in enumerate(self.lock, 1):
            self.plan["images"][name] = {
                "source": "internal", "imageRef": "registry.internal:5443/mirror/" + name + "@sha256:" + str(index) * 64,
                "expectedConfigDigest": self.lock[name]["configDigest"], "evidence": "Verified internal mirror fixture"}
        self.site = self.base / "site.json"
        self.conf = json.loads((KIT / "config/site.example.json").read_text())
        self.conf.pop("artifactPlan", None)
        self.site.write_text(json.dumps(self.conf))
        self.args = argparse.Namespace(state=str(self.state), config=str(self.site), docker_host=None)
        self.root_patch = patch.object(c, "ROOT", self.kit)
        self.payload_patch = patch.object(c, "PAYLOAD", self.kit / "payload")
        self.root_patch.start()
        self.payload_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.payload_patch.stop)

    @staticmethod
    def archive(files):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            for name, data in files.items():
                item = tarfile.TarInfo(name)
                item.size = len(data)
                item.mode = 0o755
                archive.addfile(item, io.BytesIO(data))
        return stream.getvalue()

    def policy(self):
        return c.ArtifactPolicy(self.kit, self.plan)

    def record_selection(self):
        selection = self.policy().resolve()
        c.write_json(self.state / "reports/artifact-selection.json", selection)
        return selection

    def test_internal_and_existing_artifacts_prepare_without_kit_binaries(self):
        self.plan["files"]["omp"]["source"] = "existing"
        # No kit binary/archive files exist: success proves the selected files supply the runtime.
        c.prepare_runtime(self.state, self.policy())
        self.assertEqual((self.state / "runtime/bin/omp-real").read_bytes(),
                         pathlib.Path(self.plan["files"]["omp"]["path"]).read_bytes())
        self.assertEqual((self.state / "runtime/bin/opencode").read_bytes(), self.opencode)
        selected = c.installed_selection(self.args)
        self.assertEqual(selected["files"]["omp"]["source"], "existing")
        self.assertEqual(selected["files"]["compose"]["executionPath"], self.plan["files"]["compose"]["path"])
        self.assertFalse((self.state / "tools/docker-compose").exists())

    def test_source_evidence_and_fallback_reason_are_required(self):
        with patch.dict(self.plan, {"privateRepositoriesChecked": []}):
            with self.assertRaisesRegex(ValueError, "privateRepositoriesChecked"):
                self.policy()
        entry = self.plan["files"]["omp"]
        entry["source"] = "kit"
        with self.assertRaisesRegex(ValueError, "fallbackReason"):
            self.policy().resolve_file("omp")
        entry["fallbackReason"] = "unavailable"
        entry["evidence"] = ""
        with self.assertRaisesRegex(ValueError, "evidence"):
            self.policy().resolve_file("omp")
        entry["evidence"] = "Fixture internal source unavailable after inspection"
        destination = self.kit / policy_module.FILES["omp"][0]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(pathlib.Path(entry["path"]).read_bytes())
        self.assertEqual(self.policy().resolve_file("omp")["source"], "kit")

    def test_host_docker_and_compose_require_hash_bound_capability_evidence(self):
        for name in ("docker", "compose"):
            with self.subTest(name=name):
                path = self.internal / (name + "-host")
                path.write_bytes(("#!/bin/sh\nprintf 'qualified alternate " + name + "\\n'\n").encode())
                path.chmod(0o755)
                identity = sha(path.read_bytes())
                entry = {"source": "existing", "format": "executable", "path": str(path),
                         "sha256": identity, "evidence": "Existing host tool inspected"}
                self.plan["files"][name] = entry
                with self.assertRaisesRegex(ValueError, "qualificationReport"):
                    self.policy().resolve_file(name)
                required = ["version-executes", "local-engine-compatible",
                            "selected-socket-access" if name == "docker" else "compose-config-with-raw-env"]
                report = {"schemaVersion": 1, "artifact": name, "sha256": identity, "passed": True,
                          "checks": [{"name": key, "passed": True, "evidence": "Synthetic contract fixture"} for key in required]}
                report_path = self.internal / (name + "-qualification.json")
                report_path.write_text(json.dumps(report))
                entry["qualificationReport"] = str(report_path)
                self.assertEqual(self.policy().resolve_file(name)["format"], "executable")
                report["checks"][-1]["passed"] = False
                report_path.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, "required checks"):
                    self.policy().resolve_file(name)

    def test_existing_opencode_executable_uses_installed_binary_identity(self):
        path = self.internal / "opencode-installed"
        path.write_bytes(self.opencode)
        path.chmod(0o755)
        self.plan["files"]["opencode"].update(source="existing", format="executable", path=str(path), sha256=sha(self.opencode))
        c.prepare_runtime(self.state, self.policy())
        self.assertEqual((self.state / "runtime/bin/opencode").read_bytes(), self.opencode)
        path.write_bytes(b"different binary")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.policy().resolve_file("opencode")

    def test_internal_images_propagate_to_compose_and_use_only_explicit_pull(self):
        selection = self.record_selection()
        # Config writing is exercised independently of normal state initialization.
        with patch.object(c, "make_state", return_value=self.state):
            c.write_runtime_config(self.args)
        composed = c.read_json(self.state / "compose.json")
        for name, service in (("paperclip", "server"), ("postgres", "db")):
            self.assertEqual(composed["services"][service]["image"], selection["images"][name]["imageRef"])
            self.assertEqual(composed["services"][service]["pull_policy"], "never")
        inspected = set()
        calls = []
        def fake_docker(args, *parts, **kwargs):
            calls.append(parts)
            if parts[:2] == ("image", "inspect"):
                ref = parts[-1]
                if ref not in inspected:
                    inspected.add(ref)
                    return subprocess.CompletedProcess([], 1, "", "")
                name = next(key for key, item in selection["images"].items() if item["imageRef"] == ref)
                return subprocess.CompletedProcess([], 0, self.lock[name]["configDigest"] + "\n", "")
            return subprocess.CompletedProcess([], 0, "", "")
        with patch.object(c, "docker", side_effect=fake_docker):
            c.load_images(self.args)
        pulls = [parts for parts in calls if parts[0] == "pull"]
        self.assertEqual(len(pulls), 2)
        self.assertEqual({parts[-1] for parts in pulls}, {item["imageRef"] for item in selection["images"].values()})
        self.assertFalse(any(parts[0] == "load" for parts in calls))

    def test_image_failures_do_not_select_kit_or_accept_mismatched_content(self):
        self.record_selection()
        with patch.object(c, "docker", side_effect=[subprocess.CompletedProcess([], 1, "", ""),
                                                     subprocess.CalledProcessError(1, ["docker", "pull"])]) as mocked:
            with self.assertRaises(subprocess.CalledProcessError):
                c.load_images(self.args)
            self.assertEqual([call.args[1] for call in mocked.call_args_list], ["image", "pull"])
        with patch.object(c, "docker", return_value=subprocess.CompletedProcess([], 0, "sha256:" + "f" * 64, "")) as mocked:
            with self.assertRaisesRegex(RuntimeError, "unexpected content"):
                c.load_images(self.args)
            self.assertEqual(mocked.call_count, 1)
        self.plan["images"]["paperclip"].update(source="existing", imageRef=self.lock["paperclip"]["configDigest"])
        self.record_selection()
        with patch.object(c, "docker", return_value=subprocess.CompletedProcess([], 1, "", "")) as mocked:
            with self.assertRaisesRegex(RuntimeError, "no silent fallback"):
                c.load_images(self.args)
            self.assertEqual(mocked.call_count, 1)

    def test_public_or_unapproved_image_source_is_rejected(self):
        entry = self.plan["images"]["paperclip"]
        entry["imageRef"] = "ghcr.io/example/image@sha256:" + "1" * 64
        with self.assertRaisesRegex(ValueError, "approvedInternalRegistries"):
            self.policy().resolve_images()
        self.plan["approvedInternalRegistries"].append("ghcr.io")
        with self.assertRaisesRegex(ValueError, "internal registry"):
            self.policy()

    def test_same_size_managed_replacement_keeps_backup_and_preserves_symlinks(self):
        source = self.internal / "candidate"
        destination = self.state / "runtime/bin/candidate"
        source.write_bytes(b"NEW!")
        destination.write_bytes(b"OLD!")
        c.copy_managed_binary(source, destination, self.state)
        self.assertEqual(destination.read_bytes(), b"NEW!")
        records = list((self.state / "backups/runtime-replacements").glob("*/replacement.json"))
        self.assertEqual(len(records), 1)
        record = json.loads(records[0].read_text())
        self.assertEqual(pathlib.Path(record["backup"]).read_bytes(), b"OLD!")
        self.assertEqual(record["beforeSha256"], sha(b"OLD!"))
        outside = self.base / "outside-command"
        outside.write_bytes(b"KEEP")
        destination.unlink()
        destination.symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            c.copy_managed_binary(source, destination, self.state)
        self.assertTrue(destination.is_symlink())
        self.assertEqual(outside.read_bytes(), b"KEEP")

    def test_generated_omp_wrapper_preserves_an_existing_symlink_target(self):
        outside = self.base / "existing-host-launcher"
        outside.write_bytes(b"KEEP THE HOST LAUNCHER\n")
        wrapper = self.state / "runtime/bin/omp"
        wrapper.symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            c.prepare_runtime(self.state, self.policy())
        self.assertTrue(wrapper.is_symlink())
        self.assertEqual(outside.read_bytes(), b"KEEP THE HOST LAUNCHER\n")

    def test_generated_config_writers_preserve_links_and_ignore_old_predictable_temp(self):
        outside = self.base / "existing-external-config"
        original = b"KEEP EXISTING CONFIGURATION\n"
        outside.write_bytes(original)
        for name, writer in (("runtime.env", lambda path: c.private_text(path, "KEY=new\n")),
                             ("generated.json", lambda path: c.write_json(path, {"new": True}))):
            with self.subTest(writer=name):
                destination = self.state / name
                destination.symlink_to(outside)
                with self.assertRaisesRegex(RuntimeError, "symlink"):
                    writer(destination)
                self.assertTrue(destination.is_symlink())
                self.assertEqual(outside.read_bytes(), original)
        destination = self.state / "reports/fresh.json"
        obsolete_temporary = destination.with_name(destination.name + ".tmp")
        obsolete_temporary.symlink_to(outside)
        c.write_json(destination, {"written": True})
        self.assertEqual(json.loads(destination.read_text()), {"written": True})
        self.assertTrue(obsolete_temporary.is_symlink())
        self.assertEqual(outside.read_bytes(), original)

    def test_install_and_configure_require_a_source_plan_before_runtime_changes(self):
        for command in ("install", "configure"):
            with self.subTest(command=command), patch.object(sys, "argv", ["agenticctl", command, "--config", str(self.site), "--state", str(self.state)]), \
                    patch.object(c, "preflight"), patch.object(c, "checksum_verify"), patch.object(c, "prepare_runtime") as prepare:
                with self.assertRaisesRegex(RuntimeError, "artifactPlan"):
                    c.main()
                prepare.assert_not_called()


class BootstrapSelectionContractTests(unittest.TestCase):
    def test_missing_host_python_does_not_use_kit_without_fallback_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            commands = pathlib.Path(temporary)
            (commands / "dirname").symlink_to(shutil.which("dirname"))
            unavailable = commands / "python3"
            unavailable.write_text("#!/bin/sh\nexit 1\n")
            unavailable.chmod(0o755)
            env = os.environ.copy()
            env.pop("AGENTIC_PYTHON", None)
            env.pop("AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON", None)
            env["PATH"] = str(commands)
            result = subprocess.run(["/bin/bash", str(KIT / "scripts/python.sh"), "-c", "raise SystemExit(0)"],
                                    capture_output=True, text=True, env=env, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn("Inspect internal OS/package repositories first", result.stderr)

    def test_explicit_python_wins_and_invalid_selection_does_not_fall_back(self):
        env = os.environ.copy()
        env["AGENTIC_PYTHON"] = sys.executable
        result = subprocess.run(["/bin/bash", str(KIT / "scripts/python.sh"), "-c", "print('SELECTED_PYTHON_OK')"],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "SELECTED_PYTHON_OK")
        env["AGENTIC_PYTHON"] = "/nonexistent/explicit-python"
        result = subprocess.run(["/bin/bash", str(KIT / "scripts/python.sh"), "-c", "raise SystemExit(0)"],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("AGENTIC_PYTHON", result.stderr)

    def test_daemon_bootstrap_requires_plan_before_any_system_action(self):
        result = subprocess.run(["/bin/bash", str(KIT / "scripts/bootstrap-docker.sh")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--artifact-plan is required", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
