"""No Docker/API: complete locks, tamper detection, and metadata-only repair."""
import base64
import csv
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from balrog.adapter import PACKAGE_DIR
from balrog.runtime_locks import stage_runtime_lock
from balrog.suite import ENVIRONMENTS

spec = importlib.util.spec_from_file_location(
    "locked_runtime_guard", PACKAGE_DIR / "task-template/environment/runtime_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class RuntimeLocksTests(unittest.TestCase):
    def setUp(self):
        self.inventory = json.loads((PACKAGE_DIR / "runtime-locks/inventory.json").read_text())

    def test_complete_environment_locks_and_shared_sdk_versions(self):
        for environment in ENVIRONMENTS:
            with self.subTest(environment=environment), tempfile.TemporaryDirectory() as temp:
                target = Path(temp)
                stage_runtime_lock(PACKAGE_DIR, environment, target)
                lock = json.loads((target / "runtime-lock.json").read_text())
                lines = [line for line in (target / "requirements-game.lock").read_text().splitlines()
                         if line and not line.startswith("#")]
                names = set()
                for line in lines:
                    match = re.fullmatch(r"([a-z0-9-]+) @ (https://files\.pythonhosted\.org/\S+) --hash=sha256:([0-9a-f]{64})", line)
                    self.assertIsNotNone(match, line)
                    name, url, digest = match.groups()
                    self.assertNotIn(name, names)
                    names.add(name)
                    self.assertEqual(url, lock["artifacts"][name]["url"])
                    self.assertEqual(digest, lock["artifacts"][name]["sha256"])
                    self.assertEqual(lock["packages"][name], lock["artifacts"][name]["version"])
                self.assertEqual(names | set(lock["source_distributions"]), set(lock["packages"]))
                for name, version in self.inventory["agent"]["packages"].items():
                    self.assertEqual(lock["packages"][name], version)
                expected_apt = dict(self.inventory["base_apt"])
                expected_apt.update(lock["apt_additions"])
                self.assertEqual(lock["apt"], expected_apt)
                self.assertEqual(lock["base_image"], self.inventory["base_image"])

    def test_changed_lock_rejected_before_installing(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            stage_runtime_lock(PACKAGE_DIR, "babyai", target)
            lock = json.loads((target / "runtime-lock.json").read_text())
            (target / "requirements-game.lock").write_text("numpy==2.0.0\n")
            with patch.object(guard.sys, "platform", "linux"), patch.object(guard.platform, "machine", return_value="x86_64"):
                with self.assertRaisesRegex(ValueError, "dependency lock changed"):
                    guard.install_python(lock, target)

    def test_wrong_platform_rejected_before_installing(self):
        with patch.object(guard.platform, "machine", return_value="aarch64"):
            with self.assertRaisesRegex(ValueError, "Linux x86_64"):
                guard.verify_inputs({}, Path("unused"))

    def test_source_manifest_checks_bytes_and_complete_archive_set(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "balrog.tar.gz").write_bytes(b"pinned source")
            (root / "manifest.json").write_text(json.dumps({"archives": {
                "balrog.tar.gz": {"sha256": hashlib.sha256(b"pinned source").hexdigest()}}}))
            guard.verify_sources(root)
            (root / "balrog.tar.gz").write_bytes(b"changed source")
            with self.assertRaisesRegex(ValueError, "source archive changed"):
                guard.verify_sources(root)
            (root / "extra.tar.gz").write_bytes(b"injected")
            with self.assertRaisesRegex(ValueError, "do not match"):
                guard.verify_sources(root)

    def test_baba_patch_changes_only_declared_metadata_and_updates_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            info = root / "baba-0.0.1.dist-info"
            info.mkdir()
            metadata_file = PurePosixPath("baba-0.0.1.dist-info/METADATA")
            record_file = PurePosixPath("baba-0.0.1.dist-info/RECORD")
            (root / metadata_file).write_text("Name: baba\nVersion: 0.0.1\nRequires-Dist: opencv-python\n")
            (root / record_file).write_text(f"{metadata_file.as_posix()},,\n{record_file.as_posix()},,\n")
            dist = SimpleNamespace(version="0.0.1", files=[metadata_file, record_file], locate_file=lambda p: root / p)
            lock = self.inventory["environments"]["babaisai"]
            with patch.object(guard.metadata, "distribution", return_value=dist), \
                 patch.object(guard, "distribution_file_hashes", return_value={"cv2/binary.so": "abc"}):
                guard.patch_baba(lock, root)
                self.assertIn("Requires-Dist: opencv-python-headless\n", (root / metadata_file).read_text())
                rows = list(csv.reader((root / record_file).read_text().splitlines()))
                digest = base64.urlsafe_b64encode(hashlib.sha256((root / metadata_file).read_bytes()).digest()).rstrip(b"=").decode()
                self.assertEqual(rows[0][1], "sha256=" + digest)
                self.assertTrue(json.loads((root / "metadata-patch.json").read_text())["opencv_files_unchanged"])
                with self.assertRaisesRegex(ValueError, "differs from the reviewed patch"):
                    guard.patch_baba(lock, root)

    def test_all_builds_use_digest_base_and_forbid_dependency_resolution(self):
        for environment in ENVIRONMENTS:
            path = PACKAGE_DIR / ("task-template/environment/Dockerfile.game" if environment == "babyai"
                                  else f"runtime-dockerfiles/{environment}.Dockerfile")
            contents = path.read_text()
            self.assertEqual(contents.splitlines()[0], "FROM " + self.inventory["base_image"])
            self.assertIn("runtime_guard.py sources", contents)
            self.assertIn("runtime_guard.py verify", contents)
            for line in contents.splitlines():
                if "pip install" in line:
                    self.assertIn("--no-deps", line)
                    self.assertIn("--no-build-isolation", line)
        agent = (PACKAGE_DIR / "task-template/environment/Dockerfile").read_text()
        self.assertIn("--require-hashes", agent)
        self.assertIn("--no-deps --no-build-isolation", agent)


if __name__ == "__main__":
    unittest.main()
