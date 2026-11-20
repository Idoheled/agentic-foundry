import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/profile-preservation.py"
spec = importlib.util.spec_from_file_location("profile_preservation", SCRIPT)
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.profile = self.base / "profile"
        self.profile.mkdir(mode=0o700)
        self.state = self.base / "state"
        self.plan_path = self.base / "plan.json"
        self.config = self.profile / "settings.json"
        self.original = {"model": "private-model", "env": {"ANTHROPIC_BASE_URL": "https://private.example", "TOKEN": "secret-kept-private"},
                         "hooks": {"SessionStart": [{"command": "existing-hook"}]}}
        self.config.write_text(json.dumps(self.original))
        self.config.chmod(0o600)
        self.plan = {"schemaVersion": 1, "discoveryComplete": True,
                     "discoveryEvidence": "Fixture profile, project scope and environment inspected",
                     "roots": [{"path": str(self.profile)}], "envNames": []}

    def tearDown(self):
        self.temp.cleanup()

    def snap(self):
        self.plan_path.write_bytes(pp.canonical(self.plan))
        return pp.snapshot(self.plan_path, self.state)

    def check(self):
        return pp.verify(self.state, "test")

    def write_config(self, value):
        self.config.write_text(json.dumps(value))

    def test_unchanged_exact_private_snapshot(self):
        result = self.snap()
        self.assertEqual(result["status"], "snapshotted")
        self.assertEqual(self.check()["status"], "preserved")
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.state / "baseline.json").stat().st_mode), 0o400)
        backup = self.state / "originals" / pp.digest(self.config.read_bytes())
        self.assertEqual(backup.read_bytes(), self.config.read_bytes())
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o400)

    def test_configuration_identity_stable_and_tracks_allowed_changes(self):
        self.plan["additiveJson"] = [{"path": str(self.config), "allowedPointers": ["/hooks"], "reason": "Reviewed lifecycle hook addition"}]
        self.snap()
        old = self.check()["configurationIdentity"]
        self.assertEqual(old, self.check()["configurationIdentity"])
        value = json.loads(json.dumps(self.original))
        value["hooks"]["Stop"] = [{"command": "new-reviewed-hook"}]
        self.write_config(value)
        report = self.check()
        self.assertEqual(report["status"], "preserved")
        self.assertNotEqual(old, report["configurationIdentity"])
        first_change = report["configurationIdentity"]
        (self.profile / "new-file.txt").write_text("new reviewed capability")
        report = self.check()
        self.assertNotEqual(first_change, report["configurationIdentity"])
        review = self.base / "addition-review.json"
        review.write_bytes(pp.canonical({"schemaVersion": 1, "reason": "Reviewed exact new file",
                                        "entries": [{"path": path, "identity": identity} for path, identity in report["unreviewedAdditions"].items()]}))
        pp.record_additions(self.state, review)
        self.assertEqual(report["configurationIdentity"], self.check()["configurationIdentity"])
        self.assertEqual(self.check()["status"], "preserved")

    def test_incomplete_discovery_and_rebaseline_refused(self):
        self.plan["discoveryComplete"] = False
        with self.assertRaisesRegex(pp.PreservationError, "acknowledge"):
            self.snap()
        self.plan["discoveryComplete"] = True
        self.snap()
        with self.assertRaisesRegex(pp.PreservationError, "never rebaseline"):
            self.snap()

    def test_existing_route_or_auth_changes_block(self):
        self.plan["additiveJson"] = [{"path": str(self.config), "allowedPointers": ["/hooks"], "reason": "Reviewed lifecycle hook addition"}]
        self.snap()
        for key in ("ANTHROPIC_BASE_URL", "TOKEN"):
            value = json.loads(json.dumps(self.original))
            value["env"][key] = "changed"
            self.write_config(value)
            self.assertEqual(self.check()["status"], "blocked")

    def test_additive_hooks_preserve_values_and_order(self):
        self.plan["additiveJson"] = [{"path": str(self.config), "allowedPointers": ["/hooks"], "reason": "Inspected native hooks"}]
        self.snap()
        value = json.loads(json.dumps(self.original))
        value["hooks"]["SessionStart"].append({"command": "new-hook"})
        self.write_config(value)
        self.assertEqual(self.check()["status"], "preserved")
        value["hooks"]["SessionStart"][0]["command"] = "rewritten-existing-hook"
        self.write_config(value)
        self.assertEqual(self.check()["status"], "blocked")

    def test_added_model_default_outside_reviewed_scope_blocks(self):
        self.plan["additiveJson"] = [{"path": str(self.config), "allowedPointers": ["/hooks"], "reason": "Reviewed hooks only"}]
        self.snap()
        value = json.loads(json.dumps(self.original))
        value["defaultProvider"] = "different"
        self.write_config(value)
        self.assertEqual(self.check()["status"], "blocked")

    def test_root_additive_scope_and_missing_reason_refused(self):
        for pointers, reason in [([""], "too broad"), (["/hooks"], "")]:
            self.plan["additiveJson"] = [{"path": str(self.config), "allowedPointers": pointers, "reason": reason}]
            with self.assertRaises(pp.PreservationError):
                self.snap()

    def test_json_duplicate_key_or_type_change_refused(self):
        self.plan["additiveJson"] = [{"path": str(self.config), "allowedPointers": ["/hooks"], "reason": "Hooks"}]
        self.original["flags"] = [True]
        self.write_config(self.original)
        self.snap()
        changed = dict(self.original, flags=[1])
        self.write_config(changed)
        self.assertEqual(self.check()["status"], "blocked")
        self.config.write_text('{"model":"x","model":"y"}')
        with self.assertRaisesRegex(pp.PreservationError, "Duplicate"):
            self.check()

    def test_new_files_need_exact_review_and_remain_bound(self):
        self.snap()
        skill = self.profile / "new-skill.md"
        skill.write_text("new intended instruction")
        report = self.check()
        self.assertEqual(report["status"], "blocked")
        review = self.base / "addition-review.json"
        review.write_bytes(pp.canonical({"schemaVersion": 1, "reason": "Reviewed full new skill content against selected bundle",
                                        "entries": [{"path": path, "identity": value} for path, value in report["unreviewedAdditions"].items()]}))
        pp.record_additions(self.state, review)
        self.assertEqual(self.check()["status"], "preserved")
        skill.write_text("silently replaced later")
        self.assertEqual(self.check()["status"], "blocked")

    def test_removed_or_permission_changed_existing_files_block(self):
        self.snap()
        self.config.chmod(0o644)
        self.assertEqual(self.check()["status"], "blocked")
        self.config.unlink()
        self.assertEqual(self.check()["status"], "blocked")

    def test_symlink_targets_followed_and_changes_block(self):
        external = self.base / "external-brain.md"
        external.write_text("preserve brain")
        link = self.profile / "BRAIN.md"
        link.symlink_to(external)
        self.snap()
        self.assertIn(str(external), self.check()["followedSymlinkTargets"])
        self.assertIn(str(external), self.check()["protectedRoots"])
        self.assertIn(str(self.profile), self.check()["protectedRoots"])
        external.write_text("brain changed")
        self.assertEqual(self.check()["status"], "blocked")

    def test_dangling_link_becoming_live_needs_addition_review(self):
        external = self.base / "future-brain.md"
        (self.profile / "BRAIN.md").symlink_to(external)
        self.snap()
        self.assertEqual(self.check()["status"], "preserved")
        external.write_text("new behavior")
        self.assertEqual(self.check()["status"], "blocked")

    def test_ancestor_symlink_repoint_blocks(self):
        other = self.base / "other"
        other.mkdir()
        (other / self.config.name).write_bytes(self.config.read_bytes())
        (other / self.config.name).chmod(0o600)
        link = self.base / "profile-link"
        link.symlink_to(self.profile, target_is_directory=True)
        self.plan["roots"] = [{"path": str(link / self.config.name)}]
        self.snap()
        self.assertIn(str(self.config), self.check()["protectedRoots"])
        link.unlink()
        link.symlink_to(other, target_is_directory=True)
        self.assertEqual(self.check()["status"], "blocked")

    def test_symlink_cycles_and_state_recursion_fail(self):
        (self.profile / "cycle").symlink_to(self.profile, target_is_directory=True)
        with self.assertRaisesRegex(pp.PreservationError, "cycle"):
            self.snap()
        (self.profile / "cycle").unlink()
        self.state = self.base / "state2"
        (self.profile / "evidence").symlink_to(self.state, target_is_directory=True)
        with self.assertRaisesRegex(pp.PreservationError, "preservation state"):
            self.snap()

    def test_state_parent_symlink_refused(self):
        target = self.base / "actual-private"
        target.mkdir(mode=0o700)
        link = self.base / "linked-private"
        link.symlink_to(target, target_is_directory=True)
        self.state = link / "state"
        with self.assertRaisesRegex(pp.PreservationError, "symlink ancestor"):
            self.snap()

    def test_mutable_exclusions_explicit_never_deleted(self):
        session = self.profile / "sessions"
        session.mkdir()
        item = session / "latest.jsonl"
        item.write_text("session1")
        self.plan["roots"][0].update(exclude=["sessions/**"], exclusionReason="Owned live session history backed up separately")
        self.snap()
        item.write_text("session1\nsession2")
        self.assertEqual(self.check()["status"], "preserved")
        self.assertTrue(item.exists())

    def test_environment_fingerprints_do_not_emit_values(self):
        self.plan["envNames"] = ["TEST_PRIVATE_ROUTE", "TEST_PRIVATE_TOKEN"]
        with patch.dict(os.environ, {"TEST_PRIVATE_ROUTE": "https://internal-route", "TEST_PRIVATE_TOKEN": "never-print-this-value"}):
            self.snap()
            self.assertEqual(self.check()["status"], "preserved")
            self.assertNotIn("never-print-this-value", (self.state / "baseline.json").read_text())
            os.environ["TEST_PRIVATE_TOKEN"] = "changed-secret"
            report = self.check()
            self.assertEqual(report["environmentChangedNames"], ["TEST_PRIVATE_TOKEN"])
            self.assertNotIn("changed-secret", json.dumps(report))

    def test_original_backup_damage_fails_even_unchanged_active_file(self):
        self.snap()
        original = self.state / "originals" / pp.digest(self.config.read_bytes())
        original.chmod(0o600)
        original.write_text("bad backup")
        with self.assertRaisesRegex(pp.PreservationError, "backup changed"):
            self.check()

    def test_bounded_size_refuses_silent_truncation(self):
        self.plan["maxFileBytes"] = 8
        with self.assertRaisesRegex(pp.PreservationError, "oversized"):
            self.snap()

    def prepare_migration(self):
        before = self.base / "effective-before.json"
        before.write_bytes(pp.canonical(self.original))
        self.plan["semanticEvidence"] = [{"id": "omp-global", "path": str(before), "coveredPaths": [str(self.config)],
                                         "coverage": "Complete migrated settings with unredacted private auth and route values"}]
        self.snap()
        old_sha = pp.digest(self.config.read_bytes())
        backup = self.profile / "settings.json.bak"
        self.config.rename(backup)
        target = self.profile / "config.yml"
        target.write_text("model: private-model\n")
        after = self.base / "effective-after.json"
        after.write_bytes(pp.canonical(self.original))
        spec = {"schemaVersion": 1, "sourcePath": str(self.config), "sourceSha256": old_sha,
                "destinationPath": str(target), "destinationSha256": pp.digest(target.read_bytes()),
                "retainedOriginalPath": str(backup), "baselineSemanticEvidence": "omp-global",
                "afterSemanticEvidence": {"path": str(after), "sha256": pp.digest(after.read_bytes())},
                "explanation": "Copied-profile native migration rehearsal; actual effective configuration exports checked"}
        path = self.base / "migration.json"
        path.write_bytes(pp.canonical(spec))
        return path, spec, after, target, backup

    def test_reviewed_format_migration_preserves_original_and_equivalent_semantics(self):
        path, spec, after, target, backup = self.prepare_migration()
        self.assertEqual(self.check()["status"], "blocked")
        pp.record_migration(self.state, path)
        self.assertEqual(self.check()["status"], "preserved")
        target.write_text("changed again")
        self.assertEqual(self.check()["status"], "blocked")

    def test_migration_route_change_in_export_refused(self):
        path, spec, after, target, backup = self.prepare_migration()
        after.write_bytes(pp.canonical(dict(self.original, model="wrong-model")))
        spec["afterSemanticEvidence"]["sha256"] = pp.digest(after.read_bytes())
        path.write_bytes(pp.canonical(spec))
        with self.assertRaisesRegex(pp.PreservationError, "not semantically identical"):
            pp.record_migration(self.state, path)

    def test_migration_requires_original_backup_and_before_evidence(self):
        path, spec, after, target, backup = self.prepare_migration()
        backup.write_text("not original")
        with self.assertRaisesRegex(pp.PreservationError, "Retained original"):
            pp.record_migration(self.state, path)

    def test_semantic_evidence_cannot_cover_unprotected_file(self):
        before = self.base / "effective-before.json"
        before.write_bytes(pp.canonical(self.original))
        self.plan["semanticEvidence"] = [{"id": "unrelated", "path": str(before), "coveredPaths": [str(self.base / "unprotected")],
                                         "coverage": "Invalid attempt to bind unprotected input"}]
        with self.assertRaisesRegex(pp.PreservationError, "outside the exact protected baseline"):
            self.snap()

    def test_additive_toml_preserves_route_and_auth(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest("TOML capability intentionally requires Python3.11+")
        self.config.unlink()
        self.config = self.profile / "config.toml"
        old = 'model = "private"\n[model_providers.internal]\nbase_url = "https://private.example"\n[hooks]\n'
        self.config.write_text(old)
        self.plan["additiveToml"] = [{"path": str(self.config), "allowedPointers": ["/hooks"], "reason": "Native hook approval table"}]
        self.snap()
        self.config.write_text(old + 'approved = ["exact-definition"]\n')
        self.assertEqual(self.check()["status"], "preserved")
        self.config.write_text((old + 'approved = ["exact-definition"]\n').replace('https://private.example', 'https://changed.example'))
        self.assertEqual(self.check()["status"], "blocked")

    def test_discover_requires_review_and_never_contains_raw_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "do-not-display", "CLAUDE_CONFIG_DIR": str(self.profile)}):
            plan = pp.discover(self.base)
            self.assertFalse(plan["discoveryComplete"])
            self.assertIn(str(self.profile), [item["path"] for item in plan["roots"]])
            self.assertNotIn("do-not-display", json.dumps(plan))

    def test_discover_matches_named_omp_profile_precedence(self):
        values = {"OMP_PROFILE": "work", "PI_PROFILE": "wrong", "PI_CONFIG_DIR": "/custom", "PI_CODING_AGENT_DIR": str(self.base / "ignored")}
        with patch.dict(os.environ, values):
            plan = pp.discover(self.base)
            paths = [item["path"] for item in plan["roots"]]
            self.assertIn(str(self.base / "custom/profiles/work/agent"), paths)
            self.assertNotIn(str(self.base / "ignored"), paths)
        values["OMP_PROFILE"] = ""
        with patch.dict(os.environ, values):
            paths = [item["path"] for item in pp.discover(self.base)["roots"]]
            self.assertIn(str(self.base / "ignored"), paths)

    def test_discover_rejects_invalid_pinned_omp_profile(self):
        with patch.dict(os.environ, {"OMP_PROFILE": "../other"}):
            with self.assertRaisesRegex(pp.PreservationError, "profile environment is invalid"):
                pp.discover(self.base)

    def mutable_rule(self, pointers):
        self.plan["mutableJson"] = [{"path": str(self.config), "pointers": pointers,
                                     "reason": "Inspected current client schema: these exact existing leaves are last-session usage metadata only"}]

    def test_mutable_timestamp_preserves_identity_and_other_configuration(self):
        self.original["lastSessionAt"] = "2026-11-20T10:00:00Z"
        self.write_config(self.original)
        self.mutable_rule(["/lastSessionAt"])
        self.snap()
        identity = self.check()["configurationIdentity"]
        after = dict(self.original, lastSessionAt="2026-11-20T11:00:00Z")
        self.write_config(after)
        report = self.check()
        self.assertEqual(report["status"], "preserved")
        self.assertEqual(identity, report["configurationIdentity"])
        self.assertEqual(len(report["reviewedMutableJsonChanges"]), 1)
        after["model"] = "different-model"
        self.write_config(after)
        self.assertEqual(self.check()["status"], "blocked")
        self.assertNotEqual(identity, self.check()["configurationIdentity"])

    def test_mutable_numeric_usage_counters_and_historical_session_id(self):
        self.original.update(lastTotalInputTokens=12, lastAPIDuration=10.5, lastSessionId="old-session")
        self.write_config(self.original)
        self.mutable_rule(["/lastTotalInputTokens", "/lastAPIDuration", "/lastSessionId"])
        self.snap()
        identity = self.check()["configurationIdentity"]
        self.write_config(dict(self.original, lastTotalInputTokens=81, lastAPIDuration=12.2, lastSessionId="new-session"))
        self.assertEqual(self.check()["status"], "preserved")
        self.assertEqual(identity, self.check()["configurationIdentity"])

    def test_mutable_security_and_model_control_exemptions_refused(self):
        for pointer in ("/model", "/provider", "/authToken", "/apiKey", "/clientSecret", "/hooks/lastSessionAt",
                        "/model/maxOutputTokens", "/maxOutputTokens", "/contextWindow", "/lastAuthAt", "/token"):
            with self.subTest(pointer=pointer):
                self.mutable_rule([pointer])
                with self.assertRaises(pp.PreservationError):
                    pp.validate_plan(self.plan)

    def test_mutable_string_token_counts_and_arbitrary_numeric_fields_refused(self):
        self.original["lastTotalInputTokens"] = "credential-looking-string"
        self.write_config(self.original)
        self.mutable_rule(["/lastTotalInputTokens"])
        with self.assertRaisesRegex(pp.PreservationError, "type is not appropriate"):
            self.snap()
        self.mutable_rule(["/unrecognizedNumericField"])
        with self.assertRaisesRegex(pp.PreservationError, "Ambiguous"):
            pp.validate_plan(self.plan)

    def test_mutable_leaf_presence_type_and_file_metadata_preserved(self):
        self.original["lastUsedAt"] = 10
        self.write_config(self.original)
        self.mutable_rule(["/lastUsedAt"])
        self.snap()
        self.write_config(dict(self.original, lastUsedAt="10"))
        self.assertEqual(self.check()["status"], "blocked")
        value = dict(self.original)
        del value["lastUsedAt"]
        self.write_config(value)
        self.assertEqual(self.check()["status"], "blocked")
        self.write_config(dict(self.original, lastUsedAt=20))
        self.config.chmod(0o644)
        self.assertEqual(self.check()["status"], "blocked")

    def test_mutable_json_pointer_escaping_is_exact(self):
        self.original["usage/stats"] = {"last~SeenAt": 10}
        self.original["usage"] = {"stats": {"last~SeenAt": 70}}
        self.write_config(self.original)
        self.mutable_rule(["/usage~1stats/last~0SeenAt"])
        self.snap()
        identity = self.check()["configurationIdentity"]
        value = json.loads(json.dumps(self.original))
        value["usage/stats"]["last~SeenAt"] = 20
        self.write_config(value)
        self.assertEqual(self.check()["status"], "preserved")
        self.assertEqual(identity, self.check()["configurationIdentity"])
        value["usage"]["stats"]["last~SeenAt"] = 80
        self.write_config(value)
        self.assertEqual(self.check()["status"], "blocked")

    def test_mutable_missing_non_scalar_wildcard_and_invalid_pointer_refused(self):
        for pointer in ("", "/", "/usage/*/lastUsedAt", "/usage~2stats/lastUsedAt"):
            self.mutable_rule([pointer])
            with self.assertRaises(pp.PreservationError):
                pp.validate_plan(self.plan)
        self.mutable_rule(["/lastUsedAt"])
        with self.assertRaisesRegex(pp.PreservationError, "existing field"):
            self.snap()

    def test_mutable_and_additive_json_combine_without_ignoring_routes(self):
        self.original["lastUsedAt"] = 10
        self.write_config(self.original)
        self.mutable_rule(["/lastUsedAt"])
        self.plan["additiveJson"] = [{"path": str(self.config), "allowedPointers": ["/hooks"], "reason": "Reviewed additional hook"}]
        self.snap()
        identity = self.check()["configurationIdentity"]
        value = json.loads(json.dumps(self.original))
        value["lastUsedAt"] = 11
        value["hooks"]["Stop"] = [{"command": "new-hook"}]
        self.write_config(value)
        self.assertEqual(self.check()["status"], "preserved")
        self.assertNotEqual(identity, self.check()["configurationIdentity"])
        value["env"]["ANTHROPIC_BASE_URL"] = "changed-route"
        self.write_config(value)
        self.assertEqual(self.check()["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
