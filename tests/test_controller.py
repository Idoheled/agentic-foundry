#!/usr/bin/env python3
"""Focused controller contract tests; no real model, daemon or public network."""
import argparse
import importlib.util
import io
import json
import os
import pathlib
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("controller", pathlib.Path(__file__).resolve().parents[1] / "scripts/agenticctl.py")
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)

class ControllerContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.site = self.root / "site.json"
        self.conf = c.default_config()
        self.conf["model"].update({"id": "test-local", "smallModelId": "test-small", "apiKeyEnv": "TEST_INTERNAL_KEY"})
        self.site.write_text(json.dumps(self.conf))
        self.args = argparse.Namespace(state=str(self.root / "state"), config=str(self.site), docker_host=None)
        self.env = patch.dict(os.environ, {"TEST_INTERNAL_KEY": "synthetic-test-value"})
        self.env.start()
    def tearDown(self):
        self.env.stop(); self.tmp.cleanup()
    def configure(self):
        c.write_runtime_config(self.args, True)
        return pathlib.Path(self.args.state)
    def test_backup_uses_selected_internal_docker_client(self):
        self.configure()
        selected = self.root / "internal-docker"
        selected.write_text("fixture")
        with patch.object(c, "selected_host_tool", return_value=selected), \
             patch.object(c, "container_id", return_value="fixture-db"), \
             patch.object(c, "compose", return_value=subprocess.CompletedProcess([], 0, "", "")), \
             patch.object(c.subprocess, "run") as run:
            c.backup(self.args)
        self.assertEqual(run.call_args.args[0][0], str(selected))
        self.assertTrue(any("pg_dump" in value for value in run.call_args.args[0]))
    def test_private_loopback_configuration_and_no_pulls(self):
        state = self.configure(); compose = c.read_json(state / "compose.json")
        env = (state / "runtime.env").read_text()
        self.assertIn("HOST=127.0.0.1\n", env)
        self.assertIn("PAPERCLIP_BIND=loopback\n", env)
        self.assertIn("PAPERCLIP_OMP_OFFLINE_MODELS=", env)
        self.assertIn("PAPERCLIP_OPENCODE_SMALL_MODEL=internal/test-small", env)
        for service in compose["services"].values():
            self.assertEqual(service["pull_policy"], "never")
            self.assertEqual(service["network_mode"], "host")
        self.assertIn("listen_addresses=127.0.0.1", compose["services"]["db"]["command"])
        self.assertEqual(stat.S_IMODE((state / "runtime.env").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((state / "model-secret.json").stat().st_mode), 0o600)
        self.assertNotIn("synthetic-test-value", (state / "site.json").read_text())
    def test_missing_model_secret_fails(self):
        with patch.dict(os.environ, {"TEST_INTERNAL_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "Export TEST_INTERNAL_KEY"):
                c.write_runtime_config(self.args, True)
    def test_reconfiguration_invalidates_old_model_evidence(self):
        state = self.configure()
        c.write_json(state / "reports/model-smoke.json", {"passed": True})
        c.write_runtime_config(self.args, True)
        self.assertFalse((state / "reports/model-smoke.json").exists())
    def test_smoke_cannot_pass_from_echoed_prompt(self):
        state = self.configure()
        results = [subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, '{"type":"log","message":"INTERNAL_MODEL_OK"}\n', "")]
        with patch.object(c, "exec_worker", side_effect=results):
            with self.assertRaisesRegex(RuntimeError, "smoke failed"): c.model_smoke(self.args)
        self.assertFalse(c.read_json(state / "reports/model-smoke.json")["passed"])
    def test_smoke_accepts_only_actual_assistant_text(self):
        state = self.configure()
        results = [subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, '{"type":"text","part":{"text":"INTERNAL_MODEL_OK"}}\n', "")]
        with patch.object(c, "exec_worker", side_effect=results) as mocked:
            c.model_smoke(self.args)
            self.assertEqual(json.loads(mocked.call_args.kwargs["extra_env"]["OPENCODE_CONFIG_CONTENT"])["permission"], "deny")
        self.assertEqual(c.read_json(state / "reports/model-smoke.json")["fingerprint"], c.model_fingerprint(self.args))
    def test_seed_never_enables_task_wakes(self):
        state = self.configure()
        c.write_json(state / "reports/model-smoke.json", {"passed": True, "fingerprint": c.model_fingerprint(self.args)})
        calls = []
        def fake_api(args, method, path, body=None):
            calls.append((method, path, body))
            if method == "GET": return []
            if path == "/companies": return {"id": "company", "name": self.conf["company"]}
            if path.endswith("/agents"): return {"id": str(len(calls)), **body}
            return {"ok": True}
        with patch.object(c, "api", side_effect=fake_api), patch.object(c, "import_projects"):
            c.seed(self.args)
        agents = [body for method, path, body in calls if method == "POST" and path.endswith("/agents")]
        self.assertEqual(len(agents), 4)
        for agent in agents:
            self.assertEqual(agent["runner"], "legacy")
            self.assertEqual(agent["runtimeConfig"]["heartbeat"], {"enabled": False, "intervalSec": 0, "wakeOnDemand": False, "maxConcurrentRuns": 1})
    def test_archive_traversal_is_rejected(self):
        archive = self.root / "malicious.tar"
        with tarfile.open(archive, "w") as t:
            member = tarfile.TarInfo("../escaped"); member.size = 3; t.addfile(member, io.BytesIO(b"bad"))
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            c.safe_extract(archive, self.root / "destination")
        self.assertFalse((self.root / "escaped").exists())
    def test_unrelated_state_directory_is_preserved(self):
        state = pathlib.Path(self.args.state); state.mkdir(); (state / "existing-work").write_text("keep")
        with self.assertRaisesRegex(RuntimeError, "not empty"): c.make_state(self.args)
        self.assertEqual((state / "existing-work").read_text(), "keep")
    def test_protocol_selection_is_explicit(self):
        self.conf["model"]["api"] = "anthropic-messages"; self.site.write_text(json.dumps(self.conf))
        state = self.configure()
        self.assertEqual(c.read_json(state / "home/agentic-config/opencode.json")["provider"]["internal"]["npm"], "@ai-sdk/anthropic")
        self.assertEqual(c.read_json(state / "home/agentic-config/omp/models.yml")["providers"]["internal"]["api"], "anthropic-messages")

if __name__ == "__main__": unittest.main(verbosity=2)
