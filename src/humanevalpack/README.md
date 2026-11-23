## HumanEvalPack → Harbor Adapter

## Overview

HumanEvalPack ([OctoPack, arXiv:2308.07124](https://arxiv.org/abs/2308.07124)) extends HumanEval to six languages (Python, JavaScript, Java, Go, C++, Rust) and three task families (Fix, Explain, Synthesize). This adapter converts the **HumanEvalFix** bug-repair family into Harbor tasks.

- **Task type**: repair a single buggy function so that the upstream unit tests pass.
- **Languages**: JavaScript, Java, Go, C++, Rust by default (5 × 164 = 820 problems, **818 tasks** after excluding Go/95 and Rust/32, see *Notes & Caveats*). Python (164 more) can be generated with `--languages python`, but it is already covered by the existing [`humanevalfix`](../humanevalfix) adapter.
- **Source**: Hugging Face [`bigcode/humanevalpack`](https://huggingface.co/datasets/bigcode/humanevalpack), pinned to revision `9a41762f73a8cb23bb5811b73d5aab164efcf378`, split `test`.
- **License**: MIT (same as the upstream dataset).
- **Task naming**: `bigcode/humanevalpack__<lang>-<n>` (directory `<lang>-<n>`), where `<lang>` ∈ {`js`, `java`, `go`, `cpp`, `rust`, `python`} and `<n>` is the upstream problem number (`JavaScript/12` → `js-12`).
- **Main adaptation**: the upstream benchmark prompts an LLM once with the buggy code plus tests and grades the completion. Here an agent gets the same code as a runnable file in a container and edits it in place. The grader runs the upstream tests with the upstream compile/run command and pass criterion.

## What is HumanEvalPack?

HumanEvalPack was released with OctoPack (Muennighoff et al., 2023) to evaluate instruction-tuned code models across languages. In HumanEvalFix, each of the 164 HumanEval problems has a hand-written bug (6 bug types, e.g. *missing logic*, *value misuse*) in every language. The model sees the buggy function and, in the "tests" variant (`humanevalfixtests-<lang>`), the unit tests, and must produce a fixed function. The original metric is pass@k (pass@1 in the paper), computed by [bigcode-evaluation-harness](https://github.com/bigcode-project/bigcode-evaluation-harness/blob/main/bigcode_eval/tasks/humanevalpack.py) with the [`Muennighoff/code_eval_octopack`](https://huggingface.co/spaces/Muennighoff/code_eval_octopack) executor.

## Adapter Features

- **Pinned, reproducible generation** from the HF parquet data (`--dataset-revision` to override); stable task names derived from upstream ids.
- **One file per task, runnable as-is**: the agent edits a single file containing the language prefix, `declaration`, the buggy body, and the upstream `test` block (the `humanevalfixtests` context):

  | Lang | File | Run command (shown to the agent) | Pass criterion (same as upstream) |
  |------|------|----------------------------------|-----------------------------------|
  | js | `/workspace/solution.js` | `node solution.js` | no stdout **and** no stderr |
  | java | `/workspace/Main.java` | `javac Main.java && java -cp . Main` | exit code 0 |
  | go | `/workspace/main_test.go` | `go test main_test.go` | exit code 0 |
  | cpp | `/workspace/solution.cpp` | `g++ -std=c++11 … -lcrypto -lssl && ./a.out` | compiles, exit code 0 |
  | rust | `/workspace/src/main.rs` (cargo project) | `cargo test` | `cargo check` and `cargo test` succeed |
  | python | `/workspace/solution.py` | `python3 solution.py` | exit code 0 |

- **Upstream pre-processing applied at generation time**: the Python/C++ import helpers, Go import detection (based on `test_setup`), and Rust's `fn main(){}` prefix are written into the file, so what the agent runs is what gets graded.
- **Tamper-resistant grading**: `tests/verify.py` finds the pristine upstream test block (`tests/test_block.txt`) at the end of the agent's file, takes everything before it as the candidate, re-appends the pristine tests (`candidate + "\n" + test`, as upstream), and runs the result in a fresh temp directory. If the test block was edited or deleted, the task fails.
- **Per-language Docker images** (`src/humanevalpack/dockerfiles/`): Node 20 + `js-md5`; Temurin JDK 17; Go 1.22 with `testify` pre-fetched; Debian g++ with Boost and OpenSSL; Rust 1.83 with the upstream `Cargo.toml` dependencies (`rand 0.4`, `regex 1`, `md5 0.7`) prebuilt. Offline grading works for every language.
- **Oracle**: `solution/solve.sh` writes the same file with the upstream `canonical_solution`.
- **Data repairs**: five problems whose upstream `declaration` is not a valid prefix of the solutions are repaired at generation time (see *Notes & Caveats*); `tests/config.json` records the repair in `declaration_fix`.
- **Prompt**: follows the OpenHands HumanEvalFix prompt used by the existing `humanevalfix` adapter, generalised to all languages. It keeps the upstream instruction `Fix bugs in <entry_point>.` and adds the file path and test command.

## Generated Task Structure

```
humanevalpack/
├── js-0/
│   ├── task.toml                 # name = "bigcode/humanevalpack__js-0", authors, metadata
│   ├── instruction.md            # fix-the-bug prompt + full buggy file
│   ├── environment/
│   │   ├── Dockerfile            # per-language toolchain
│   │   └── workspace/            # the buggy file (+ Cargo.toml for Rust)
│   ├── solution/
│   │   └── solve.sh              # writes declaration + canonical_solution + tests
│   └── tests/
│       ├── test.sh               # runs verify.py, writes /logs/verifier/reward.txt
│       ├── verify.py             # rebuilds candidate + pristine tests and runs them
│       ├── test_block.txt        # pristine upstream `test` field
│       └── config.json           # language, file path, source id, dataset revision
├── java-0/
└── ...
```

Adapter code layout:

```
src/humanevalpack/
├── README.md
├── adapter_metadata.json
├── parity_experiment.json
├── pyproject.toml
├── run_humanevalpack.yaml
└── src/humanevalpack/
    ├── __init__.py
    ├── adapter.py               # HumanEvalPackAdapter: load HF data, write tasks
    ├── languages.py             # per-language program assembly (upstream pre-processing)
    ├── main.py                  # CLI
    ├── dockerfiles/             # <lang>.Dockerfile
    └── task-template/
        ├── task.toml
        ├── instruction.md
        ├── environment/Dockerfile   # placeholder, replaced per language
        ├── solution/solve.sh
        └── tests/{test.sh,verify.py}
```

## Run Evaluation / Harness

### Running with Datasets Registry

After the dataset is published:

```bash
harbor run -d bigcode/humanevalpack                       # oracle
harbor run -d bigcode/humanevalpack -a <agent> -m "<model>"
```

### Using Job Configurations

```bash
# From the adapters repository root, after generating datasets/humanevalpack
harbor run -c src/humanevalpack/run_humanevalpack.yaml                    # oracle (default)
harbor run -p datasets/humanevalpack -a <agent> -m "<model>"
harbor job resume -p /path/to/jobs/directory
```

### Running Individual Trial

```bash
harbor trial start -p datasets/humanevalpack/rust-0                       # oracle
harbor trial start -p datasets/humanevalpack/rust-0 -a <agent> -m "<model>"
```

## Usage: Create Task Directories

```bash
cd src/humanevalpack
uv sync
uv run humanevalpack --output-dir ../../datasets/humanevalpack
```

Flags:
- `--output-dir` — where to write tasks (default `datasets/humanevalpack` at the repo root)
- `--limit N` — only the first N problems **of each selected language**
- `--overwrite` — replace existing task directories (otherwise they are skipped)
- `--task-ids` — e.g. `js-0 Java/3 bigcode/humanevalpack__go-7`
- `--languages` — any of `js java go cpp rust python` (default: `js java go cpp rust`)
- `--dataset-revision` — HF revision (default: pinned)
- `--include-excluded` — also generate tasks excluded for upstream defects (currently `go-95`, `rust-32`)

## Comparison with Original Benchmark (Parity)

Parity has not been run yet. The agent, model, and number of runs still need to be agreed with the Harbor team. The upstream harness is single-shot LLM generation with no agent support, so parity will need a fork of bigcode-evaluation-harness (Scenario 2) or another agreed setup. Results will be reported as mean ± sample SEM.

| Agent | Model | Metric | Number of Runs | Dataset Size | Original Benchmark Performance | Harbor Adapter Performance |
|-------|-------|--------|------------------|--------------|------------------------------|----------------------------|
| TBD | TBD | pass@1 | TBD | 818 | TBD | TBD |

Reproduction (Harbor side):

```bash
harbor run -c src/humanevalpack/run_humanevalpack.yaml -a <agent> -m "<model>"
```

## Notes & Caveats

- **Python overlap**: Python is not in the default set, to avoid duplicating `humanevalfix` (`python-<n>`). Whether this adapter should also own Python is still an open question for the team.
- **Deviations from the upstream executor**:
  - Go: upstream adds detected helper packages by their last path component (`"rand"`, `"md5"`); this adapter writes the full import path (`math/rand`, `crypto/md5`).
  - Upstream truncates model generations at language stop words (for Go these include `"
func"` and `"struct"`). Agents edit files instead of producing a completion, so no truncation is applied. Upstream, the canonical solutions of Go/72, Go/90 and Go/158 fail only because of this truncation; here they pass.
  - C++: upstream prepends `using namespace std;` *before* the includes. Here it comes after them, so the file compiles on its own.
  - Timeouts are more generous than upstream (e.g. `javac` 120 s instead of 5 s × 5 retries; Go wall clock 180 s with `-timeout=20s` as upstream). The run-step timeouts match upstream where they apply.
  - JavaScript keeps the strict upstream rule (any stdout/stderr output fails). The instruction states it explicitly, so agents don't fail by leaving debug prints in.
- **Test integrity**: the agent must leave the trailing test block unchanged (trailing whitespace is ignored). Editing it gives reward 0.
- **Repaired upstream data** (the canonical solution does not compile upstream for these problems):
  - Go/10, Go/32, Go/38, Go/50: `declaration` omits a helper function that the solution calls (`IsPalindrome`, `Poly`, `EncodeCyclic`, `EncodeShift`). The helper is taken from the upstream `prompt`, without its import block and `//` comments, so no docstring is added (HumanEvalFix gives no docstrings).
  - CPP/38: `declaration` already contains the first lines of the `decode_cyclic` body, which both solutions repeat. It is cut right after the `decode_cyclic` signature.
- **Excluded**: Go/95. The canonical `CheckDictCase` stops after the second key, so the result depends on Go's random map iteration order (oracle passed 14/20 runs locally).
- **Excluded**: Rust/32. The test runs `find_zero` on 100 random polynomials, and the canonical Newton iteration has no iteration limit, so on some draws it never converges and the test hangs until the timeout.
- Generate the excluded tasks anyway with `--include-excluded`.
- **Kept, known weak test**: CPP/23. The tests call `strlen("...")` with string literals, which resolves to the C library `strlen(const char*)` instead of the candidate `strlen(string)`, so the buggy version also passes. It is kept as in upstream.

## Installation / Prerequisites

- Docker running locally
- Harbor CLI (`uv tool install harbor`)
- Python ≥ 3.12 and `uv`:
  ```bash
  cd src/humanevalpack
  uv sync
  ```
- First builds download several toolchain images (Node, JDK, Go, GCC, Rust; ~3–4 GB in total). The Rust image also compiles the upstream crate dependencies.
- On Windows, set `PYTHONUTF8=1` when running `harbor adapter init`/`uv run` if you hit `UnicodeDecodeError: 'gbk' codec`.

## Troubleshooting

- **Rust tasks slow on first run**: the image prebuilds `rand`/`regex`/`md5` into `CARGO_TARGET_DIR=/opt/humanevalpack/rust-target`. Make sure the image build is not timing out (`build_timeout_sec = 1800`).
- **Go `cannot find module`**: grading uses the image's pre-fetched module cache with `GOPROXY=off`. Rebuild the image if `go.mod`/`go.sum` under `/opt/humanevalpack/go` is missing.
- **"test code ... was modified or removed"** in verifier output: the agent edited the trailing test block. See *Test integrity* above.

## Citation

```bibtex
@article{muennighoff2023octopack,
  title={OctoPack: Instruction Tuning Code Large Language Models},
  author={Niklas Muennighoff and Qian Liu and Armel Zebaze and Qinkai Zheng and Binyuan Hui and Terry Yue Zhuo and Swayam Singh and Xiangru Tang and Leandro von Werra and Shayne Longpre},
  journal={arXiv preprint arXiv:2308.07124},
  year={2023}
}
```

## Authors & Contributions

This adapter is developed and maintained by [Feikai Gao](mailto:mingqwqqaq@gmail.com).

**Issues and Contributions:**
- Submit issues and pull requests to [harbor-framework/adapters](https://github.com/harbor-framework/adapters)
