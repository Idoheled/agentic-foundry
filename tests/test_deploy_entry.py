import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


DEPLOY = Path(__file__).resolve().parents[1] / "deploy.sh"
BOOTSTRAP_SHA = "6a9e62dad033790aef722dbd370e0ce76ce17b73627ba3ae679f537049350b39"


class DeployEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="foundry-entry-test-")
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        shutil.copyfile(DEPLOY, self.root / "deploy.sh")
        logger = self.root / "logger.py"
        logger.write_text("import json,os,sys\nfrom pathlib import Path\np=Path(os.environ['FOUNDRY_TEST_LOG'])\nwith p.open('a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n")
        for name, kind in (("setup.sh", "setup"), ("scripts/python.sh", "python")):
            script = self.root / name
            script.write_text("#!/bin/bash\n" + sys.executable + " " + str(logger) + " " + kind + ' "$@"\n')
            script.chmod(0o755)
        self.env = dict(os.environ, FOUNDRY_TEST_LOG=str(self.root / "calls.jsonl"))
        self.env.pop("AGENTIC_PYTHON", None)
        self.env.pop("AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON", None)

    def tearDown(self):
        self.temp.cleanup()

    def calls(self):
        path = self.root / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def run_entry(self, *args):
        return subprocess.run(["/bin/bash", str(self.root / "deploy.sh"), *args], env=self.env, text=True, capture_output=True)

    def no_python_path(self):
        path = self.root / "minimal-bin"; path.mkdir()
        for name in ("dirname", "uname", "mkdir", "mktemp", "cat", "sha256sum", "chmod", "ln", "rm"):
            (path / name).symlink_to(shutil.which(name))
        self.env["PATH"] = str(path)

    def test_help_does_not_hydrate_or_install(self):
        result = self.run_entry("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Git-checkout deployment", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_doctor_skips_hydration(self):
        result = self.run_entry("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [["setup", "doctor"]])

    def test_agent_hydrates_then_preserves_argv(self):
        result = self.run_entry("agent", "--state", "/private/state with spaces")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(calls[0], ["python", str(self.root / "scripts/refresh-checksums.py"), "--check", "--root", str(self.root)])
        self.assertEqual(calls[1], ["python", str(self.root / "scripts/offline_payload.py"), "hydrate", "--root", str(self.root), "--link-objects"])
        self.assertEqual(calls[2], ["setup", "agent", "--state", "/private/state with spaces"])

    def test_failed_hydration_does_not_start_setup(self):
        (self.root / "scripts/python.sh").write_text("#!/bin/bash\ncase \"$1\" in *offline_payload.py) exit 2;; esac\nexit 0\n")
        result = self.run_entry("agent")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_no_python_requires_factual_private_source_reason(self):
        self.no_python_path()
        result = self.run_entry("agent")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Inspect private repositories", result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.root / "payload").exists())

    def test_no_python_stages_only_verified_controller_object(self):
        self.no_python_path()
        body = b"fixture controller archive"; sha = hashlib.sha256(body).hexdigest()
        deploy = self.root / "deploy.sh"
        deploy.write_text(deploy.read_text().replace(BOOTSTRAP_SHA, sha))
        obj = self.root / "offline/objects/sha256" / (sha + ".chunk")
        obj.parent.mkdir(parents=True); obj.write_bytes(body)
        self.env["AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON"] = "Fixture private repository has no qualified Python"
        result = self.run_entry("agent")
        self.assertEqual(result.returncode, 0, result.stderr)
        archives = list((self.root / "payload/packages").iterdir())
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_bytes(), body)
        self.assertEqual(self.calls()[-1], ["setup", "agent"])

    def test_tampered_controller_object_is_not_executed(self):
        self.no_python_path()
        body = b"fixture controller archive"; sha = hashlib.sha256(body).hexdigest()
        deploy = self.root / "deploy.sh"
        deploy.write_text(deploy.read_text().replace(BOOTSTRAP_SHA, sha))
        obj = self.root / "offline/objects/sha256" / (sha + ".chunk")
        obj.parent.mkdir(parents=True); obj.write_bytes(b"tampered")
        self.env["AGENTIC_BOOTSTRAP_PYTHON_FALLBACK_REASON"] = "Fixture private repository has no qualified Python"
        result = self.run_entry("agent")
        self.assertEqual(result.returncode, 2)
        self.assertIn("pinned hash", result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertEqual(list((self.root / "payload/packages").iterdir()), [])

    def test_stale_source_stops_before_hydration(self):
        (self.root / "scripts/python.sh").write_text("#!/bin/bash\nexit 2\n")
        result = self.run_entry("agent")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
