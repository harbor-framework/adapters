"""Generate the reviewed three-row subset of ControlArena BigCodeBench honest mode."""

import hashlib
import io
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from urllib.request import urlopen

import pyarrow.parquet as pq
from control_arena import EvalMode
from control_arena.settings.bigcodebench.task.dataset import record_to_sample_factory
from filelock import FileLock

REVISION = "b74c0d0bf70d2c0bc459be537895cca163007f1a"
PARQUET_SHA256 = "d9a4965821c9507ebdfb551c288656b2d5fe553234f5183044333ca8a4018267"
URL = f"https://huggingface.co/datasets/bigcode/bigcodebench/resolve/{REVISION}/data/v0.1.4-00000-of-00001.parquet"
IDS = ("BigCodeBench/0", "BigCodeBench/1", "BigCodeBench/2")
TEMPLATE = Path(__file__).with_name("task-template")


def load_rows(source: Path | None) -> list[dict]:
    if source is None:
        with urlopen(URL, timeout=60) as response:
            data = response.read()
    else:
        data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != PARQUET_SHA256:
        raise ValueError("BigCodeBench source does not match the pinned v0.1.4 Parquet file")
    # These three reviewed IDs occupy the first three rows at the pinned revision.
    parquet = pq.ParquetFile(io.BytesIO(data))
    rows = next(parquet.iter_batches(batch_size=len(IDS))).to_pylist()
    if tuple(row["task_id"] for row in rows) != IDS:
        raise ValueError("Pinned BigCodeBench row IDs do not match their expected positions")
    return rows


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


class ControlArenaBigCodeBenchHonestAdapter:
    def __init__(
        self, output_dir: Path, limit: int | None = None, overwrite: bool = False,
        task_ids: list[str] | None = None, source_parquet: Path | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.source_parquet = source_parquet

    def run(self) -> list[Path]:
        if self.limit is not None and self.limit < 0:
            raise ValueError("--limit must be nonnegative")
        slugs = {key: "bigcodebench-honest-" + key.split("/")[1] for key in IDS}
        aliases = {alias: key for key, slug in slugs.items()
                   for alias in (key, slug, "control-arena/" + slug)}
        wanted = set(IDS)
        if self.task_ids is not None:
            unknown = set(self.task_ids).difference(aliases)
            if unknown:
                raise ValueError(f"Unknown BigCodeBench IDs: {sorted(unknown)}")
            wanted = {aliases[value] for value in self.task_ids}
        indices = [i for i, key in enumerate(IDS) if key in wanted][: self.limit]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if not indices:
            return []
        rows = load_rows(self.source_parquet)
        lock = hashlib.sha256(bytes(self.output_dir.resolve())).hexdigest()
        with FileLock(Path(gettempdir()) / f"harbor-bigcodebench-{lock}.lock"):
            return [self._generate(rows[i], slugs[IDS[i]]) for i in indices]

    def _generate(self, row: dict, slug: str) -> Path:
        destination = self.output_dir / slug
        origin = {"task_id": row["task_id"], "revision": REVISION, "mode": "honest"}
        if destination.exists() or destination.is_symlink() or destination.is_junction():
            provenance = destination / "tests" / "source.json"
            if (not provenance.is_file() or provenance.resolve() != self.output_dir.resolve() / slug / "tests/source.json"
                    or json.loads(provenance.read_text(encoding="utf-8")) != origin):
                raise ValueError(f"Destination belongs to a different task: {destination}")
            if not self.overwrite:
                return destination

        with TemporaryDirectory(dir=self.output_dir, prefix=".bcb-") as temp:
            stage = Path(temp) / "new"
            shutil.copytree(TEMPLATE, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            sample = record_to_sample_factory(EvalMode.HONEST, "full", "complete")(row)
            if isinstance(sample, list):
                raise ValueError(f"Missing native sample for {row['task_id']}")
            # Replace only the native submit-tool transport with Harbor's artifact.
            instruction = sample.metadata["setting_description"].replace(
                "Submit your solution using the submit tool.",
                "Write the Python code you would submit to /logs/artifacts/solution.py.",
            )
            write(stage / "instruction.md", instruction.rstrip() + "\n\n" + sample.input + "\n")
            config = stage / "task.toml"
            write(config, config.read_text(encoding="utf-8").replace("{task_id}", slug))
            # The honest scorer requires only the signature and tests. Its typed
            # metadata also declares canonical_solution, which honest mode never uses.
            sample.metadata["metadata"]["canonical_solution"] = ""
            write(stage / "tests" / "sample.json", sample.model_dump_json() + "\n")
            write(stage / "tests" / "source.json", json.dumps(origin) + "\n")
            write(stage / "solution" / "solution.py", row["canonical_solution"])
            for script in stage.rglob("*.sh"):
                write(script, script.read_text(encoding="utf-8"))
                script.chmod(0o755)
            previous = Path(temp) / "previous"
            if destination.exists():
                destination.rename(previous)
            try:
                stage.rename(destination)
            except OSError:
                if previous.exists():
                    previous.rename(destination)
                raise
        return destination
