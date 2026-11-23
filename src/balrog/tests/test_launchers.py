"""Launcher selection/configuration tests; never start Docker, an agent or an API."""

from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
import parity_launch as launch
import run_harbor
import run_native


PLAN = PROJECT / "parity/plan.proposed.json"
SETTINGS = PROJECT / "parity/settings.proposed.json"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="balrog-launcher-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def make_dataset(self, episodes, *, legacy_babyai=True):
        dataset = self.root / "dataset"
        for episode in episodes:
            task = dataset / episode["task_id"]
            payload = dict(episode)
            if legacy_babyai and episode["env_name"] == "babyai":
                payload.pop("env_name")
            for relative in ("environment/episode.json", "tests/task_config.json"):
                write_json(task / relative, payload)
            (task / "task.toml").write_text(
                f'[task]\nname = "balrog/{episode["task_id"]}"\n[verifier]\nenvironment_mode = "separate"\n',
                encoding="utf-8")
            environment = task / "environment"
            for name in ("Dockerfile.game", "game_server.py", "export_result.py", "requirements-agent.lock",
                         "requirements-game.lock", "runtime-lock.json", "runtime_guard.py", "apt-game.lock"):
                (environment / name).write_text("test input\n", encoding="utf-8")
            (environment / "vendor").mkdir()
            (environment / "vendor/sources.tar.gz").write_bytes(b"test source")
        return dataset

    def test_exact_plan_ten_and_original_full_255_and_legacy_58(self):
        expected = launch.read_json(PLAN)
        sanity, full, legacy = [], [], []
        for env in launch.ENVIRONMENTS:
            selected, metadata = launch.select_episodes(env, selection_plan=PLAN)
            sanity += [e["task_id"] for e in selected]
            self.assertEqual(metadata["global_selected_task_count"], 10)
            self.assertEqual(metadata["episodes"], len(selected))
            all_cases, _ = launch.select_episodes(env, "full", selection_plan=PLAN)
            same, _ = launch.select_episodes(env, "parity", selection_plan=PLAN)
            self.assertEqual(all_cases, same)
            self.assertEqual([e["task_id"] for e in all_cases], expected["scope"]["environments"][env]["task_ids"])
            full += all_cases
            legacy += launch.select_episodes(env)[0]
        self.assertEqual(sanity, expected["scope"]["sanity_task_ids"])
        self.assertEqual(len(full), 255)
        self.assertEqual(len(legacy), 58)

    def test_invalid_scope_ids_duplicates_hashes_and_sanity_are_rejected(self):
        mutations = (
            lambda p: p["scope"]["sanity_task_ids"].__setitem__(0, "not-a-task"),
            lambda p: p["scope"]["sanity_task_ids"].__setitem__(0, p["scope"]["sanity_task_ids"][1]),
            lambda p: p["scope"]["environments"].pop("nle"),
            lambda p: p["scope"]["environments"]["nle"].update(manifest_sha256="0" * 64),
            lambda p: p["scope"]["environments"]["nle"].update(native_action_budget_per_full_run=500),
            lambda p: p["scope"]["sanity_task_ids"].__setitem__(0, "babyai-goto-seed-1"),
        )
        for mutate in mutations:
            plan = launch.read_json(PLAN)
            mutate(plan)
            path = self.root / "invalid.json"
            write_json(path, plan)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                launch.select_episodes("babyai", selection_plan=path)

    def test_explicit_ids_reject_wrong_scope_and_keep_manifest_order(self):
        path = self.root / "ids.json"
        for ids in (["unknown-task"], ["babyai-goto-seed-0"] * 2, [],
                    ["nle-nethackchallenge-v0-seed-0"], ["babyai-goto-seed-1"]):
            write_json(path, ids)
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                launch.select_episodes("babyai", task_ids_file=path)
        write_json(path, ["babyai-putnext-seed-0", "babyai-goto-seed-0"])
        rows, _ = launch.select_episodes("babyai", task_ids_file=path)
        self.assertEqual([r["task_id"] for r in rows], ["babyai-goto-seed-0", "babyai-putnext-seed-0"])

    def test_dataset_must_match_selection_and_native_metadata(self):
        episodes, _ = launch.select_episodes("babyai", selection_plan=PLAN)
        dataset = self.make_dataset(episodes)
        self.assertEqual(set(launch.validate_dataset(dataset, episodes)), {e["task_id"] for e in episodes})
        with self.assertRaises(ValueError):
            launch.validate_dataset(dataset, episodes[:1])
        wrong = copy.deepcopy(episodes[0]); wrong["seed"] = 9
        write_json(dataset / episodes[0]["task_id"] / "tests/task_config.json", wrong)
        with self.assertRaises(ValueError):
            launch.validate_dataset(dataset, episodes)

    def test_native_cache_binds_exporter_new_locks_and_all_context_inputs(self):
        episodes, _ = launch.select_episodes("babyai", selection_plan=PLAN)
        dataset = self.make_dataset(episodes)
        directory = dataset / episodes[0]["task_id"] / "environment"
        previous = launch.native_build_provenance(directory, episodes)
        for name in ("export_result.py", "requirements-game.lock", "runtime-lock.json", "future-build-input.txt"):
            (directory / name).write_text("changed\n", encoding="utf-8")
            current = launch.native_build_provenance(directory, episodes)
            self.assertNotEqual(current["image"], previous["image"])
            self.assertIn(name, current["build_files_sha256"])
            previous = current
        write_json(directory / "episode.json", {**episodes[0], "expected_max_steps": 999})
        with self.assertRaises(ValueError):
            launch.native_build_provenance(directory, episodes)

    def test_native_preview_rejects_missing_locked_runtime_inputs(self):
        episodes, _ = launch.select_episodes("babyai", selection_plan=PLAN)
        dataset = self.make_dataset(episodes)
        directory = dataset / episodes[0]["task_id"] / "environment"
        for name in ("runtime_guard.py", "runtime-lock.json", "requirements-game.lock", "apt-game.lock"):
            path = directory / name
            content = path.read_bytes()
            path.unlink()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "missing a required runtime input"):
                launch.native_build_provenance(directory, episodes)
            path.write_bytes(content)

    def test_current_harbor_schema_keeps_deadlines_concurrency_and_no_retries(self):
        from harbor.models.job.config import JobConfig
        # The schema holds an agent configuration; it must not instantiate it.
        with patch("harbor.agents.factory.AgentFactory.create_agent_from_config", side_effect=AssertionError("agent launch")):
            job = launch.build_harbor_job(dataset=self.root, settings_path=SETTINGS, model_id="fake-model",
                jobs_dir=self.root / "jobs", job_name="test", concurrency=2, episode_timeout=700, collection_grace=120)
            parsed = JobConfig.model_validate(job)
        self.assertNotIn("orchestrator", job)
        self.assertEqual(parsed.n_concurrent_trials, 2)
        self.assertEqual(parsed.retry.max_retries, 0)
        self.assertEqual(job["agents"][0]["kwargs"]["execution_timeout_sec"], 700)
        self.assertEqual(job["agents"][0]["override_timeout_sec"], 820)
        self.assertEqual(job["environment"]["kwargs"], {"auto_mounting": False})

    def test_daytona_options_and_job_preview_never_construct_provider_or_read_keys(self):
        from harbor.environments.daytona import environment as daytona
        from harbor.models.job.config import JobConfig
        episodes, _ = launch.select_episodes("babyai", selection_plan=PLAN)
        dataset = self.make_dataset(episodes)
        output = io.StringIO()
        with patch.object(daytona.DaytonaEnvironment, "__init__", side_effect=AssertionError("provider construction")), \
                patch.object(daytona, "_daytona_preflight", side_effect=AssertionError("provider key read")), \
                patch.object(daytona.DaytonaClientManager, "get_instance", side_effect=AssertionError("cloud client")), \
                patch.object(run_harbor, "load_model_key", side_effect=AssertionError("model key read")), \
                patch.object(run_harbor.subprocess, "run", side_effect=AssertionError("subprocess")), redirect_stdout(output):
            run_harbor.main(["--dataset", str(dataset), "--settings", str(SETTINGS), "--jobs-dir", str(self.root / "jobs"),
                            "--job-name", "daytona-preview", "--selection-plan", str(PLAN), "--episode-timeout", "700",
                            "--environment-type", "daytona", "--dry-run"])
        preview = json.loads(output.getvalue())
        job = JobConfig.model_validate(preview["job"])
        options = daytona.DaytonaOptions.model_validate(job.environment.kwargs)
        self.assertEqual(job.environment.type, "daytona")
        self.assertFalse(options.auto_mounting)
        self.assertIsNone(options.secrets)
        self.assertEqual(preview["job"]["environment"]["kwargs"], {"auto_mounting": False})
        self.assertEqual(job.retry.max_retries, 0)
        self.assertEqual(preview["plan"]["environment_type"], "daytona")
        self.assertIn("runtime remains untested", preview["plan"]["platform_note"])
        self.assertFalse((self.root / "jobs").exists())

    def test_unknown_provider_rejected(self):
        with self.assertRaisesRegex(ValueError, "docker or daytona"):
            launch.build_harbor_job(dataset=self.root, settings_path=SETTINGS, model_id="fake-model",
                jobs_dir=self.root, job_name="test", environment_type="unknown")
        with patch.object(run_native.subprocess, "run", side_effect=AssertionError("subprocess")), \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            run_native.main(["--environment-dir", "unused", "--settings", str(SETTINGS), "--output-dir", "unused",
                             "--environment-type", "unknown", "--dry-run"])

    def test_both_dry_runs_validate_inputs_without_secrets_writes_or_subprocesses(self):
        episodes, _ = launch.select_episodes("babyai", selection_plan=PLAN)
        dataset = self.make_dataset(episodes)
        common = ["--settings", str(SETTINGS), "--selection-plan", str(PLAN), "--dry-run"]
        native_args = ["--environment-dir", str(dataset / episodes[0]["task_id"] / "environment"),
                       "--output-dir", str(self.root / "native-output"), *common]
        harbor_args = ["--dataset", str(dataset), "--jobs-dir", str(self.root / "jobs"), "--job-name", "preview", *common]
        with patch.object(run_native.subprocess, "run", side_effect=AssertionError("subprocess")), \
             patch.object(run_native, "load_model_key", side_effect=AssertionError("secret read")), \
             patch.object(run_harbor, "load_model_key", side_effect=AssertionError("secret read")):
            native_out, harbor_out = io.StringIO(), io.StringIO()
            with redirect_stdout(native_out):
                run_native.main(native_args)
            with redirect_stdout(harbor_out):
                run_harbor.main(harbor_args)
        native, harbor = json.loads(native_out.getvalue()), json.loads(harbor_out.getvalue())
        self.assertEqual(native["task_ids"], harbor["plan"]["task_ids"])
        self.assertEqual(native["environment_type"], "docker")
        self.assertEqual(harbor["plan"]["environment_type"], "docker")
        self.assertFalse(native["episode_timeout_confirmed"])
        self.assertFalse(harbor["plan"]["episode_timeout_confirmed"])
        self.assertIsNone(harbor["job"]["agents"][0]["override_timeout_sec"])
        self.assertFalse((self.root / "native-output").exists())
        self.assertFalse((self.root / "jobs").exists())

    def test_live_requires_explicit_timeout_before_any_secret_or_process(self):
        for module, argv in (
            (run_native, ["--environment-dir", "unused", "--settings", str(SETTINGS), "--output-dir", "unused"]),
            (run_harbor, ["--dataset", "unused", "--settings", str(SETTINGS), "--jobs-dir", "unused", "--job-name", "test"]),
        ):
            with self.subTest(module=module.__name__), patch.object(module, "load_model_key", side_effect=AssertionError("secret read")), \
                    patch.object(module.subprocess, "run", side_effect=AssertionError("subprocess")), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                module.main(argv)
        for value in (0, -1, True):
            with self.assertRaises(ValueError):
                launch.validate_timeout(value, dry_run=True)

    def test_installed_harbor_cli_module_help_is_executable(self):
        # This launches only CLI help, not a job or environment; catches absent
        # harbor.__main__ even when every configuration-only test would pass.
        completed = subprocess.run([sys.executable, "-m", "harbor.cli.main", "--help"],
                                   capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Usage", completed.stdout)

    def test_live_command_uses_verified_cli_entrypoint_with_fake_process(self):
        episodes, _ = launch.select_episodes("babyai", selection_plan=PLAN)
        dataset = self.make_dataset(episodes)
        jobs = self.root / "jobs"
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            self.assertEqual(command[:5], [sys.executable, "-m", "harbor.cli.main", "run", "-c"])
            config = launch.read_json(command[5])
            write_json(jobs / "fake-run/result.json", {"finished_at": "unit-test-only",
                "stats": {"n_errored_trials": 0, "n_retries": 0, "n_completed_trials": len(episodes)}})
            self.assertEqual(config["retry"]["max_retries"], 0)

        with patch.object(run_harbor.subprocess, "run", side_effect=fake_run), \
                patch.object(run_harbor, "load_model_key", return_value="unit-test-placeholder"):
            run_harbor.main(["--dataset", str(dataset), "--settings", str(SETTINGS), "--jobs-dir", str(jobs),
                            "--job-name", "fake-run", "--selection-plan", str(PLAN), "--episode-timeout", "700"])
        self.assertEqual(len(calls), 1)
        self.assertTrue((jobs / "fake-run.launch-plan.json").is_file())

    def test_secret_bearing_or_placeholder_settings_fail_before_execution(self):
        for mutate in (
            lambda s: s["client"].update(api_key="do-not-read-or-print"),
            lambda s: s["client"].update(model_id="REPLACE_MODEL"),
            lambda s: s.update(api_base_url="https://user:password@example.test/v1"),
            lambda s: s.update(api_base_url="https://example.test/v1?key=value"),
            lambda s: s.update(api_base_url=" https://example.test/v1"),
            lambda s: s.update(api_base_url="https://example.test/\nv1"),
            lambda s: s.pop("api_base_url"),
            lambda s: s["agent"].update(type="other-agent"),
            lambda s: s["agent"].update(max_image_history=1),
            lambda s: s["client"].update(client_name="unsupported"),
            lambda s: s["client"].update(model_id="TODO"),
            lambda s: s["client"].update(model_id="YOUR_MODEL"),
            lambda s: s["client"].update(model_id="<model>"),
            lambda s: s["limits"].update(max_model_calls=0),
            lambda s: s["client"].update(max_retries=True),
            lambda s: s["client"].update(max_retries=0),
            lambda s: s["client"].update(delay=-1),
            lambda s: s["client"]["generate_kwargs"].update(temperature=float("nan")),
            lambda s: s["client"]["generate_kwargs"].update(max_tokens=0),
        ):
            settings = launch.read_json(SETTINGS); mutate(settings)
            path = self.root / "settings.json"; write_json(path, settings)
            with self.assertRaises(ValueError):
                launch.load_settings(path)

    def test_junction_detection_is_fail_closed_without_native_junction_creation(self):
        with patch.object(Path, "is_junction", return_value=True, create=True):
            with self.assertRaisesRegex(ValueError, "junctions"):
                launch.read_json(PLAN)


if __name__ == "__main__":
    unittest.main()
