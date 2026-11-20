import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("productivity", ROOT / "scripts/productivity.py")
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


class ProductivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prefix = self.root / "host"
        self.payload = self.root / "private-demo"
        self.payload.write_text("#!/bin/sh\nprintf 'delivery-demo 1.0\\n'\n"); self.payload.chmod(0o755)
        self.catalog = self.root / "catalog.json"
        self.catalog.write_text(json.dumps({"schemaVersion": 1, "tools": {"delivery-demo": {
            "version": "1.0", "commands": {"delivery-demo": {"path": "bin/demo", "verifyPattern": "delivery-demo 1.0"}},
            "artifact": {"path": "unused", "sha256": p.digest(self.payload), "format": "file", "destination": "bin/demo"}}}}))
        self.plan = self.root / "plan.json"
        self.value = {"schemaVersion": 1, "mode": "system", "catalog": str(self.catalog), "privateRepositoriesChecked": ["Fixture private mirror inspected"],
                      "tools": {"delivery-demo": {"source": "internal", "path": str(self.payload), "sha256": p.digest(self.payload), "evidence": "Fixture complete executable qualified"}}}
        self.save(); self.state = self.root / "state"

    def save(self):
        self.plan.write_text(json.dumps(self.value))

    def run_command(self, command):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            result = p.main([command, "--plan", str(self.plan), "--state", str(self.state), "--prefix", str(self.prefix)])
        return result, json.loads(stream.getvalue())

    def test_plan_has_no_install_mutation_then_real_apply_verify(self):
        self.assertEqual(self.run_command("plan")[0], 0)
        self.assertFalse(self.state.exists()); self.assertFalse(self.prefix.exists())
        _, installed = self.run_command("apply")
        self.assertEqual(installed["status"], "installed_and_verified")
        self.assertTrue((self.prefix / "usr/local/bin/agentic-delivery-demo").is_file())
        self.assertEqual(self.run_command("verify")[0], 0)

    def test_changed_plan_blocks_bound_verification(self):
        self.run_command("apply")
        self.value["tools"]["delivery-demo"]["evidence"] += " changed"
        self.save()
        with self.assertRaisesRegex(ValueError, "Plan or catalog changed"):
            self.run_command("verify")

    def test_missing_private_inspection_does_not_create_state(self):
        self.value["privateRepositoriesChecked"] = []; self.save()
        with self.assertRaisesRegex(ValueError, "private repositories"):
            self.run_command("apply")
        self.assertFalse(self.state.exists())

    def test_changed_installed_binary_is_not_success(self):
        self.run_command("apply")
        command = self.prefix / "usr/local/bin/agentic-delivery-demo"
        command.write_text("#!/bin/sh\nexit 19\n")
        with self.assertRaisesRegex(ValueError, "provisioner failed"):
            self.run_command("verify")


if __name__ == "__main__":
    unittest.main()
