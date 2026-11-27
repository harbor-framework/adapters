import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from video2world import MANIFEST_SHA256, UPSTREAM_REVISION, bridge
from video2world.adapter import Video2WorldAdapter
from video2world.attempts import Records, harbor_records
from video2world.bridge import evaluate, pack, unpack, write_reward
from video2world.release import load_selection, read_manifest, task_id
from video2world.runtimes import runtime
from video2world.scoring import original_records, write_report


def store_trial(directory, row, record):
    """A real Harbor result schema around an upstream-scored CPU fixture."""
    from harbor.models.trial.result import TrialResult
    from v2w import scoring

    task_path = (
        directory.parent / "tasks" / task_id(row["family"] + "/" + row["sample"])
    )
    verifier = directory / "verifier"
    (verifier / "report").mkdir(parents=True)
    config = scoring.load_config()
    report = scoring.score(
        {(row["family"], row["sample"]): record},
        scoring.make_scope([row], config),
        config,
    )
    (verifier / "report/summary.json").write_text(json.dumps(report))
    (verifier / "identity.json").write_text(
        json.dumps(
            {
                "family": row["family"],
                "sample": row["sample"],
                "upstream_revision": UPSTREAM_REVISION,
                "manifest_sha256": MANIFEST_SHA256,
            }
        )
    )
    (verifier / "metrics.json").write_text(json.dumps(record))
    result = TrialResult.model_validate(
        {
            "task_name": "aetherlabsai/video2world-"
            + task_id(row["family"] + "/" + row["sample"]),
            "trial_name": directory.name,
            "trial_uri": directory.as_uri(),
            "task_id": {"path": str(task_path)},
            "source": "cpu-fixture",
            "task_checksum": "0" * 64,
            "config": {
                "task": {"path": str(task_path)},
                "trial_name": directory.name,
                "trials_dir": str(directory.parent),
            },
            "agent_info": {"name": "oracle", "version": "cpu-fixture"},
            "started_at": "2026-11-20T00:00:00Z",
            "finished_at": "2026-11-20T00:00:01Z",
            "verifier_environment_mode": "separate",
            "verifier_result": {"rewards": {"reward": report["v2w_score"] / 100}},
        }
    )
    (directory / "result.json").write_text(result.model_dump_json())
    (directory / "config.json").write_text(result.config.model_dump_json())
    return json.loads(result.model_dump_json())


class TransportTests(unittest.TestCase):
    def test_archive_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pkg/assets").mkdir(parents=True)
            (root / "pkg/protocol.json").write_text("{}")
            (root / "pkg/assets/object.obj").write_text("v 0 0 0\n")
            unpack(pack(root / "pkg"), root / "copy")
            self.assertEqual((root / "copy/assets/object.obj").read_text(), "v 0 0 0\n")

    def test_rejects_archive_escape_and_links(self):
        for name, kind in (
            ("../escape", tarfile.REGTYPE),
            ("/escape", tarfile.REGTYPE),
            ("link", tarfile.SYMTYPE),
            ("fifo", tarfile.FIFOTYPE),
        ):
            with (
                self.subTest(name=name, kind=kind),
                tempfile.TemporaryDirectory() as temp,
            ):
                stream = io.BytesIO()
                with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    archive.addfile(member)
                with self.assertRaises(ValueError):
                    unpack(stream.getvalue(), Path(temp) / "copy")

    def test_rejects_package_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "link").symlink_to("/etc/passwd")
            with self.assertRaises(ValueError):
                pack(root)

    def test_blocked_and_nonfinite_reports_have_no_reward(self):
        reports = [
            {"readiness": "blocked", "v2w_score": None},
            {"readiness": "ready", "v2w_score": float("nan")},
            {"readiness": "ready", "v2w_score": True},
        ]
        for report in reports:
            with self.subTest(report=report), tempfile.TemporaryDirectory() as temp:
                out = Path(temp)
                with self.assertRaises((ValueError, RuntimeError)):
                    write_reward(report, out)
                self.assertFalse((out / "reward.txt").exists())


class PublicationTests(unittest.TestCase):
    def test_publication_failure_restores_previous_cohort(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, staged = root / "output", root / "staged"
            target.mkdir()
            staged.mkdir()
            (target / "marker").write_text("previous")
            (staged / "marker").write_text("replacement")
            adapter = Video2WorldAdapter(root, root, target, root / "unused.json")
            rename = Path.rename

            def fail_publication(path, destination):
                if path == staged:
                    raise OSError("injected publication failure")
                return rename(path, destination)

            with (
                patch.object(
                    Path, "rename", autospec=True, side_effect=fail_publication
                ),
                self.assertRaisesRegex(OSError, "publication failure"),
            ):
                adapter._publish(staged)
            self.assertEqual((target / "marker").read_text(), "previous")
            self.assertFalse(list(root.glob(".output.previous-*")))

    def test_failed_rollback_keeps_backup_outside_staging_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "output"
            target.mkdir()
            (target / "marker").write_text("previous")
            adapter = Video2WorldAdapter(root, root, target, root / "unused.json")
            rename = Path.rename
            with tempfile.TemporaryDirectory(dir=root) as staging:
                staged = Path(staging) / "cohort"
                staged.mkdir()

                def fail_both(path, destination):
                    if path == staged or path.name.startswith(".output.previous-"):
                        raise OSError("injected rename failure")
                    return rename(path, destination)

                with (
                    patch.object(Path, "rename", autospec=True, side_effect=fail_both),
                    self.assertRaisesRegex(RuntimeError, "previous cohort retained at"),
                ):
                    adapter._publish(staged)
            backups = list(root.glob(".output.previous-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "marker").read_text(), "previous")


UPSTREAM = os.environ.get("V2W_TEST_UPSTREAM")
DATA = os.environ.get("V2W_TEST_DATA")


@unittest.skipUnless(
    UPSTREAM and DATA, "set V2W_TEST_UPSTREAM and V2W_TEST_DATA to the pinned release"
)
class UpstreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(UPSTREAM).resolve()))
        os.environ["V2W_DATA"] = str(Path(DATA).resolve())
        from v2w import paths

        paths.DATA = Path(DATA).resolve()
        cls.rows = read_manifest(Path(DATA))
        cls.records = {
            (r["family"], r["sample"]): json.loads(
                (Path(DATA) / "har" / r["family"] / (r["sample"] + ".json")).read_text()
            )
            for r in cls.rows
        }

    def test_full_scope_and_runtime_routes(self):
        from v2w import benchmark, scoring

        self.assertEqual(len(self.rows), 222)
        self.assertEqual(len({r["family"] for r in self.rows}), 39)
        configs = [
            benchmark.Configuration(r["family"], r["sample"], r["metric_family"])
            for r in self.rows
        ]
        self.assertEqual(len({task_id(c.key) for c in configs}), 222)
        self.assertEqual(
            {runtime(c.evaluator) for c in configs}, {"sim", "twin", "isaac"}
        )
        for row in self.rows:
            c = benchmark.Configuration(
                row["family"], row["sample"], row["metric_family"]
            )
            self.assertIn(c.evaluator, benchmark.EVALUATORS)
            self.assertTrue(c.profile)
        scope = scoring.make_scope(self.rows, scoring.load_config())
        self.assertTrue(all(r["eligible"] for r in scope["rows"]))
        adapter = Video2WorldAdapter(
            Path(UPSTREAM), Path(DATA), Path("/unused"), Path("/unused"), split="parity"
        )
        subset = adapter._select(self.rows)
        selected = [
            benchmark.Configuration(r["family"], r["sample"], r["metric_family"])
            for r in subset
        ]
        self.assertEqual(len(selected), 22)
        self.assertEqual(
            {(c.profile, c.evaluator) for c in selected},
            {(c.profile, c.evaluator) for c in configs},
        )
        samples = {c.sample for c in selected}
        self.assertEqual(
            {c.key for c in configs if c.sample in samples}, {c.key for c in selected}
        )

    def test_har_score_and_defined_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            report = write_report(self.rows, Records(self.records, []), out / "har")
            self.assertEqual(report["readiness"], "ready")
            self.assertAlmostEqual(report["v2w_score"], 73.784123605048, places=6)
            row = self.rows[0]
            pair = (row["family"], row["sample"])
            for index, (record, status) in enumerate(
                (
                    (
                        {"build": False, "error_kind": "agent", "task_success": False},
                        "ready",
                    ),
                    (None, "blocked"),
                    (
                        {
                            "build": None,
                            "error_kind": "evaluator",
                            "error": "simulator crashed",
                        },
                        "blocked",
                    ),
                )
            ):
                r = write_report([row], Records({pair: record}, []), out / str(index))
                self.assertEqual(r["readiness"], status)
                if status == "ready":
                    self.assertEqual(r["v2w_score"], 0)

    def test_missing_submission_uses_upstream_agent_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            pkg = work / "pkg"
            pkg.mkdir()
            evaluate(self.rows[0], pkg, work)
            report = json.loads((work / "report/summary.json").read_text())
            self.assertEqual(report["readiness"], "ready")
            self.assertEqual(report["v2w_score"], 0)
            self.assertEqual(
                json.loads((work / "metrics.json").read_text())["error_kind"], "agent"
            )

    def test_failed_evaluator_command_blocks_even_if_output_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            pkg = work / "pkg"
            pkg.mkdir()
            (pkg / "protocol.json").write_text("{}")

            def fail(*args, **kwargs):
                ev = next((work / "upstream/experiment").glob("*/*/eval"))
                (ev / "eval.json").write_text('{"build": false, "error_kind": "agent"}')
                raise subprocess.CalledProcessError(9, args[0])

            with patch("video2world.bridge.subprocess.run", side_effect=fail):
                evaluate(self.rows[0], pkg, work)
            report = json.loads((work / "report/summary.json").read_text())
            self.assertEqual(report["readiness"], "blocked")
            self.assertIsNone(report["v2w_score"])

    def test_collector_matches_har_and_preserves_missing_slots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            results = root / "results"
            selection = root / "selection.json"
            selection.write_text(
                json.dumps(
                    {
                        "manifest_sha256": MANIFEST_SHA256,
                        "upstream_revision": UPSTREAM_REVISION,
                        "configurations": self.rows,
                    }
                )
            )
            for i, row in enumerate(self.rows):
                d = results / str(i) / "verifier"
                store_trial(d.parent, row, self.records[(row["family"], row["sample"])])
                original = root / "original" / row["family"] / row["sample"]
                original.mkdir(parents=True)
                (original / "metrics.json").write_bytes(
                    (d / "metrics.json").read_bytes()
                )
            rows = load_selection(Path(UPSTREAM), Path(DATA), selection)
            report = write_report(
                rows, harbor_records(results, rows), root / "complete"
            )
            baseline = write_report(
                rows, original_records(root / "original", rows), root / "baseline"
            )
            self.assertEqual(report, baseline)
            for source, path in (
                ("--results", results),
                ("--experiment", root / "original"),
            ):
                output = root / ("report-" + source.removeprefix("--"))
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "video2world.scoring",
                        "--upstream-root",
                        UPSTREAM,
                        "--data-root",
                        DATA,
                        "--selection",
                        str(selection),
                        source,
                        str(path),
                        "--out",
                        str(output),
                    ],
                    text=True,
                    capture_output=True,
                    check=True,
                )
                self.assertIn("V2WScore 73.784124", completed.stdout)
                self.assertEqual(
                    json.loads((output / "summary.json").read_text()),
                    {key: value for key, value in report.items() if key != "samples"},
                )
            self.assertEqual(report["readiness"], "ready")
            self.assertAlmostEqual(report["v2w_score"], 73.784123605048, places=6)
            (results / "0/verifier/metrics.json").unlink()
            missing = write_report(
                rows, harbor_records(results, rows), root / "incomplete"
            )
            self.assertEqual(missing["configurations"], 222)
            self.assertEqual(missing["readiness"], "blocked")
            self.assertIsNone(missing["v2w_score"])

    def test_harbor_records_reject_duplicate_and_mixed_provenance(self):
        row = self.rows[0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "job"
            for name in ("first", "duplicate"):
                store_trial(
                    root / name, row, self.records[(row["family"], row["sample"])]
                )
            with self.assertRaisesRegex(ValueError, "duplicate attempt"):
                write_report(
                    [row],
                    harbor_records(root, [row]),
                    Path(temp) / "duplicate-report",
                )
            # Keep the diagnostic output outside the job directory being scanned.
            shutil.rmtree(root / "duplicate")
            identity = json.loads((root / "first/verifier/identity.json").read_text())
            identity["upstream_revision"] = "different release"
            (root / "first/verifier/identity.json").write_text(json.dumps(identity))
            with self.assertRaisesRegex(ValueError, "mismatched result provenance"):
                write_report(
                    [row],
                    harbor_records(root, [row]),
                    Path(temp) / "provenance-report",
                )

    def test_attempt_ledger_keeps_failures_and_incomplete_trials(self):
        rows = self.rows[:8]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "job"
            method_failure = {
                "build": False,
                "error_kind": "agent",
                "task_success": False,
            }
            for index, kind in enumerate(
                (
                    "valid",
                    "method_failure",
                    "agent_timeout",
                    "provider_failure",
                    "no_reward",
                    "incomplete",
                    "no_result",
                )
            ):
                directory = job / kind
                row = rows[index]
                record = (
                    method_failure
                    if kind in ("method_failure", "agent_timeout", "provider_failure")
                    else self.records[(row["family"], row["sample"])]
                )
                result = store_trial(directory, row, record)
                if kind in ("agent_timeout", "provider_failure"):
                    result["exception_info"] = {
                        "exception_type": "AgentTimeoutError"
                        if kind == "agent_timeout"
                        else "ApiError",
                        "exception_message": "fixture failure",
                        "exception_traceback": "fixture",
                        "occurred_at": "2026-11-20T00:00:01Z",
                    }
                    if kind == "provider_failure":
                        result["step_results"] = [
                            {
                                "step_name": "agent",
                                "exception_info": result.pop("exception_info"),
                            }
                        ]
                if kind == "no_reward":
                    result["verifier_result"] = None
                if kind == "incomplete":
                    result["finished_at"] = None
                if kind == "no_result":
                    (directory / "result.json").unlink()
                else:
                    (directory / "result.json").write_text(json.dumps(result))
            records = harbor_records(job, rows)
            report = write_report(rows, records, root / "report")
            self.assertEqual(report["readiness"], "blocked")
            self.assertIsNone(report["v2w_score"])
            ledger = json.loads((root / "report/attempts.json").read_text())
            self.assertEqual(
                ledger["counts"],
                {"attempted": 7, "scored": 3, "failed": 2, "incomplete": 2},
            )
            self.assertEqual(len(ledger["not_attempted"]), 1)
            self.assertEqual(len(ledger["missing"]), 5)
            statuses = {a["trial"]: a["status"] for a in ledger["attempts"]}
            self.assertEqual(statuses["method_failure"], "scored")
            self.assertEqual(statuses["agent_timeout"], "scored")
            self.assertEqual(statuses["provider_failure"], "exception")
            self.assertEqual(statuses["no_reward"], "no_reward")
            provider = next(
                a for a in ledger["attempts"] if a["trial"] == "provider_failure"
            )
            self.assertEqual(provider["exceptions"][0]["type"], "ApiError")

    def test_malformed_trial_is_preserved_in_ledger_before_scoring_fails(self):
        row = self.rows[0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store_trial(
                root / "job/invalid", row, self.records[(row["family"], row["sample"])]
            )
            (root / "job/invalid/result.json").write_text("{broken")
            records = harbor_records(root / "job", [row])
            with self.assertRaisesRegex(ValueError, "invalid Harbor attempts"):
                write_report([row], records, root / "report")
            ledger = json.loads((root / "report/attempts.json").read_text())
            self.assertEqual(ledger["counts"]["failed"], 1)
            self.assertEqual(ledger["attempts"][0]["status"], "invalid_result")
            self.assertTrue(Path(ledger["attempts"][0]["configuration"]).is_file())
            self.assertFalse((root / "report/summary.json").exists())

    def test_actual_cloth_contract_rejects_malformed_submission(self):
        from v2w.tracks.cloth.contract import errors

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "protocol.json").write_text("{}")
            self.assertEqual(errors(root), ["protocol_version must be 3.0"])

    def test_inherited_rigid_entity_check_accepts_external_paths(self):
        from video2sim.bench.protocol import _check_entity

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "pkg"
            package.mkdir()
            external = root / "outside.obj"
            external.write_text("v 0 0 0\n")
            errors = []
            _check_entity(
                {
                    "kind": "mesh",
                    "name": "object",
                    "pos": [0, 0, 0],
                    "mesh_path": str(external),
                    "collision_path": str(external),
                },
                package,
                "object",
                errors,
            )
            self.assertEqual(errors, [])

    def test_actual_cloth_contract_validates_arrays_and_rejects_corruption(self):
        import numpy as np
        from v2w.tracks.cloth.contract import errors

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "source").mkdir()
            (root / "source/video.mp4").write_bytes(
                b"input placeholder; format validator checks existence"
            )
            (root / "report.md").write_text(
                "Synthetic format fixture, not an evaluated reconstruction"
            )
            (root / "scene.json").write_text(
                json.dumps(
                    {
                        "table": {"point": [0, 0, 0], "normal": [0, 0, 1]},
                        "cloth": {
                            "corners": [
                                [0, 0, 0.01],
                                [0.2, 0, 0.01],
                                [0.2, 0.2, 0.01],
                                [0, 0.2, 0.01],
                            ],
                            "grid": [3, 3],
                            "mass": 0.1,
                            "friction": 0.5,
                            "young": 10000,
                            "poisson": 0.2,
                            "thickness": 0.001,
                        },
                    }
                )
            )
            (root / "protocol.json").write_text(
                json.dumps(
                    {
                        "protocol_version": "3.0",
                        "physics_profile": "droid-cloth-camera/1",
                        "coordinate_frame": "first_camera_opencv",
                        "status": "success",
                        "scene": {"path": "scene.json"},
                        "actions": {
                            "path": "actions.npz",
                            "format": "tcp_matrix_grip",
                            "dt": 1 / 15,
                        },
                    }
                )
            )
            np.savez(
                root / "actions.npz",
                tcp_pose=np.repeat(np.eye(4)[None], 2, axis=0),
                gripper_closure=np.array([0, 1]),
            )
            self.assertEqual(errors(root), [])
            np.savez(
                root / "actions.npz",
                tcp_pose=np.zeros((2, 4, 4)),
                gripper_closure=np.array([0, 1]),
            )
            self.assertTrue(any("proper rigid transforms" in e for e in errors(root)))

    def grade_args(self, root):
        config = {
            "configuration": next(
                row for row in self.rows if row["family"] == "droid-cloth-fold"
            ),
            "manifest_sha256": MANIFEST_SHA256,
            "upstream_revision": UPSTREAM_REVISION,
            "tools": {"python": sys.executable},
            "source_files": {
                "v2w/scoring.py": hashlib.sha256(
                    (Path(UPSTREAM) / "v2w/scoring.py").read_bytes()
                ).hexdigest()
            },
            "requirements": [],
        }
        (root / "config.json").write_text(json.dumps(config))
        return argparse.Namespace(
            root=Path(UPSTREAM).resolve(),
            data=Path(DATA).resolve(),
            config=root / "config.json",
            package=root / "pkg",
            work=root / "work",
            out=root / "verifier",
            port=0,
        )

    def test_missing_furniture_assets_block_before_submission_scoring(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.grade_args(root)
            config = json.loads(args.config.read_text())
            config["configuration"] = next(
                row
                for row in self.rows
                if row["metric_family"].get("evaluator") == "fb"
            )
            args.config.write_text(json.dumps(config))
            args.package.mkdir()
            args.out.mkdir()
            (args.out / "reward.txt").write_text("1\n")

            def import_runtime(name):
                if name == "video2sim.bench.bridge_env":
                    raise FileNotFoundError("missing official Bridge library")

            with (
                patch(
                    "video2world.bridge.importlib.import_module",
                    side_effect=import_runtime,
                ),
                self.assertRaisesRegex(FileNotFoundError, "official Bridge library"),
            ):
                bridge.grade(args)
            self.assertFalse((args.out / "reward.txt").exists())
            self.assertFalse((args.out / "upstream").exists())

    @contextmanager
    def evaluator_server(self, root):
        from http.server import HTTPServer

        args = self.grade_args(root)
        ready = threading.Event()
        servers = []

        def create(address, handler):
            server = HTTPServer(("127.0.0.1", 0), handler)
            servers.append(server)
            ready.set()
            return server

        with patch("video2world.bridge.HTTPServer", side_effect=create):
            thread = threading.Thread(target=bridge.serve, args=(args,), daemon=True)
            thread.start()
            self.assertTrue(ready.wait(10), "service did not start")
            try:
                yield f"http://127.0.0.1:{servers[0].server_port}"
            finally:
                servers[0].shutdown()
                servers[0].server_close()
                thread.join(timeout=10)

    def test_public_checker_exposes_no_final_grading_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pkg = root / "pkg"
            pkg.mkdir()
            with self.evaluator_server(root) as url:
                self.assertEqual(
                    bridge.request(url, pkg)["errors"], ["protocol.json missing"]
                )
                request = urllib.request.Request(url + "/evaluate", data=pack(pkg))
                with self.assertRaises(urllib.error.HTTPError) as forbidden:
                    urllib.request.urlopen(request)
                self.assertEqual(forbidden.exception.code, 404)
                self.assertFalse((root / "verifier").exists())

    def test_collected_empty_submission_scores_zero_and_retains_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pkg").mkdir()
            (root / "pkg/agent-note.txt").write_text("collected artifact")
            bridge.grade(self.grade_args(root))
            self.assertEqual((root / "verifier/reward.txt").read_text(), "0\n")
            self.assertTrue((root / "pkg/agent-note.txt").exists())
            self.assertEqual(
                len(
                    list(
                        (root / "verifier/upstream/experiment").glob(
                            "*/*/pkg/agent-note.txt"
                        )
                    )
                ),
                1,
            )

    def test_missing_artifact_blocks_instead_of_scoring_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(
                ValueError, "submission artifact must be a directory"
            ):
                bridge.grade(self.grade_args(root))
            self.assertFalse((root / "verifier/reward.txt").exists())

    def test_scoring_failure_retains_evidence_without_reward(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pkg").mkdir()
            with (
                patch(
                    "v2w.scoring.write_report",
                    side_effect=RuntimeError("injected scoring failure"),
                ),
                self.assertRaisesRegex(RuntimeError, "injected scoring failure"),
            ):
                bridge.grade(self.grade_args(root))
            self.assertTrue((root / "verifier/metrics.json").is_file())
            self.assertTrue((root / "verifier/identity.json").is_file())
            self.assertEqual(
                len(
                    list(
                        (root / "verifier/upstream/experiment").glob(
                            "*/*/eval/eval.json"
                        )
                    )
                ),
                1,
            )
            self.assertFalse((root / "verifier/reward.txt").exists())

    def test_blocked_report_produces_no_reward(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pkg").mkdir()
            (root / "pkg/protocol.json").write_text("{}")
            args = self.grade_args(root)
            with (
                patch(
                    "video2world.bridge.subprocess.run",
                    side_effect=subprocess.CalledProcessError(9, "evaluator"),
                ),
                self.assertRaisesRegex(RuntimeError, "upstream score is blocked"),
            ):
                bridge.grade(args)
            self.assertFalse((root / "verifier/reward.txt").exists())
            self.assertIsNone(
                json.loads((root / "verifier/report/summary.json").read_text())[
                    "v2w_score"
                ]
            )

    def test_invalid_runtime_fails_before_output_creation(self):
        row = next(r for r in self.rows if r["family"] == "droid-cloth-fold")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "runtimes.json"
            config.write_text(
                json.dumps(
                    {
                        "twin": {
                            "image": "twin:test",
                            "python": "/usr/local/bin/python3",
                            "twin_python": 123,
                        }
                    }
                )
            )
            adapter = Video2WorldAdapter(
                Path(UPSTREAM),
                Path(DATA),
                root / "output",
                config,
                task_ids=[row["family"] + "/" + row["sample"]],
            )
            with self.assertRaisesRegex(ValueError, r"twin\.twin_python"):
                adapter.run()
            self.assertFalse((root / "output").exists())

    def test_failed_generation_preserves_entire_previous_cohort(self):
        rows = [r for r in self.rows if r["family"] == "droid-cloth-fold"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "output"
            adapter = Video2WorldAdapter(
                Path(UPSTREAM),
                Path(DATA),
                root,
                Path(__file__).parents[1] / "runtimes/example.json",
                task_ids=[r["family"] + "/" + r["sample"] for r in rows],
            )
            tasks = adapter.run()
            import tomllib

            import yaml
            from harbor.models.task.config import TaskConfig
            from harbor.models.task.paths import TaskPaths
            from harbor.models.task.verifier_mode import (
                resolve_task_verifier_mode,
                resolve_verifier_environment_definition,
            )

            for task in tasks:
                config = TaskConfig.model_validate(
                    tomllib.loads((task / "task.toml").read_text())
                )
                self.assertEqual(resolve_task_verifier_mode(config).value, "separate")
                definition = resolve_verifier_environment_definition(
                    config, TaskPaths(task)
                )
                self.assertEqual(definition.directory, task / "tests")
                self.assertTrue(definition.bundled_tests)
                self.assertEqual(config.artifacts[0].source, "/workspace/pkg")
                agent = yaml.safe_load(
                    (task / "environment/docker-compose.yaml").read_text()
                )
                verifier = yaml.safe_load(
                    (task / "tests/docker-compose.yaml").read_text()
                )
                self.assertNotIn("volumes", agent["services"]["main"])
                self.assertNotIn("verifier", agent.get("volumes", {}))
                self.assertEqual(set(verifier["services"]), {"main"})
                self.assertNotIn(
                    "token", (task / "environment/docker-compose.yaml").read_text()
                )
                self.assertIn(
                    "grade --package /workspace/pkg",
                    (task / "tests/test.sh").read_text(),
                )

            def snapshot():
                return {
                    str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in root.rglob("*")
                    if p.is_file()
                }

            before = snapshot()
            actual_run = subprocess.run
            prepares = 0

            def fail_second(command, **kwargs):
                nonlocal prepares
                if "v2w.agents.run" in command:
                    prepares += 1
                    if prepares == 2:
                        raise subprocess.CalledProcessError(23, command)
                return actual_run(command, **kwargs)

            adapter.overwrite = True
            with (
                patch("video2world.adapter.subprocess.run", side_effect=fail_second),
                self.assertRaises(subprocess.CalledProcessError),
            ):
                adapter.run()
            self.assertEqual(snapshot(), before)
            adapter.limit = 1
            adapter.run()
            self.assertTrue(tasks[0].exists())
            self.assertFalse(tasks[1].exists())
            self.assertEqual(
                len(
                    json.loads((root / "selection.json").read_text())["configurations"]
                ),
                1,
            )


class OracleConverterTests(unittest.TestCase):
    def test_cloth_conversion_produces_valid_camera_package(self):
        import numpy as np

        from video2world.oracle import populate_oracle

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = root / "sample"
            gt = sample / "gt_pkg"
            (sample / "hidden").mkdir(parents=True)
            gt.mkdir(parents=True)
            (sample / "video.mp4").write_bytes(b"mp4")
            (gt / "report.md").write_text("ok\n")
            T = np.array(
                [
                    [0.0, -1.0, 0.0, 0.5],
                    [1.0, 0.0, 0.0, -0.2],
                    [0.0, 0.0, 1.0, 1.0],
                    [0.0, 0.0, 0.0, 1.0],
                ]
            )
            (sample / "hidden/camera.json").write_text(
                json.dumps({"extrinsics_base_cam": T.tolist()})
            )
            (gt / "scene.json").write_text(
                json.dumps(
                    {
                        "gravity": "table_normal",
                        "table": {"point": [0.3, 0.0, -0.1], "normal": [0.0, 0.0, 1.0], "z": -0.1},
                        "cloth": {
                            "corners": [[0.2, -0.1, -0.1], [0.4, -0.1, -0.1], [0.4, 0.1, -0.1], [0.2, 0.1, -0.1]],
                            "grid": [5, 5],
                            "mass": 0.05,
                            "friction": 1.0,
                            "young": 1e5,
                            "poisson": 0.3,
                            "thickness": 0.001,
                            "yaw": 0.0,
                        },
                    }
                )
            )
            tcp = np.repeat(np.eye(4)[None], 3, axis=0)
            np.savez(
                gt / "actions.npz",
                tcp_pose=tcp,
                gripper_closure=np.array([0.0, 0.8, 0.2]),
                fps=np.array(15.0),
            )
            sol = root / "solution"
            ok = populate_oracle("cloth", "droid_cloth", sample, sol)
            self.assertTrue(ok)
            self.assertTrue((sol / "pkg/source/video.mp4").is_file())
            self.assertIn("cp -a", (sol / "solve.sh").read_text())
            self.assertNotIn("/logs/verifier", (sol / "solve.sh").read_text())
            proto = json.loads((sol / "pkg/protocol.json").read_text())
            self.assertEqual(proto["physics_profile"], "droid-cloth-camera/1")
            scene = json.loads((sol / "pkg/scene.json").read_text())
            self.assertEqual(set(scene["table"]), {"point", "normal"})
            self.assertNotIn("yaw", scene["cloth"])

    def test_non_convertible_evaluator_exits_nonzero(self):
        from video2world.oracle import populate_oracle

        for evaluator, profile in (
            ("inhouse", "inhouse_provider_native_v2"),
            ("ego_arm", "ego_arm"),
            ("ego_bimanual", "ego_bimanual"),
            ("twin", "twin_rope"),
            ("twin_toy", "twin_toy"),
            ("fb", "fb_lamp"),
            ("fb", "fb_furniture"),
        ):
            with self.subTest(evaluator=evaluator, profile=profile), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                sol = root / "solution"
                ok = populate_oracle(evaluator, profile, root, sol)
                self.assertFalse(ok)
                self.assertFalse((sol / "pkg").exists())
                self.assertIn("exit 1", (sol / "solve.sh").read_text())

    def test_fb_supported_profiles_remap_robot_uid(self):
        from video2world.oracle import populate_oracle

        for profile, expected_uid in (("fb_pusht", "xarm7_pusher"), ("fb_droid", "panda_robotiq")):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                sample = root / "sample"
                (sample / "gt_pkg").mkdir(parents=True)
                (sample / "gt_pkg/protocol.json").write_text(
                    json.dumps({"robot": {"uid": "widowx250s_bridge", "base_pose": [0, 0, 0, 1, 0, 0, 0]}})
                )
                sol = root / "solution"
                ok = populate_oracle("fb", profile, sample, sol)
                self.assertTrue(ok)
                proto = json.loads((sol / "pkg/protocol.json").read_text())
                self.assertEqual(proto["robot"]["uid"], expected_uid)
                self.assertIn("cp -a", (sol / "solve.sh").read_text())

    def test_inhouse_candidate_evaluators_copy_candidate_dir(self):
        from video2world.oracle import INHOUSE_CANDIDATE_EVALUATORS, populate_oracle

        for evaluator in sorted(INHOUSE_CANDIDATE_EVALUATORS):
            with self.subTest(evaluator=evaluator), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                sample = root / "sample"
                (sample / "candidate").mkdir(parents=True)
                (sample / "candidate/protocol.json").write_text(
                    json.dumps({"physics_profile": "inhouse_camera_native_v1"})
                )
                sol = root / "solution"
                ok = populate_oracle(evaluator, "inhouse_provider_native_v2", sample, sol)
                self.assertTrue(ok)
                self.assertTrue((sol / "pkg/protocol.json").is_file())
                self.assertIn("cp -a", (sol / "solve.sh").read_text())

    def test_robodojo_usd_conversion_produces_camera_geometry_npz(self):
        import numpy as np
        from pxr import Gf, Usd, UsdGeom

        from video2world.oracle import populate_oracle

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = root / "sample"
            gt = sample / "gt_pkg"
            (sample / "hidden").mkdir(parents=True)
            (gt / "assets/block").mkdir(parents=True)
            usd_file = gt / "assets/block/object.usda"
            stage = Usd.Stage.CreateNew(str(usd_file))
            UsdGeom.Xform.Define(stage, "/root")
            mesh = UsdGeom.Mesh.Define(stage, "/root/visual")
            mesh.CreatePointsAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(0.1, 0, 0), Gf.Vec3f(0, 0.2, 0), Gf.Vec3f(0, 0, 0.3)])
            mesh.CreateFaceVertexCountsAttr([3, 3])
            mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 0, 1, 3])
            stage.GetRootLayer().Save()

            np.save(gt / "actions.npy", np.zeros((3, 14), dtype=np.float32))
            np.savez(
                gt / "assets/table.npz",
                vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32),
                face_vertex_counts=np.array([3], dtype=np.int32),
                face_vertex_indices=np.array([0, 1, 2], dtype=np.int32),
            )
            T_wc = np.eye(4)
            T_wc[:3, 3] = [0.0, -0.5, 1.0]
            (sample / "hidden/camera.json").write_text(json.dumps({"camera_to_world_ros": T_wc.tolist()}))
            (gt / "protocol.json").write_text(
                json.dumps(
                    {
                        "protocol_version": "3.0",
                        "physics_profile": "robodojo_candidate_task_v1",
                        "task": "test_task",
                        "embodiment": "x5",
                        "actions": {"path": "actions.npy", "format": "dual_joint_position_gripper01", "dt": 0.04},
                    }
                )
            )
            (gt / "scene.json").write_text(
                json.dumps(
                    {
                        "camera": {"focal_px": 288.0},
                        "objects": [
                            {
                                "name": "block",
                                "asset_path": "assets/block/object.usda",
                                "pos": [0.0, 0.0, 0.5],
                                "quat_wxyz": [1.0, 0.0, 0.0, 0.0],
                                "size": [0.1, 0.2, 0.3],
                                "scale": [1.0, 1.0, 1.0],
                                "color": [1.0, 0.0, 0.0],
                                "mass": 0.2,
                            }
                        ],
                        "props": [],
                        "table": {
                            "name": "table",
                            "geometry_npz": "assets/table.npz",
                            "pos": [0.0, 0.0, 0.0],
                            "quat_wxyz": [1.0, 0.0, 0.0, 0.0],
                            "size": [1.0, 1.0, 0.05],
                            "scale": [1.0, 1.0, 1.0],
                            "color": [0.5, 0.5, 0.5],
                            "mass": 0.0,
                        },
                    }
                )
            )
            sol = root / "solution"
            ok = populate_oracle("robodojo_native_task", "robodojo_candidate_task_v1", sample, sol)
            self.assertTrue(ok)
            proto = json.loads((sol / "pkg/protocol.json").read_text())
            self.assertEqual(proto["physics_profile"], "robodojo_camera_task_v1")
            self.assertEqual(proto["frame"], "camera_opencv")
            scene = json.loads((sol / "pkg/scene.json").read_text())
            self.assertNotIn("asset_path", scene["objects"][0])
            self.assertEqual(scene["objects"][0]["geometry_npz"], "assets/block.npz")
            self.assertTrue((sol / "pkg/assets/block.npz").is_file())
            self.assertEqual(scene["table"]["mass"], 0.1)
            np.testing.assert_allclose(scene["objects"][0]["pos"], [0.0, 0.5, -0.5])

    def test_decimate_mesh_reduces_high_poly_geometry(self):
        import numpy as np

        from video2world.oracle import _decimate_mesh

        # Build a 6,000-triangle grid (> max_faces=4000) and confirm decimation reduces faces.
        gx, gy = np.meshgrid(np.linspace(0, 1, 56), np.linspace(0, 1, 56))
        verts = np.c_[gx.ravel(), gy.ravel(), np.sin(gx.ravel() * 3.0)].astype(np.float32)
        tris = []
        for r in range(55):
            for c in range(55):
                i = r * 56 + c
                tris.append([i, i + 1, i + 56])
                tris.append([i + 1, i + 57, i + 56])
        faces = np.asarray(tris, dtype=np.int32)
        counts = np.full(len(faces), 3, dtype=np.int32)
        dv, dc, di = _decimate_mesh(verts, counts, faces.reshape(-1), max_faces=1000)
        self.assertLessEqual(len(dc), 1000)
        self.assertEqual(len(di), len(dc) * 3)
        self.assertTrue(np.all(di >= 0) and np.all(di < len(dv)))


if __name__ == "__main__":
    unittest.main()
