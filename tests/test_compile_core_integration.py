#!/usr/bin/env python3
"""Compile the actual pinned core/profile recipes; no install, endpoint or Docker access."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get("AGENTIC_TEST_BASE_KIT", str(HERE)))


def load(name):
    spec = importlib.util.spec_from_file_location("core_compile_fixture_" + name.replace("-", "_"), BASE / "scripts" / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", [str(BASE / "scripts"), *sys.path]):
        spec.loader.exec_module(value)
    return value


@unittest.skipUnless((BASE / "scripts/compile-site.py").exists(), "Requires assembled r5 compiler and pinned recipe metadata")
class CompileCoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="compile-core-tests-", dir=os.environ.get("AGENTIC_TEST_TMPDIR"))
        self.root = Path(self.temporary.name)
        self.compiler = load("compile-site")
        self.catalog = json.loads((BASE / "config/host-catalog.json").read_text())
        self.identities = json.loads((BASE / "provenance/r5/host-file-identities.json").read_text())
        self.source = self.root / "site.json"
        self.output = self.root / "compiled"
        self.config = {"schemaVersion": 1, "schemaKind": "minimal", "bootstrapMode": "fresh", "mode": "user",
            "evidence": "Read-only complete core/profile recipe fixture; no installation is requested.",
            "stateRoot": str(self.root / "states"), "canonicalCommands": "none", "reuseExisting": False,
            "privateSupply": {"roots": [], "inspectionEvidence": "This isolated fixture intentionally supplies no private artifacts.",
                "unavailabilityEvidence": "Private supply is absent from the test fixture, not a production finding.",
                "imageRepositoryFinding": "No registry is part of this isolated recipe test; it intentionally resolves the pinned kit images.",
                "allowKitFallback": True},
            "tools": ["codex", "claude", "python", "native-profiles", "node"],
            "model": {"api": "openai-responses", "providerId": "fixture", "baseUrl": "http://127.0.0.1:9/v1", "id": "fixture-model", "apiKeyEnv": "FIXTURE_INTERNAL_KEY"},
            "nativePackages": {"enabled": False, "evidence": "This read-only recipe test needs no native package installation."},
            "core": {"enabled": True}, "profiles": {"enabled": True}, "productivity": {"enabled": False}}

    def tearDown(self):
        self.temporary.cleanup()

    def compile(self):
        self.source.write_text(json.dumps(self.config))
        self.source.chmod(0o600)
        with patch.object(sys, "path", [str(BASE / "scripts"), *sys.path]):
            return self.compiler.compile_config(self.source, self.output, BASE)

    def test_fresh_core_plan_contains_daemon_archive_and_loadable_profile_bindings(self):
        generated = self.compile()
        self.assertIn("dockerDaemon", generated["artifact-plan.json"]["files"])
        self.assertTrue(generated["setup.json"]["docker"]["enabled"])
        profile = generated["profile-plan.json"]
        python_tool = self.catalog["tools"]["python"]
        versioned = python_tool["version"] + "-" + python_tool["artifact"]["sha256"][:12]
        self.assertIn("/tools/python/" + versioned + "/", profile["python"])
        self.assertEqual(profile["pythonSha256"], self.identities["python"]["commands"]["python3"])
        self.assertEqual(profile["clients"]["codex"]["binarySha256"], self.identities["codex"]["commands"]["codex"])
        self.output.mkdir(mode=0o700)
        for name, value in generated.items():
            (self.output / name).write_text(json.dumps(value))
        loaded = load("install-stack").load_site(str(self.output / "installation.json"), "all")
        self.assertTrue(loaded["modelSmoke"])
        self.assertFalse((self.root / "states").exists())

    def test_automatic_bare_reuse_is_reselected_as_a_complete_core_archive(self):
        self.config["reuseExisting"] = True
        def existing(tool, identities):
            if not tool.get("commands"):
                return None
            return {"source": "existing", "adequate": True,
                    "executables": {name: {"path": str(self.root / "qualified-existing" / name), "sha256": identities.get("commands", {}).get(name, "0" * 64)} for name in tool["commands"]},
                    "evidence": "Fixture represents a previously qualified bare command selection."}
        with patch.object(self.compiler, "existing_exact", side_effect=existing):
            generated = self.compile()
        for name in ("codex", "claude", "python", "node"):
            choice = generated["host-plan.json"]["tools"][name]
            self.assertIn(choice["source"], ("kit", "internal"))
            self.assertIn(choice.get("fallbackReason", "insufficient"), ("insufficient", "unavailable"))

    def test_partial_profile_location_override_preserves_generated_bindings(self):
        chosen = str(self.root / "named-codex")
        self.config["profiles"]["clients"] = {"codex": {"home": chosen}}
        profile = self.compile()["profile-plan.json"]
        self.assertEqual(profile["clients"]["codex"]["home"], chosen)
        self.assertIn("skillsDir", profile["clients"]["codex"])
        self.assertEqual(profile["clients"]["codex"]["binarySha256"], self.identities["codex"]["commands"]["codex"])

    def test_nested_hook_activation_cannot_bypass_exact_review_hash(self):
        self.config["profiles"]["clients"] = {"codex": {"activateReviewedHooks": True}}
        with self.assertRaisesRegex(ValueError, "[Rr]eview|profile paths"):
            self.compile()

    def test_explicit_hook_review_binds_to_the_packaged_asset_manifest(self):
        manifest = self.identities["native-profiles"]["files"]["ASSET_MANIFEST.json"]
        self.config["profiles"].update(activateReviewedCodexHooks=True, reviewedAssetManifestSha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "[Rr]eview"):
            self.compile()
        self.config["profiles"]["reviewedAssetManifestSha256"] = manifest
        profile = self.compile()["profile-plan.json"]
        self.assertEqual(profile["reviewedAssetManifestSha256"], manifest)
        self.assertTrue(profile["clients"]["codex"]["activateReviewedHooks"])


if __name__ == "__main__":
    unittest.main()
