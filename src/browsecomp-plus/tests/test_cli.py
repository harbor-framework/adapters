"""Offline regression coverage for migration entry points and data preparation."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from datasets import Dataset

from browsecomp_plus import main as cli


@pytest.fixture
def sample_dataset():
    return Dataset.from_list([{"query_id": str(index)} for index in range(40)])


def patch_generation(monkeypatch, dataset):
    monkeypatch.setattr(cli, "load_dataset", Mock(return_value=dataset))
    factory = Mock()
    factory.return_value.run.side_effect = lambda **kwargs: (
        len(factory.call_args.kwargs["dataset"]),
        0,
        len(factory.call_args.kwargs["dataset"]),
    )
    monkeypatch.setattr(cli, "BrowseCompPlusAdapter", factory)
    download = Mock(side_effect=AssertionError("Unexpected network download"))
    monkeypatch.setattr(cli, "snapshot_download", download)
    return factory, download


def test_default_output_is_relative_to_invocation_cwd(
    monkeypatch, tmp_path, sample_dataset
):
    factory, download = patch_generation(monkeypatch, sample_dataset)
    monkeypatch.chdir(tmp_path)
    cli.main(["--skip-download", "--limit", "1"])
    assert (
        factory.call_args.kwargs["output_dir"] == tmp_path / "datasets/browsecomp-plus"
    )
    download.assert_not_called()


def test_parity_split_keeps_first_thirty_historical_rows(
    monkeypatch, tmp_path, sample_dataset
):
    factory, _ = patch_generation(monkeypatch, sample_dataset)
    cli.main(["--output-dir", str(tmp_path), "--skip-download", "--split", "parity"])
    assert factory.call_args.kwargs["dataset"]["query_id"] == [
        str(index) for index in range(30)
    ]


def test_task_ids_and_limit_keep_dataset_order(monkeypatch, tmp_path, sample_dataset):
    factory, _ = patch_generation(monkeypatch, sample_dataset)
    cli.main(
        [
            "--output-dir",
            str(tmp_path),
            "--skip-download",
            "--task-ids",
            "8",
            "2",
            "--limit",
            "1",
            "--overwrite",
        ]
    )
    assert factory.call_args.kwargs["dataset"]["query_id"] == ["2"]
    factory.return_value.run.assert_called_once_with(overwrite=True)


def test_missing_task_ids_fail_before_download(monkeypatch, tmp_path, sample_dataset):
    _, download = patch_generation(monkeypatch, sample_dataset)
    with pytest.raises(ValueError, match="999"):
        cli.main(["--output-dir", str(tmp_path), "--task-ids", "2", "999"])
    download.assert_not_called()


def test_load_errors_are_not_reported_as_success(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli, "load_dataset", Mock(side_effect=OSError("dataset unavailable"))
    )
    with pytest.raises(OSError, match="dataset unavailable"):
        cli.main(["--output-dir", str(tmp_path), "--skip-download"])


def test_partial_generation_is_failure(monkeypatch, tmp_path, sample_dataset):
    factory, _ = patch_generation(monkeypatch, sample_dataset)
    factory.return_value.run.side_effect = None
    factory.return_value.run.return_value = (1, 0, 2)
    with pytest.raises(RuntimeError, match="generation incomplete"):
        cli.main(["--output-dir", str(tmp_path), "--skip-download", "--limit", "2"])


@pytest.mark.parametrize("arguments", [["--limit", "-1"], ["--sample-size", "0"]])
def test_invalid_sizes_fail_before_loading(monkeypatch, arguments):
    loader = Mock()
    monkeypatch.setattr(cli, "load_dataset", loader)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2
    loader.assert_not_called()


def test_generation_downloads_only_bm25_using_sdk(monkeypatch, tmp_path):
    def fake_download(**kwargs):
        bm25 = Path(kwargs["local_dir"]) / "bm25"
        bm25.mkdir(parents=True)
        (bm25 / "segments_1").write_text("fixture")

    download = Mock(side_effect=fake_download)
    monkeypatch.setattr(cli, "snapshot_download", download)
    cli.prepare_data(tmp_path)
    download.assert_called_once_with(
        repo_id="Tevatron/browsecomp-plus-indexes",
        repo_type="dataset",
        allow_patterns=["bm25/*"],
        local_dir=tmp_path / "indices",
    )


def test_offline_index_reuse_and_partial_copy_fallback(monkeypatch, tmp_path):
    source = tmp_path / "source"
    (source / "bm25").mkdir(parents=True)
    (source / "bm25/segments_1").write_text("fixture")
    output = tmp_path / "output"
    (output / "indices").mkdir(parents=True)
    download = Mock(side_effect=AssertionError("Unexpected network download"))
    monkeypatch.setattr(cli, "snapshot_download", download)
    # Existing partial target forces symlink creation to fail and copy fallback.
    cli.prepare_data(output, indices_dir=source)
    assert (output / "indices/bm25/segments_1").read_text() == "fixture"
    download.assert_not_called()


def test_invalid_explicit_indices_are_not_silently_skipped(tmp_path):
    with pytest.raises(FileNotFoundError, match="non-empty bm25"):
        cli.prepare_data(
            tmp_path / "output", indices_dir=tmp_path / "missing", skip_download=True
        )


def test_empty_download_is_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "snapshot_download", Mock())
    with pytest.raises(FileNotFoundError, match="produced no index files"):
        cli.prepare_data(tmp_path)


def test_installed_package_has_agent_and_required_resources():
    from importlib.resources import files

    package = files("browsecomp_plus")
    assert package.joinpath("deep_research_agent.py").is_file()
    assert package.joinpath("install-deep-research-agent.sh.j2").is_file()
    assert package.joinpath("task-template/environment/Dockerfile").is_file()


def test_agent_installer_renders_and_uploads_packaged_template(tmp_path):
    import asyncio
    from unittest.mock import AsyncMock

    pytest.importorskip("harbor")
    from browsecomp_plus.deep_research_agent import DeepResearchAgent

    agent = DeepResearchAgent(logs_dir=tmp_path, model_name="openai/gpt-4o")
    environment = Mock()
    environment.upload_file = AsyncMock()
    agent.exec_as_root = AsyncMock()
    asyncio.run(agent.install(environment))
    install_script = tmp_path / "install_deep_research_agent.sh"
    rendered = install_script.read_text()
    runner = rendered.split("<< 'RUNNER_EOF'\n", 1)[1].split("\nRUNNER_EOF", 1)[0]
    compile(runner, "run_deep_research_agent.py", "exec")
    assert "{% raw %}" not in rendered
    environment.upload_file.assert_awaited_once_with(
        source_path=install_script,
        target_path="/installed-agent/install_deep_research_agent.sh",
    )
    agent.exec_as_root.assert_awaited_once()
