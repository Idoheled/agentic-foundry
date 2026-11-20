import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compile_site", ROOT / "scripts/compile-site.py")
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


class CompileSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kit = self.root / "kit"
        (self.kit / "config").mkdir(parents=True)
        (self.kit / "provenance/r5").mkdir(parents=True)
        self.mirror = self.root / "private"; self.mirror.mkdir()
        self.artifact = self.mirror / "demo.bin"
        self.artifact.write_bytes(b"fixture")
        self.catalog = {"schemaVersion": 1, "tools": {"demo": {"version": "1", "commands": {"demo": {"path": "bin/demo"}},
            "artifact": {"path": "payload/demo.bin", "sha256": c.sha(self.artifact), "format": "file"}}}}
        (self.kit / "config/host-catalog.json").write_text(json.dumps(self.catalog))
        (self.kit / "provenance/r5/host-file-identities.json").write_text("{}")
        self.config = {"schemaVersion": 1, "schemaKind": "minimal", "bootstrapMode": "fresh", "evidence": "Disposable fixture target inspected", "mode": "user", "stateRoot": str(self.root / "state"),
            "privateSupply": {"roots": [str(self.mirror)], "inspectionEvidence": "Declared fixture repository inspected", "allowKitFallback": True},
            "core": {"enabled": False}, "profiles": {"enabled": False}, "productivity": {"enabled": False},
            "nativePackages": {"enabled": False, "evidence": "Fixture native prerequisites are available"}, "reuseExisting": False}
        self.input = self.root / "site.json"; self.output = self.root / "out"

    def compile(self):
        self.input.write_text(json.dumps(self.config))
        return c.compile_config(self.input, self.output, self.kit)

    def test_private_exact_mirror_is_preferred_and_compilation_does_not_install(self):
        value = self.compile()
        self.assertEqual(value["host-plan.json"]["tools"]["demo"]["source"], "internal")
        self.assertFalse(self.output.exists()); self.assertFalse((self.root / "state").exists())

    def test_mismatch_is_not_silently_selected_as_qualified(self):
        self.artifact.write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "private candidate differs"):
            self.compile()

    def test_disabled_fallback_blocks(self):
        self.artifact.unlink(); self.config["privateSupply"]["allowKitFallback"] = False
        with self.assertRaisesRegex(ValueError, "fallback is disabled"):
            self.compile()

    def test_private_symlink_escape_is_not_a_mirror_match(self):
        escaped = self.root / "escape.bin"; self.artifact.rename(escaped); self.artifact.symlink_to(escaped)
        self.assertEqual(self.compile()["host-plan.json"]["tools"]["demo"]["source"], "kit")

    def test_missing_private_evidence_blocks(self):
        self.config["privateSupply"]["inspectionEvidence"] = "REPLACE_FINDING"
        with self.assertRaisesRegex(ValueError, "inspection finding"):
            self.compile()

    def test_explicit_private_qualified_version_precedes_kit(self):
        index = self.root / "index.json"
        index.write_text(json.dumps({"schemaVersion": 1, "tools": {"demo": {"source": "internal", "path": str(self.artifact), "sha256": c.sha(self.artifact), "version": "2", "evidence": "Internal v2 qualified with site tests"}}}))
        self.config["privateSupply"]["index"] = str(index)
        value = self.compile()["host-plan.json"]["tools"]["demo"]
        self.assertEqual(value["version"], "2"); self.assertEqual(value["source"], "internal")

    def test_os_payload_mismatch_cannot_be_overridden_by_label(self):
        with patch.object(c.platform, "machine", return_value="aarch64"):
            with self.assertRaisesRegex(ValueError, "x86_64"):
                self.compile()


if __name__ == "__main__":
    unittest.main()
