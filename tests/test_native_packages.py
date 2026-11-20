"""Scoped native-helper contracts; every APT/package operation is mocked."""
import copy
import importlib.util
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/native-packages.py"
spec = importlib.util.spec_from_file_location("native_helper", SCRIPT)
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


class NativePackageContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.state = self.root / "private-state"
        self.plan_path = self.root / "site-native.json"
        self.keyring = self.root / "internal.gpg"
        self.keyring.write_bytes(b"synthetic keyring; no signature operation is performed")
        self.actual = {"id": "debian", "versionID": "13", "architecture": "x86_64"}
        self.plan = {"schemaVersion": 1, "expectedOS": dict(self.actual),
            "privateRepositoriesChecked": ["Synthetic internal repository inspection result"],
            "source": "internal", "evidence": "Synthetic scoped contract fixture, not real package approval",
            "approvedInternalHosts": ["apt.internal:8443"],
            "repositories": [{"uri": "https://apt.internal:8443/debian", "suite": "trixie", "components": ["main"], "signedBy": str(self.keyring)}],
            "packages": ["tmux", "ninja-build=1.12.1-1"],
            "hostRecoveryEvidence": "Synthetic host snapshot fixture with a documented restoration command; no real package transaction"}
        self.calls = []
        self.sources = []
        self.uri_output = "'https://apt.internal:8443/debian/pool/tmux.deb' tmux.deb 100 SHA256:fixture\n"
        self.dpkg_output = "tmux\t3.5\tinstalled\nninja-build\t1.12.1-1\tinstalled\n"

    def write_plan(self):
        self.plan_path.write_text(json.dumps(self.plan))

    def fake_run(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.assertNotIn("shell", kwargs)
        if argv[0] == "apt-get":
            source = next(x.split("=", 1)[1] for x in argv if x.startswith("Dir::Etc::sourcelist="))
            parts = next(x.split("=", 1)[1] for x in argv if x.startswith("Dir::Etc::sourceparts="))
            self.assertTrue(pathlib.Path(source).is_relative_to(self.state))
            self.assertTrue(pathlib.Path(parts).is_relative_to(self.state))
            self.assertFalse(any(pathlib.Path(parts).iterdir()))
            self.sources.append(pathlib.Path(source).read_text())
            self.assertIn("Acquire::http::AllowRedirect=false", argv)
            self.assertIn("Acquire::https::AllowRedirect=false", argv)
            if "--simulate" in argv:
                return subprocess.CompletedProcess(argv, 0, "Inst tmux (3.5 fixture)\nInst ninja-build (1.12.1-1 fixture)\n", "")
            if "--print-uris" in argv:
                return subprocess.CompletedProcess(argv, 0, self.uri_output, "")
            return subprocess.CompletedProcess(argv, 0, "", "")
        self.assertEqual(argv[0], "dpkg-query")
        return subprocess.CompletedProcess(argv, 0, self.dpkg_output, "")

    def invoke(self, command="plan", state=None):
        self.write_plan()
        argv = [str(SCRIPT), command, "--plan", str(self.plan_path), "--state", str(state or self.state)]
        if command == "apply":
            argv += ["--operator-uid", str(os.getuid()), "--operator-gid", str(os.getgid())]
        with patch.object(sys, "argv", argv), patch.object(n, "system_info", return_value=self.actual), \
                patch.object(n.shutil, "which", side_effect=lambda name: "/fixture/" + name), \
                patch.object(n.subprocess, "run", side_effect=self.fake_run), \
                patch.object(n.os, "geteuid", return_value=0 if command == "apply" else os.getuid()), \
                patch.dict(os.environ, {"SUDO_UID": str(os.getuid()), "SUDO_GID": str(os.getgid())}):
            n.main()

    def test_strict_declared_os_architecture_and_supported_profiles(self):
        mismatch = dict(self.actual, versionID="12")
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            n.validate(self.plan, mismatch)
        for actual, source in [(dict(self.actual, architecture="aarch64"), "internal"),
                               (dict(self.actual, id="fedora", versionID="43"), "internal"),
                               (dict(self.actual, versionID="12"), "kit"),
                               (dict(self.actual, id="ubuntu", versionID="24.04"), "kit")]:
            with self.subTest(actual=actual, source=source):
                plan = copy.deepcopy(self.plan)
                plan.update(expectedOS=actual, source=source, fallbackReason="unavailable")
                with self.assertRaises(RuntimeError):
                    n.validate(plan, actual)

    def test_source_evidence_fallback_and_explicit_package_names(self):
        for update in ({"privateRepositoriesChecked": []}, {"evidence": "REPLACE_WITH_EVIDENCE"},
                       {"source": "kit"}, {"packages": ["--allow-unauthenticated"]},
                       {"packages": ["/tmp/tool.deb"]}, {"packages": ["tmux;echo bad"]}):
            with self.subTest(update=update):
                plan = copy.deepcopy(self.plan)
                plan.update(update)
                with self.assertRaises(RuntimeError):
                    n.validate(plan, self.actual)
        plan = copy.deepcopy(self.plan)
        plan["packages"] = ["libstdc++6:amd64=14.2.0-1", "python3-venv", "libssl-dev"]
        n.validate(plan, self.actual)

    def test_internal_repository_allowlist_rejects_source_injection_and_public_uris(self):
        for uri in ("http://apt.internal:8443/debian", "https://outside.example/debian",
                    "https://user:secret@apt.internal:8443/debian",
                    "https://apt.internal:8443/debian trixie main\ndeb [trusted=yes] https://outside.example/debian",
                    "https://apt.internal:8443/debian\t", "https://apt.internal:8443/debian?token=secret"):
            with self.subTest(uri=uri):
                plan = copy.deepcopy(self.plan)
                plan["repositories"][0]["uri"] = uri
                with self.assertRaises(RuntimeError):
                    n.validate(plan, self.actual)
        plan = copy.deepcopy(self.plan)
        plan["approvedInternalHosts"] = ["deb.debian.org"]
        plan["repositories"][0]["uri"] = "https://deb.debian.org/debian"
        with self.assertRaises(RuntimeError):
            n.validate(plan, self.actual)
        plan = copy.deepcopy(self.plan)
        plan["repositories"][0]["components"] = "main"
        with self.assertRaises(RuntimeError):
            n.validate(plan, self.actual)

    def test_plan_scopes_sources_and_cache_without_package_transaction(self):
        self.invoke()
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(all(argv[0] == "apt-get" for argv in self.calls))
        self.assertEqual(self.sources[0], "deb [arch=amd64 signed-by=" + str(self.keyring) + "] https://apt.internal:8443/debian trixie main\n")
        for argv in self.calls[1:]:
            self.assertIn("--no-remove", argv)
            self.assertIn("--no-install-recommends", argv)
        report = n.read(self.state / "plan.json")
        self.assertFalse(report["applied"])
        self.assertFalse(report["globalSourcesModified"])

    def test_apply_requires_nonplaceholder_recovery_before_package_operations(self):
        for value in (None, "", "   ", "REPLACE_WITH_RECOVERY", {"todo": "create backup"}):
            with self.subTest(value=value):
                self.plan["hostRecoveryEvidence"] = value
                with self.assertRaisesRegex(RuntimeError, "hostRecoveryEvidence"):
                    self.invoke("apply")
                self.assertFalse(self.calls)

    def test_mocked_apply_uses_no_remove_and_private_owned_receipt(self):
        self.invoke("apply")
        self.assertEqual(len(self.calls), 5)
        install = self.calls[-2]
        self.assertEqual(install[0], "apt-get")
        self.assertIn("--yes", install)
        self.assertIn("--no-remove", install)
        self.assertIn("Dpkg::Options::=--force-confold", install)
        self.assertEqual(install[-2:], self.plan["packages"])
        self.assertEqual(self.calls[-1][-2:], ["tmux", "ninja-build"])
        report_path = self.state / "installed.json"
        self.assertTrue(n.read(report_path)["applied"])
        self.assertEqual(report_path.stat().st_uid, os.getuid())
        self.assertEqual(stat.S_IMODE(report_path.stat().st_mode), 0o600)

    def test_resolved_public_download_blocks_transaction_and_keeps_failure_log(self):
        self.uri_output = "'https://outside.example/tmux.deb' tmux.deb 100 SHA256:fixture\n"
        with self.assertRaisesRegex(RuntimeError, "outside the approved"):
            self.invoke("apply")
        self.assertEqual(len(self.calls), 3)
        self.assertFalse((self.state / "installed.json").exists())
        self.assertTrue((self.state / "last-operation.log").exists())

    def test_package_postcheck_cannot_mark_uninstalled_package_as_applied(self):
        self.dpkg_output = "tmux\t3.5\tconfig-files\nninja-build\t1.12.1-1\tinstalled\n"
        with self.assertRaisesRegex(RuntimeError, "postcheck"):
            self.invoke("apply")
        self.assertFalse((self.state / "installed.json").exists())

    def test_state_symlinks_and_unrelated_directories_are_preserved(self):
        unrelated = self.root / "existing-directory"
        unrelated.mkdir()
        keep = unrelated / "keep"
        keep.write_text("existing work")
        original_mode = stat.S_IMODE(unrelated.stat().st_mode)
        with self.assertRaisesRegex(RuntimeError, "unrelated nonempty"):
            self.invoke("plan", unrelated)
        self.assertEqual(keep.read_text(), "existing work")
        self.assertEqual(stat.S_IMODE(unrelated.stat().st_mode), original_mode)
        link = self.root / "state-link"
        link.symlink_to(unrelated, target_is_directory=True)
        for candidate in (link, link / "nested"):
            with self.subTest(path=candidate), self.assertRaisesRegex(RuntimeError, "symlinks"):
                n.state_path(str(candidate))
        self.assertFalse(self.calls)

    def test_output_symlink_is_preserved_and_tiny_kit_checksum_failure_blocks_apt(self):
        victim = self.root / "unrelated-config"
        victim.write_text("keep")
        output = self.root / "output.json"
        output.symlink_to(victim)
        with self.assertRaisesRegex(RuntimeError, "existing native output"):
            with n.private_output(output, os.getuid(), os.getgid()) as stream:
                stream.write("overwrite")
        self.assertEqual(victim.read_text(), "keep")
        fake_kit = self.root / "tiny-kit"
        repo = fake_kit / "payload/packages/debian13-amd64"
        repo.mkdir(parents=True)
        (fake_kit / "provenance").mkdir()
        (repo / "tmux.deb").write_bytes(b"tiny changed fixture; not a real DEB")
        (repo / "Packages").write_text("synthetic index")
        inventory = {"packages": [{"filename": "tmux.deb", "package": "tmux", "sha256": "0" * 64}],
                     "packagesIndexSha256": n.sha(repo / "Packages")}
        (fake_kit / "provenance/r3-native-packages.json").write_text(json.dumps(inventory))
        self.plan.update(source="kit", fallbackReason="unavailable")
        with patch.object(n, "ROOT", fake_kit), self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            self.invoke("plan")
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
