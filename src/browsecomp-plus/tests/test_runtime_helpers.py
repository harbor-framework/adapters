"""Offline regressions for the migrated runtime and reproduction entry points."""

import contextlib
import importlib
import importlib.util
import io
import json
import os
import pickle
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ADAPTER_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = ADAPTER_ROOT / "src/browsecomp_plus/task-template/environment"


def module(name, **attributes):
    result = types.ModuleType(name)
    result.__dict__.update(attributes)
    return result


class RuntimeHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ENVIRONMENT))
        cls.implementation = importlib.import_module("skills.searchers.implementation")
        cls.faiss_searcher = importlib.import_module("skills.searchers.faiss_searcher")
        spec = importlib.util.spec_from_file_location(
            "browsecomp_tools_wrapper", ENVIRONMENT / "tools_wrapper.py"
        )
        cls.wrapper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.wrapper)

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(ENVIRONMENT))

    def test_empty_compose_values_use_runtime_defaults(self):
        tool = Mock()
        tool.search.return_value = [{"docid": "42", "text": "passage"}]
        output = io.StringIO()
        blank_values = {
            "SEARCH_AGENT_SEARCHER_TYPE": "",
            "SEARCH_AGENT_INDEX_PATH": "",
            "SEARCH_AGENT_K": "",
            "SEARCH_AGENT_SNIPPET_MAX_TOKENS": "",
        }
        with (
            patch.dict(os.environ, blank_values),
            patch.object(self.wrapper, "SearchTool", return_value=tool) as factory,
            patch.object(sys, "argv", ["search", "search", "a query"]),
            contextlib.redirect_stdout(output),
        ):
            self.wrapper.main()
        factory.assert_called_once_with(
            "bm25", "/app/indices/bm25", k=5, snippet_max_tokens=512
        )
        tool.search.assert_called_once_with("a query", k=None)
        self.assertEqual(json.loads(output.getvalue())[0]["docid"], "42")

    def test_explicit_runtime_values_preserve_zero_snippet_limit(self):
        tool = Mock()
        tool.search.return_value = []
        values = {
            "SEARCH_AGENT_SEARCHER_TYPE": "bm25",
            "SEARCH_AGENT_INDEX_PATH": "/corpus/bm25",
            "SEARCH_AGENT_K": "7",
            "SEARCH_AGENT_SNIPPET_MAX_TOKENS": "0",
        }
        with (
            patch.dict(os.environ, values),
            patch.object(self.wrapper, "SearchTool", return_value=tool) as factory,
            patch.object(sys, "argv", ["search", "search", "a query", "--k", "2"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.wrapper.main()
        factory.assert_called_once_with(
            "bm25", "/corpus/bm25", k=7, snippet_max_tokens=0
        )
        tool.search.assert_called_once_with("a query", k=2)

    def test_existing_bm25_index_needs_no_download(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "bm25"
            index.mkdir()
            (index / "segments_1").write_text("offline fixture")
            with patch.dict(sys.modules, {"huggingface_hub": None}):
                result = self.implementation.SearchTool._ensure_bm25_index(
                    object(), str(index)
                )
            self.assertEqual(result, str(index))

    def test_missing_bm25_index_download_uses_shared_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "indices" / "bm25"

            def download(**kwargs):
                index.mkdir()
                (index / "segments_1").write_text("downloaded offline fixture")

            snapshot_download = Mock(side_effect=download)
            with (
                patch.dict(
                    sys.modules,
                    {
                        "huggingface_hub": module(
                            "huggingface_hub", snapshot_download=snapshot_download
                        )
                    },
                ),
                patch.dict(os.environ, {"SEARCH_AGENT_INDEX_REPO_ID": "test/corpus"}),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = self.implementation.SearchTool._ensure_bm25_index(
                    object(), str(index)
                )
            self.assertEqual(result, str(index))
            snapshot_download.assert_called_once_with(
                repo_id="test/corpus",
                repo_type="dataset",
                allow_patterns=["bm25/*"],
                local_dir=str(index.parent),
            )

    def test_missing_bm25_index_after_download_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot_download = Mock()
            with (
                patch.dict(
                    sys.modules,
                    {
                        "huggingface_hub": module(
                            "huggingface_hub", snapshot_download=snapshot_download
                        )
                    },
                ),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaisesRegex(FileNotFoundError, "missing or empty"),
            ):
                self.implementation.SearchTool._ensure_bm25_index(
                    object(), str(Path(directory) / "bm25")
                )

    def test_reasonir_initialization_dispatches_to_its_own_model_loader(self):
        loaded_model = Mock()
        loaded_model.to.return_value = loaded_model
        auto_model = Mock()
        auto_model.from_pretrained.return_value = loaded_model
        dense_model = Mock()
        dense_model.load.side_effect = AssertionError(
            "ReasonIR must not load DenseModel"
        )
        flat_searcher = Mock(return_value=Mock())
        dependencies = {
            "faiss": module("faiss", get_num_gpus=lambda: 0),
            "numpy": module("numpy", array=lambda value: value),
            "datasets": module(
                "datasets",
                load_dataset=Mock(return_value=[{"docid": "42", "text": "passage"}]),
            ),
            "torch": module(
                "torch",
                float16="float16",
                cuda=types.SimpleNamespace(is_available=lambda: False),
            ),
            "transformers": module("transformers", AutoModel=auto_model),
            "tevatron": module("tevatron"),
            "tevatron.retriever": module("tevatron.retriever"),
            "tevatron.retriever.arguments": module(
                "tevatron.retriever.arguments", ModelArguments=types.SimpleNamespace
            ),
            "tevatron.retriever.searcher": module(
                "tevatron.retriever.searcher", FaissFlatSearcher=flat_searcher
            ),
            "tevatron.retriever.driver": module("tevatron.retriever.driver"),
            "tevatron.retriever.driver.encode": module(
                "tevatron.retriever.driver.encode", DenseModel=dense_model
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "corpus.pkl"
            index.write_bytes(pickle.dumps(([[1.0, 2.0]], ["42"])))
            args = types.SimpleNamespace(
                index_path=str(index),
                model_name="reasonir-fixture",
                normalize=False,
                pooling="eos",
                torch_dtype="float16",
                dataset_name="fixture-corpus",
            )
            with (
                patch.dict(sys.modules, dependencies),
                patch.dict(os.environ, {"HF_HOME": "/cache"}),
            ):
                searcher = self.faiss_searcher.ReasonIrSearcher(args)
        auto_model.from_pretrained.assert_called_once_with(
            "reasonir-fixture",
            cache_dir="/cache",
            torch_dtype="float16",
            trust_remote_code=True,
        )
        dense_model.load.assert_not_called()
        loaded_model.eval.assert_called_once_with()
        self.assertIs(searcher.model, loaded_model)
        self.assertEqual(
            searcher.get_document("42"), {"docid": "42", "text": "passage"}
        )
        self.assertEqual(searcher.lookup, ["42"])

    def test_reproduction_clis_import_and_show_help_without_optional_backends(self):
        # Imports are stubbed rather than installing CUDA, Java, or model packages.
        # argparse exits before clients, models, corpus downloads, or judges run.
        dependencies = {
            "numpy": module("numpy"),
            "openai": module("openai", OpenAI=Mock()),
            "tqdm": module("tqdm", tqdm=Mock()),
            "rich": module("rich", print=print),
            "vllm": None,
            "faiss": None,
            "torch": None,
            "tevatron": None,
            "pyserini": None,
            "transformers": None,
        }
        paths = [
            "origin_agents/openai_client.py",
            "scripts_evaluation/evaluate_run.py",
            "scripts_evaluation/evaluate_with_openai.py",
            "origin_agents/scripts_evaluation/evaluate_run.py",
            "origin_agents/scripts_evaluation/evaluate_with_openai.py",
            "origin_agents/scripts_evaluation/evaluate_run_openai.py",
        ]
        for relative in paths:
            with self.subTest(entrypoint=relative):
                output = io.StringIO()
                with (
                    patch.dict(sys.modules, dependencies),
                    patch.object(sys, "path", list(sys.path)),
                    patch.object(sys, "argv", [relative, "--help"]),
                    contextlib.redirect_stdout(output),
                    self.assertRaises(SystemExit) as result,
                ):
                    runpy.run_path(str(ADAPTER_ROOT / relative), run_name="__main__")
                self.assertEqual(result.exception.code, 0)
                self.assertIn("usage:", output.getvalue())
                dependencies["openai"].OpenAI.assert_not_called()

        # Module invocation previously broke on top-level prompts/utils imports.
        with (
            patch.dict(sys.modules, dependencies),
            patch.object(sys, "path", [str(ADAPTER_ROOT), *sys.path]),
            patch.object(sys, "argv", ["origin_agents.openai_client", "--help"]),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as result,
        ):
            runpy.run_module("origin_agents.openai_client", run_name="__main__")
        self.assertEqual(result.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
