"""SUPER-Expert builder (AstaBench `super_test`, SUPER "Expert" split).

Each SUPER Expert sample describes a research-repository task (set up the
repo, run an experiment) and asks for the result in a stated JSON shape.

Scoring mirrors upstream `check_super_execution` from
astabench/evals/super/task.py (allenai/asta-bench, vendored at fork commit
17c84ca; the file is unchanged from upstream main).  The Harbor reward is
`output_match`, the primary metric AstaBench's suite config uses for
`SUPER_Expert_test` (`astabench/config/v1.0.0.yml`: `output_match/mean`).

SUPER "Auto" split (AstaBench `super_validation`) is EXCLUDED
---------------------------------------------------------------
Upstream scores Auto with `check_super_auto` -> `evaluate_entrypoints()`,
which rewards any execution-history step that mentions the entrypoint file,
lasts >= 10 s and shows no "Traceback".  That history comes either from the
agent's own answer JSON (`parse_super_output` Case 1: `{"submitted": ...,
"history": [...]}`) or from `jupyter_cell_history.json`, which the sandbox
Jupyter server writes in the agent's own working directory.  Both are
agent-writable, so the Auto metric cannot be made unforgeable in Harbor while
staying faithful to upstream.  The builder therefore generates no tasks for
the `validation` split: it raises `SplitNotAvailable` (see
`SuperExpertBuilder.load_samples`).

`pre_execute_cells`: upstream only copies them into `Sample.metadata`; nothing
executes them, and no Expert sample has any, so the adapter ignores them.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from hashlib import md5
from pathlib import Path

from .base import (
    INSPECT_DEFAULT_EVAL_ARGS,
    VERIFIER_TEST_SH,
    BenchmarkBuilder,
    SampleRecord,
    SplitNotAvailable,
    make_inspect_config,
    write_task_files,
)

_INSPECT_TASK = "astabench/super_test"

# Upstream's super_test declares sandbox=("docker", ...) for the agent's
# python_session.  We override with --sandbox local so the agent's code runs
# inside the harbor task container itself, whose image mirrors upstream's
# sandbox image (see DOCKERFILE below).
_BRIDGE_EVAL_ARGS = INSPECT_DEFAULT_EVAL_ARGS + ["--sandbox", "local"]


TASK_TOML_TEMPLATE = """\
schema_version = "1.0"

[task]
name = "{task_name}"
authors = [
    {{ name = "Allen Institute for AI (AstaBench)", email = "asta@allenai.org" }},
    {{ name = "Ben Bogin et al. (SUPER, arXiv:2409.07440)" }},
]
keywords = ["ml-experiments", "code-execution", "research-reproduction", "expert"]

[metadata]
category = "code-execution"
family = "super-expert"
split = "{split}"
source_sample_id = "{source_id}"

[agent]
timeout_sec = 7200

[verifier]
timeout_sec = 60

[environment]
build_timeout_sec = 1800.0
cpus = 4
memory_mb = 8192
storage_mb = 10240
# Internet is required: nothing task-specific is bundled in the image.  Every
# SUPER task asks the agent to `git clone` a research repository, pip-install
# its dependencies and download data/checkpoints (GitHub, PyPI, Google Drive,
# Hugging Face), exactly as upstream's sandbox (network_mode: bridge) allows.
# In Harbor's Docker environment allow_internet=false means network_mode:
# none, which would also cut the agent off from its model API.
allow_internet = true
"""


# Upstream sandbox requirement files, vendored verbatim from
# astabench/util/sandbox/{ds1000,super,diagnostics}_requirements.txt
# (allenai/asta-bench @ 645722c, the last commit touching that directory).
# Upstream builds ONE shared sandbox image for all code families and installs
# all three files, in this order; we do the same so agent code sees the same
# package versions.
DS1000_REQUIREMENTS_TXT = """\
# Dependencies for evaluations of generated code.

# Use cpu version of torch
--index-url https://download.pytorch.org/whl/cpu
--extra-index-url https://pypi.org/simple

gensim==4.3.2
matplotlib==3.8.4
numpy==1.26.4
pandas==1.5.3
seaborn==0.13.2
scikit-learn==1.4.0
scipy==1.12.0
statsmodels==0.14.1
xgboost==2.0.3
PyYAML==6.0.2
torch==2.2.0
tensorflow-cpu==2.16.1 ; platform_machine == 'x86_64'
tensorflow==2.16.1 ; platform_machine != 'x86_64'

"""

SUPER_REQUIREMENTS_TXT = """\
--extra-index-url https://download.pytorch.org/whl/cpu
libclang==18.1.1
tqdm==4.66.4
transformers==4.40.2
urllib3==2.0.7
termcolor==2.4.0
text-unidecode==1.3
spacy==3.7.4
regex==2023.12.25
requests==2.31.0
requests-oauthlib==1.3.1
build==1.2.1
cmake==3.27.9
Cython==3.0.10
en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl#sha256=86cc141f63942d4b2c5fcee06630fd6f904788d2f0ab005cce45aadb8fb73889
nltk==3.8.1
tensorboard==2.15.2
gdown==5.1.0
tweepy==4.14.0
sklearn-pandas==2.2.0
sympy==1.12
jieba==0.42.1
hyperopt==0.2.7
fsspec==2023.6.0
jsonpickle==3.0.4
mlflow
"""

DIAGNOSTICS_REQUIREMENTS_TXT = """\
nltk==3.9.1
transformers==4.40.2
datasets==3.6.0
gensim==4.3.2
spacy==3.8.7
scikit-learn==1.4.0
torch==2.2.2
sympy==1.14.0
pandas==2.2.2
matplotlib==3.8.4
networkx==3.2.1
scipy==1.15.3
seaborn==0.13.2
graphviz==0.20.3
torchdata==0.11.0
mpmath==1.3.0
jinja2==3.1.6
tokenizers==0.19.1
tqdm
numpy==1.26.4
dill==0.3.8
pyarrow==20.0.0
safetensors==0.5.3
pyparsing==3.2.3
psutil==7.0.0
"""

_REQUIREMENTS_FILES = {
    "ds1000_requirements.txt": DS1000_REQUIREMENTS_TXT,
    "super_requirements.txt": SUPER_REQUIREMENTS_TXT,
    "diagnostics_requirements.txt": DIAGNOSTICS_REQUIREMENTS_TXT,
}
_REQUIREMENTS_DIR = "sandbox_requirements"


# Mirrors upstream's sandbox image (astabench/util/sandbox/Dockerfile @
# 645722c): python:3.11-bookworm (ships git, curl, wget and a C toolchain),
# the three pinned requirement files in upstream's order, then the
# system-env Jupyter / matplotlib / mcp pins.  Upstream's
# /opt/inspect_tool_support venv is Inspect tool plumbing, not agent
# environment; the bridge runtime layer appended by base.py
# (`wire_inspect_bridge_runtime`) creates it for bridge datasets.
DOCKERFILE = f"""\
FROM python:3.11-bookworm

WORKDIR /app

COPY {_REQUIREMENTS_DIR}/ds1000_requirements.txt /opt/{_REQUIREMENTS_DIR}/
RUN pip install --no-cache-dir -r /opt/{_REQUIREMENTS_DIR}/ds1000_requirements.txt

COPY {_REQUIREMENTS_DIR}/super_requirements.txt /opt/{_REQUIREMENTS_DIR}/
RUN pip install --no-cache-dir -r /opt/{_REQUIREMENTS_DIR}/super_requirements.txt

COPY {_REQUIREMENTS_DIR}/diagnostics_requirements.txt /opt/{_REQUIREMENTS_DIR}/
RUN pip install --no-cache-dir -r /opt/{_REQUIREMENTS_DIR}/diagnostics_requirements.txt

RUN pip install jupyterlab==4.4.3 jupyter_kernel_gateway==3.0.1 numpy pandas
RUN pip install "matplotlib==3.10.0"
RUN pip install "mcp~=1.10"

COPY workspace/ /app/
"""


# Upstream `Sample.input` is exactly `obj["query"]` (task.py json_to_sample);
# the query itself states the required answer shape.  We append only where to
# put the answer, since Harbor reads it from a file.
INSTRUCTION_TEMPLATE = """\
{query}

---

When you are done, write your final answer, in the format requested above, to
`/app/answer.txt`.
"""


SOLVE_SH_TEMPLATE = """\
#!/bin/bash
set -e

cat > /app/answer.txt <<'ORACLE_ANSWER_EOF'
{oracle_answer}
ORACLE_ANSWER_EOF
"""


TEST_SH = VERIFIER_TEST_SH


RUN_SCORER_PY = r'''"""SUPER-Expert verifier (AstaBench super_test).

Faithful port of upstream `check_super_execution` (astabench/evals/super/
task.py) with `extract_json_from_response` (astabench/evals/utils.py), both
vendored from allenai/asta-bench (fork commit 17c84ca; unchanged from upstream
main).  Reward = `output_match` (suite primary metric `output_match/mean`).

Upstream flow on `state.output.completion`:
  try:   submission, submitted, trajectory = parse_super_output(completion)
  except Exception: score 0 (output_match = submitted = landmarks = 0)
  em = evaluate(submission, json.loads(target))            # may raise
  landmarks = evaluate_checkpoints(metadata.landmarks, trajectory)  # may raise
`evaluate` / `evaluate_checkpoints` run outside the try, so an exception there
is an Inspect sample error, not a score.  Here that is a non-zero exit with no
reward (verifier contract in tests/test.sh).

Harbor difference: the verifier only sees the final completion
(/app/answer.txt), not the sandbox Jupyter history that upstream's
`load_trajectory_from_sandbox()` reads.  Consequences:
  * Case 1 (answer JSON carries `history` + `submitted`): identical.
  * Case 2 (parsable answer, no history keys): identical for output_match;
    landmarks is computed over an empty trajectory (not part of the reward).
  * Case 3 (no parsable answer): upstream would mine the last Jupyter cell
    output; with no history the submission stays None, and
    evaluate(None, gold) == 0.0.  Harbor always takes the no-history branch.
The SUPER "Auto" split (`check_super_auto` / `evaluate_entrypoints`) is not
shipped: its execution history is agent-writable, so it cannot be scored
unforgeably.
"""

from __future__ import annotations

import json
import re
import sys
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, List

ANSWER_FILE = Path("/app/answer.txt")
CONFIG_FILE = Path("/tests/config.json")
REWARD_FILE = Path("/logs/verifier/reward.txt")


def _write_reward(value: float) -> None:
    REWARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    REWARD_FILE.write_text(f"{value:.6f}\n")


# --- verbatim: astabench/evals/utils.py::extract_json_from_response ---------
# (logger.warning replaced by a print to stderr)
def extract_json_from_response(response: str) -> dict[str, Any] | None:
    """Extract JSON from a response string.  Tries to be flexible with format,
    allowing other text around the json.  Returns None if no valid JSON."""
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    if json_start == -1 or json_end == -1:
        return None

    try:
        return json.loads(response[json_start:json_end])
    except json.JSONDecodeError:
        try:
            return json.loads(response[json_start + 1 : json_end - 1])
        except json.JSONDecodeError:
            print(
                f"Could not decode JSON from response: {response[json_start:json_end]}",
                file=sys.stderr,
            )
        return None


# --- astabench/evals/super/task.py::parse_super_output ----------------------
# Verbatim except that the sandbox trajectory is unavailable to the Harbor
# verifier: `load_trajectory_from_sandbox()` is replaced by `None`, so the
# Case 3 history-mining branch (`if history:`) can never run.
def parse_super_output(output: str) -> tuple[Any, int, List[dict]]:
    try:
        # Case 1
        exec_res = extract_json_from_response(output)
        if exec_res is not None and all(
            k in exec_res for k in ["history", "submitted"]
        ):
            return (
                exec_res.get("exec_result", "ERROR"),
                exec_res["submitted"],
                exec_res["history"],
            )

        history = None  # upstream: await load_trajectory_from_sandbox()

        # Case 2
        if exec_res is not None:
            submitted = 1
        # Case 3
        else:
            submitted = 0
            # upstream mines history[-1]["observation"] here when a sandbox
            # history exists; unavailable in Harbor (see module docstring).
    except (JSONDecodeError, ValueError):
        raise ValueError(f"Unable to parse agent output: {output}")

    return exec_res, submitted, (history or [])


# --- verbatim: astabench/evals/super/task.py::evaluate ----------------------
# Quirks kept on purpose: the dict branch swaps the arguments of the
# recursive call, the list branch drops float_epsilon, and None / empty
# list / empty dict raise (ValueError / ZeroDivisionError) -> sample error.
def evaluate(predicted, gold, float_epsilon: float = 1e-2) -> float:
    if isinstance(gold, int):
        gold = float(gold)
    if isinstance(predicted, int):
        predicted = float(predicted)

    if not isinstance(gold, type(predicted)):
        return 0.0
    if isinstance(gold, list):
        return sum([evaluate(p, g) for p, g in zip(predicted, gold)]) / len(gold)
    if isinstance(gold, dict):
        return sum(
            [
                evaluate(gv, predicted.get(gk, None), float_epsilon=float_epsilon)
                for gk, gv in gold.items()
            ]
        ) / len(gold)
    if isinstance(gold, str):
        return float(predicted.strip() == gold.strip())
    if isinstance(gold, float):
        return float(abs(predicted - gold) < float_epsilon)

    raise ValueError(f"Unknown gold type: {type(gold)}")


# --- verbatim: astabench/evals/super/task.py::evaluate_checkpoints ----------
# Not part of the reward; run only so that inputs on which upstream raises
# (e.g. a malformed self-reported `history`) are a sample error here too.
def evaluate_checkpoints(
    gold_checkpoints: List[str], agent_history: List[Dict]
) -> float:
    checkpoints_hit = []
    for checkpoint in gold_checkpoints:
        hit = False
        for step in agent_history:
            if re.search(checkpoint, step["observation"].replace("\n", " ")):
                hit = True
                break
        checkpoints_hit.append(hit)
    return sum(checkpoints_hit) / len(checkpoints_hit) if checkpoints_hit else 0.0


def score_completion(completion: str, gold_answer_json: str, landmarks_gold):
    """Upstream `check_super_execution.score`; returns the Score value dict."""
    try:
        submission, submitted, trajectory = parse_super_output(completion)
    except Exception as e:
        print(f"Error parsing output: {e!r}", file=sys.stderr)
        return {"output_match": 0.0, "submitted": 0.0, "landmarks": 0.0}
    em = evaluate(submission, json.loads(gold_answer_json))
    landmarks = evaluate_checkpoints(landmarks_gold, trajectory)
    return {"output_match": em, "submitted": submitted, "landmarks": landmarks}


def _read_answer():
    # A missing file, a directory, or undecodable bytes is an invalid answer
    # (reward 0), never a verifier crash.
    try:
        if not ANSWER_FILE.is_file():
            return None
        return ANSWER_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"answer.txt unreadable: {e}", file=sys.stderr)
        return None


def main() -> int:
    cfg = json.loads(CONFIG_FILE.read_text())
    gold_answer_json = cfg["gold_answer_json"]
    landmarks_gold = cfg["landmarks"]
    json.loads(gold_answer_json)  # broken gold -> verifier failure

    raw = _read_answer()
    if raw is None:
        print("answer.txt missing or unreadable", file=sys.stderr)
        _write_reward(0.0)
        return 0

    value = score_completion(raw, gold_answer_json, landmarks_gold)
    print(
        "output_match={output_match} submitted={submitted} "
        "landmarks={landmarks}".format(**value),
        file=sys.stderr,
    )
    _write_reward(float(value["output_match"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def oracle_answer_for(gold_answer_json: str) -> str:
    """Oracle completion that upstream's parser maps back to the gold value.

    Upstream parses the answer with `extract_json_from_response`, which only
    looks between the first `{` and the last `}` (falling back to the text
    strictly inside them).  A dict gold is therefore returned as-is; a list or
    string gold (3 of the 45 Expert samples) is only recoverable when wrapped
    in braces, e.g. `{["race", ...]}` -> inner text `["race", ...]`.
    """
    if isinstance(json.loads(gold_answer_json), dict):
        return gold_answer_json
    return "{" + gold_answer_json + "}"


def json_to_record(obj: dict, split: str) -> SampleRecord:
    """Mirror of upstream `json_to_sample` for the Expert split.

    Where upstream raises (missing answer, malformed entrypoint) we raise
    too, so generation fails loudly instead of silently dropping a sample.
    """
    target = obj.get("answer", None)
    entrypoint = (obj.get("entrypoint") or "").strip()
    if target is None:
        raise RuntimeError(
            f"super-expert: instance missing answer: {obj.get('task_id')}"
        )
    if entrypoint and not entrypoint.endswith((".py", ".sh", ".bash")):
        raise RuntimeError(
            "super-expert: entry point not correct format, must be Python or "
            f"Bash file: {entrypoint}"
        )
    if not isinstance(target, str):
        # Upstream scores json.loads(target.text); HF ships answers as JSON
        # strings.  Anything else would change what is compared.
        raise TypeError(
            f"super-expert: answer for {obj.get('task_id')} is not a JSON string"
        )
    json.loads(target)  # must be valid JSON, as upstream's scorer requires

    instance_rep = md5(str(obj["query_components"]).encode("utf-8")).hexdigest()
    return SampleRecord(
        sample_id=f"{obj['task_id']}_{instance_rep}",
        split=split,
        instruction=obj["query"],
        target=target,
        metadata={
            "landmarks": list(obj.get("landmarks") or []),
            "task_id": obj.get("task_id"),
            "github_repo": obj.get("github_repo"),
            "git_commit": obj.get("git_commit"),
        },
        workspace_files={},
    )


class SuperExpertBuilder(BenchmarkBuilder):
    family_name = "super-expert"
    default_split = "test"

    def load_samples(self, split: str) -> Iterable[SampleRecord]:
        if split == "validation":
            raise SplitNotAvailable(
                "super_validation (SUPER 'Auto') is excluded: its metric, "
                "evaluate_entrypoints(), scores an execution history the agent "
                "can write (parse_super_output Case 1 answer JSON, or "
                "jupyter_cell_history.json in its working dir), so it cannot be "
                "scored unforgeably"
            )
        if split != "test":
            raise ValueError(f"super-expert: unknown split {split!r}")

        try:
            from datasets import load_dataset
        except ImportError as e:
            raise RuntimeError("`datasets` required") from e

        token = os.getenv("HF_TOKEN") or os.getenv("HF_ACCESS_TOKEN")
        ds = load_dataset("allenai/super", "Expert", token=token)
        for obj in map(dict, ds["all_examples"]):
            yield json_to_record(obj, split)

    def write_task(self, record: SampleRecord, task_dir: Path) -> None:
        task_name = f"allenai/asta-bench__{self.task_id(record)}"
        task_toml = TASK_TOML_TEMPLATE.format(
            task_name=task_name,
            split=record.split,
            source_id=record.sample_id,
        )
        instruction = INSTRUCTION_TEMPLATE.format(query=record.instruction)
        solve_sh = SOLVE_SH_TEMPLATE.format(
            oracle_answer=oracle_answer_for(record.target)
        )

        tests_config = {
            "family": self.family_name,
            "source_sample_id": record.sample_id,
            "split": record.split,
            "gold_answer_json": record.target,
            "landmarks": record.metadata["landmarks"],
        }

        bridge_config = make_inspect_config(
            task=_INSPECT_TASK,
            sample_id=record.sample_id,
            pip_install=self.inspect_pip_install(),
            eval_args=_BRIDGE_EVAL_ARGS,
        )
        # Lands at /app/inspect_config.json via `COPY workspace/ /app/`.
        ws_files = dict(record.workspace_files)
        ws_files["inspect_config.json"] = json.dumps(bridge_config, indent=2)

        write_task_files(
            task_dir,
            task_toml=task_toml,
            instruction_md=instruction,
            dockerfile=DOCKERFILE,
            solve_sh=solve_sh,
            test_sh=TEST_SH,
            tests_config=tests_config,
            extra_tests={"run_scorer.py": RUN_SCORER_PY},
            workspace_files=ws_files,
        )
        # Build-context-only files (environment/ is the Docker build context);
        # they are COPY'd to /opt/sandbox_requirements, not into /app.
        req_dir = task_dir / "environment" / _REQUIREMENTS_DIR
        req_dir.mkdir(parents=True, exist_ok=True)
        for name, content in _REQUIREMENTS_FILES.items():
            (req_dir / name).write_text(content, encoding="utf-8")
