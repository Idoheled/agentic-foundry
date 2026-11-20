import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/agentic-bench.py"


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Benchmark fixture")
        (self.repo / "answer.txt").write_text("wrong\n")
        self.git("add", "answer.txt")
        self.git("commit", "-qm", "fixed fixture")
        self.revision = self.git("rev-parse", "HEAD").strip()
        self.candidate = self.root / "candidate.py"
        self.candidate.write_text("from pathlib import Path\nPath('answer.txt').write_text('correct\\n')\n")
        self.check = self.root / "check.py"
        self.check.write_text("from pathlib import Path\nassert Path('answer.txt').read_text() == 'correct\\n'\n")
        self.plan = {"schemaVersion": 1, "repository": str(self.repo), "revision": self.revision,
                     "routingEvidence": "Controlled local fixture; no network or model calls",
                     "isolationAcknowledgment": "git-worktrees-are-not-an-os-sandbox",
                     "agents": [{"id": "fixture", "argv": [sys.executable, str(self.candidate)], "timeoutSeconds": 10}],
                     "tasks": [{"id": "repair", "prompt": "Repair answer.txt", "checks": [
                         {"argv": [sys.executable, str(self.check)], "timeoutSeconds": 10}]}]}
        self.plan_path = self.root / "plan.json"
        self.state = self.root / "state"

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def run_bench(self, action="run"):
        self.plan_path.write_text(json.dumps(self.plan))
        return subprocess.run([sys.executable, str(SCRIPT), action, "--plan", str(self.plan_path),
                               "--state", str(self.state)], capture_output=True, text=True, timeout=25)

    def result(self):
        return json.loads(next(self.state.glob("run-*/*/result.json")).read_text())

    def test_real_candidate_and_checker_do_not_change_original(self):
        (self.repo / "unrelated.txt").write_text("preserve\n")
        result = self.run_bench()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.result()["passed"])
        self.assertEqual((self.repo / "answer.txt").read_text(), "wrong\n")
        self.assertEqual((self.repo / "unrelated.txt").read_text(), "preserve\n")
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.revision)
        self.assertIn("correct", Path(self.result()["diff"]["path"]).read_text())

    def test_exit_zero_does_not_pass_failed_acceptance(self):
        self.candidate.write_text("print('all done')\n")
        result = self.run_bench()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.result()["passed"])
        self.assertTrue(self.result()["agentExecution"]["passed"])
        self.assertFalse(self.result()["checks"][0]["passed"])

    def test_checker_tamper_blocks_acceptance(self):
        self.candidate.write_text("from pathlib import Path\nPath(" + repr(str(self.check)) + ").write_text('pass\\n')\n")
        result = self.run_bench()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.result()["passed"])
        self.assertIn("inputs changed", self.result()["error"])

    def test_timeout_is_recorded_failure(self):
        self.candidate.write_text("import time\ntime.sleep(30)\n")
        self.plan["agents"][0]["timeoutSeconds"] = 1
        result = self.run_bench()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(self.result()["agentExecution"]["timedOut"])

    def test_plan_is_read_only_and_requires_fixed_commit(self):
        result = self.run_bench("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.state.exists())
        self.plan["revision"] = "HEAD"
        result = self.run_bench()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.state.exists())

    def test_existing_nonbenchmark_state_is_preserved(self):
        self.state.mkdir()
        marker = self.state / "precious.txt"
        marker.write_text("keep")
        result = self.run_bench()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(marker.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
