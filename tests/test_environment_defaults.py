"""Check catalog defaults preserve private Go routes in probes and generated launchers."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get("AGENTIC_TEST_BASE_KIT", str(HERE)))
spec = importlib.util.spec_from_file_location("environment_default_hostctl", BASE / "scripts/hostctl.py")
hostctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hostctl)


class EnvironmentDefaultTests(unittest.TestCase):
    def test_private_go_routes_survive_and_absent_values_get_offline_defaults(self):
        with tempfile.TemporaryDirectory(prefix="environment-default-tests-", dir=os.environ.get("AGENTIC_TEST_TMPDIR")) as temporary:
            root = Path(temporary)
            prefix = root / "host"
            physical = prefix / "opt/agentic-stack/tools/demo/1"
            (physical / "bin").mkdir(parents=True)
            executable = physical / "bin/demo"
            executable.write_text('#!/bin/sh\nprintf "%s|%s|%s\\n" "$GOPROXY" "$GOSUMDB" "$GOTOOLCHAIN"\n')
            executable.chmod(0o755)
            args = argparse.Namespace(prefix=str(prefix), operator_home="/home/fixture-operator", operator_uid=None,
                                      operator_gid=None, state=str(root / "state"), mode="system")
            host = hostctl.Host(args)
            tool = {"catalog": {"environmentDefaults": {"GOPROXY": "off", "GOSUMDB": "off", "GOTOOLCHAIN": "local"}},
                    "choice": {}, "commands": {"demo": {"path": "bin/demo"}}}
            launcher = root / "launcher"
            launcher.write_text(host.launcher(tool, {"reuse": False, "installPath": "/opt/agentic-stack/tools/demo/1"}, "demo"))
            launcher.chmod(0o755)
            for supplied, expected in (({}, ("off", "off", "local")),
                    ({"GOPROXY": "https://go.private.invalid", "GOSUMDB": "sum.private.invalid", "GOTOOLCHAIN": "private-setting"},
                     ("https://go.private.invalid", "sum.private.invalid", "private-setting")),
                    ({"GOPROXY": "", "GOSUMDB": "", "GOTOOLCHAIN": ""}, ("", "", ""))):
                environment = os.environ.copy()
                for name in ("GOPROXY", "GOSUMDB", "GOTOOLCHAIN"):
                    environment.pop(name, None)
                environment.update(supplied)
                with self.subTest(supplied=supplied), patch.dict(os.environ, environment, clear=True):
                    probe_environment = host.tool_env(tool, physical)
                    self.assertEqual(tuple(probe_environment[key] for key in ("GOPROXY", "GOSUMDB", "GOTOOLCHAIN")), expected)
                    result = subprocess.run([str(launcher)], env=environment, capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout.strip(), "|".join(expected))


if __name__ == "__main__":
    unittest.main()
