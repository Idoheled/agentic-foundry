"""Real Git LFS cache/checkout regressions; all fixture supply is local."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("git-lfs"), "Git LFS is required for cached-object integration tests")
class LfsMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="foundry-lfs-checkout-")
        self.root = Path(self.tmp.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_ALLOW_PROTOCOL="", GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1")
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture Maintainer")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("lfs", "install", "--local")
        (self.root / ".gitattributes").write_text("offline/objects/sha256/*.chunk filter=lfs diff=lfs merge=lfs -text\n")
        self.content = b"cached agentic-foundry fixture\x00" * 64
        self.oid = hashlib.sha256(self.content).hexdigest()
        self.relative = "offline/objects/sha256/" + self.oid + ".chunk"
        self.object = self.root / self.relative
        self.object.parent.mkdir(parents=True)
        self.pointer = ("version https://git-lfs.github.com/spec/v1\noid sha256:" + self.oid +
                        "\nsize " + str(len(self.content)) + "\n").encode()
        self.object.write_bytes(self.pointer)
        self.git("add", ".gitattributes", self.relative)
        self.git("commit", "-qm", "Cached LFS checkout fixture")
        self.commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.git("cat-file", "blob", "HEAD:" + self.relative).stdout.encode(), self.pointer)
        self.cache = self.root / ".git/lfs/objects" / self.oid[:2] / self.oid[2:4] / self.oid
        self.marker = self.root / "transfer-invoked"
        trap = self.root / "transfer-trap.py"
        trap.write_text("from pathlib import Path\nimport sys\nPath(__file__).with_name('transfer-invoked').write_text('unexpected transfer')\nsys.exit(89)\n")
        # A transfer attempt cannot access a service: the only configured endpoint
        # is local, and the standalone transfer implementation records and fails.
        self.git("config", "lfs.url", (self.root / "no-remote-service").as_uri())
        self.git("config", "lfs.standalonetransferagent", "no-network")
        self.git("config", "lfs.customtransfer.no-network.path", sys.executable)
        self.git("config", "lfs.customtransfer.no-network.args", str(trap))
        self.git("config", "lfs.customtransfer.no-network.concurrent", "false")
        script = self.root / "ci/materialize-lfs.sh"
        script.parent.mkdir()
        shutil.copyfile(ROOT / "ci/materialize-lfs.sh", script)
        self.script = script

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, env=None):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, text=True,
                              capture_output=True, env=self.env if env is None else env)

    def cached(self):
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_bytes(self.content)

    def materialize(self):
        result = subprocess.run(["bash", str(self.script)], cwd=self.root, env=self.env,
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.marker.exists(), "Cached checkout must not invoke a download transfer")
        return result

    def test_same_commit_checkout_leaves_pointer_then_explicit_lfs_checkout_materializes(self):
        self.cached()
        second_checkout_env = dict(self.env, GIT_LFS_SKIP_SMUDGE="0")
        self.git("checkout", "--force", self.commit, env=second_checkout_env)
        self.assertEqual(self.object.read_bytes(), self.pointer,
                         "This fixture reproduces the same-commit checkout leaving its pointer unchanged")
        self.materialize()
        self.assertEqual(self.object.read_bytes(), self.content)
        self.assertEqual(hashlib.sha256(self.object.read_bytes()).hexdigest(), self.oid)
        self.assertEqual(self.git("cat-file", "blob", "HEAD:" + self.relative).stdout.encode(), self.pointer)

    def test_missing_cache_is_not_downloaded_or_claimed_as_verified(self):
        self.assertFalse(self.cache.exists())
        result = self.materialize()
        self.assertEqual(self.object.read_bytes(), self.pointer)
        self.assertFalse(self.cache.exists())
        self.assertIn("publisher will verify", result.stdout)

    def test_modified_worktree_bytes_are_preserved(self):
        self.cached()
        edited = b"modified working-tree data"
        self.object.write_bytes(edited)
        self.materialize()
        self.assertEqual(self.object.read_bytes(), edited)


if __name__ == "__main__":
    unittest.main()
