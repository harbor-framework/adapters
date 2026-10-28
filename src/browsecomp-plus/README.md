# BrowseComp-Plus → Harbor Adapter

## Overview

Converts [BrowseComp-Plus](https://texttron.github.io/BrowseComp-Plus/), a fixed-corpus deep-research benchmark, into Harbor tasks. The upstream `test` split has **830 queries**. Task generation decrypts upstream records locally; generated data is not included in this adapter repository.

This contribution migrates [harbor#1511](https://github.com/harbor-framework/harbor/pull/1511), source head `eedc646d0637ebbefe459a5bd965fa242faecac6`, into the standalone adapters repository. [Migration review context](migration/REVIEW_CONTEXT.md) preserves review links, public validation artifacts, and outstanding decisions.

## What is BrowseComp-Plus?

[BrowseComp-Plus](https://github.com/texttron/BrowseComp-Plus) evaluates multi-step retrieval and answer synthesis over a controlled document collection. The primary workflow uses BM25, `search`, and `get_document`. Accuracy is evaluated against the benchmark's reference answer.

This is distinct from the 1,266-task open-web **BrowseComp** adapter in [harbor#2355](https://github.com/harbor-framework/harbor/pull/2355), migrated to [adapters#44](https://github.com/harbor-framework/adapters/pull/44). Those PRs are cross-referenced for coordination; their tasks, protocols, and scores are not combined here.

## Adapter Features

- Independent uv package and canonical `browsecomp-plus` generation command; `browsecomp_plus` remains a compatibility alias.
- Full split, explicit query IDs, deterministic sampling, and the historical first-30 parity subset.
- Packaged `browsecomp_plus.deep_research_agent:DeepResearchAgent` custom Harbor agent, version `1.0.11`, with its installation template available after wheel installation.
- Task-local BM25 tools, oracle answer wiring, and the existing exact-match / LLM-judge verifier.
- `origin_agents/` retains the original-style reference code; `scripts_build_index/` and `scripts_evaluation/` are source-checkout helpers for preparation and offline analysis.

The custom agent wraps the original search/retrieve/answer workflow. Historical metadata calls the original side `search-agent@1.0.0` and the Harbor side `deep-research-agent@1.0.11`; equivalent behavior remains a methodology claim to check, including turn limits and tool/prompt alignment. Supplementary Claude Code runs are separate from this comparison.

## Generated Task Structure

```text
datasets/browsecomp-plus/
├── indices/bm25/                # shared retrieval assets, not one copy per task
└── <query-id>/
    ├── task.toml               # name: texttron/browsecomp-plus-<query-id>
    ├── instruction.md
    ├── environment/
    │   ├── Dockerfile
    │   ├── docker-compose.yaml
    │   ├── tools_wrapper.py
    │   └── skills/searchers/
    ├── solution/
    │   ├── solve.sh
    │   └── oracle_config.json
    └── tests/
        ├── config.json
        ├── test.sh
        └── test_outputs.py
```

The compose mount `../../indices` resolves relative to each task's `environment/` directory. Keep the shared index beside task directories. The Dockerfile also supports a runtime BM25 download when a cloud provider does not mount the host corpus; that path requires network access and adequate storage and has not been revalidated by this migration.

## Run Evaluation / Harness

Registry execution is only available after the team confirms publication. Historical [dataset PR #180](https://github.com/harbor-framework/harbor-datasets/pull/180) was merged, but current registration and encrypted-data handling remain under discussion in [harbor-datasets#246](https://github.com/harbor-framework/harbor-datasets/issues/246). No working registry ID is claimed here. After publication, the intended command is `harbor run -d texttron/browsecomp-plus -a oracle`.

For local development, run from this adapter directory:

```bash
cd src/browsecomp-plus
uv sync --extra agent
uv run browsecomp-plus --output-dir datasets/browsecomp-plus --limit 1

# Default config runs oracle. Docker must be running.
uv run --extra agent harbor run -c run_browsecomp_plus.yaml

# Single-task oracle smoke (use an ID that was generated).
uv run --extra agent harbor trial start -p datasets/browsecomp-plus/1 -a oracle

# Custom agent import is explicit; it is not registered as a Harbor built-in.
uv run --extra agent harbor run -p datasets/browsecomp-plus \
  --agent-import-path browsecomp_plus.deep_research_agent:DeepResearchAgent \
  -m gpt-5-mini
```

Model runs can incur API costs. Agree any new parity plan with the maintainers before execution. `run_parity.yaml` is a proposed, single-run reproduction config, not evidence of a new experiment.

## Usage: Create Task Directories

```bash
cd src/browsecomp-plus
uv sync
uv run browsecomp-plus --output-dir datasets/browsecomp-plus
uv run browsecomp-plus --output-dir datasets/debug --task-ids 1 6 7 --overwrite
uv run browsecomp-plus --output-dir datasets/parity --split parity

# Reuse an existing directory containing bm25/.
uv run browsecomp-plus --output-dir datasets/debug --limit 1 \
  --indices-dir /absolute/path/to/indices

# Generate without downloading indices; retrieval will need assets before use.
uv run browsecomp-plus --output-dir datasets/debug --limit 1 --skip-download
```

The default output is `datasets/browsecomp-plus` under the current directory. The dataset itself still needs Hugging Face access or an existing local HF cache, including with `--skip-download`. Generation downloads only BM25 assets by default. It does not download historical evaluation runs or optional dense indexes. `--split parity` takes the first 30 upstream records before other filters, matching the historical subset rule; it does not repair historical missing outputs.

## Comparison with Original Benchmark (Parity)

The table preserves the **historical comparison**, not a new current-contract parity approval. Scores are percentages; uncertainty is sample SEM across the five run scores. Summary strings were recomputed from the retained rounded raw arrays.

| Agent | Model | Metric | Runs | Dataset Size | Original (mean ± SEM) | Harbor (mean ± SEM) |
|-------|-------|--------|------|--------------|-----------------------|---------------------|
| search-agent@1.0.0 / deep-research-agent@1.0.11 | gpt-5-mini | Accuracy | 5 per side | first 30 of 830 (3.61%) | 17.424 ± 1.579 | 20.000 ± 1.489 |

Original correct/completed counts were **4/29, 6/30, 5/25, 6/30, 4/30**. Harbor counts were **5/30, 5/30, 7/30, 6/30, 7/30**. The run-score ranges overlap, but denominators differ. The historical model alias is floating, and documented commands use 50 iterations on the original side versus 30 on Harbor. Exact execution revisions and matched settings remain for maintainer confirmation. The metadata therefore leaves current matching status unclassified.

Public evidence:

- [Original adapter PR and review history](https://github.com/harbor-framework/harbor/pull/1511).
- [Original-side parity fork](https://github.com/wizard1203/BrowseComp-Plus-parity).
- [Historical merged dataset PR](https://github.com/harbor-framework/harbor-datasets/pull/180).
- [HF parity discussion #246](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/246), with both sides, result collections, configs, and oracle material.
- [Evidence inventory and immutable artifact references](migration/REVIEW_CONTEXT.md).

### Reproduction preparation

Use the canonical generator above for the Harbor first-30 subset. After a matching plan is agreed, run `uv run --extra agent harbor run -c run_parity.yaml` from this directory. The config uses BM25, `k=5`, snippets of 512 tokens, and the historical Harbor limits of 30 turns / 10,000 output tokens. Align both sides to the approved settings before a fresh comparison.

The original-side fork is the canonical reproduction source:

```bash
git clone https://github.com/wizard1203/BrowseComp-Plus-parity.git
cd BrowseComp-Plus-parity
# Snapshot inspected during migration; not asserted to be the old run revision.
git checkout 56534c8453a9efe37862f0173cf221974a99a49c
uv sync
mkdir -p data topics-qrels
uv run python scripts_build_index/decrypt_dataset.py \
  --output data/browsecomp_plus_decrypted.jsonl \
  --generate-tsv topics-qrels/queries.tsv
# Historical subset uses the first 30 lines in upstream order.
head -n 30 topics-qrels/queries.tsv > topics-qrels/queries-first30.tsv
```

Prepare BM25 under `indexes/bm25` using this adapter's `scripts_build_index/download_indexes.sh` or the Hugging Face Python API; dense indexes and flash-attn are not needed for BM25. Java/Pyserini and the upstream dependencies must be installed for the original runner. The historical runner/scorer commands are:

```bash
uv run python search_agent/openai_client.py \
  --query topics-qrels/queries-first30.tsv --model gpt-5-mini \
  --searcher-type bm25 --index-path ./indexes/bm25 \
  --output-dir runs/bm25/gpt-5-mini --k 5 \
  --snippet-max-tokens 512 --max-iterations 50

uv run python scripts_evaluation/evaluate_with_openai.py \
  --input_dir runs/bm25/gpt-5-mini \
  --ground_truth data/browsecomp_plus_decrypted.jsonl \
  --eval_dir evals/gpt-5-mini \
  --qrel_evidence topics-qrels/qrel_evidence.txt --model gpt-5-mini
```

These commands document the inherited setup and its turn-limit mismatch; they have not been rerun for migration. Five independent runs per side produced the retained report. A new plan should first use a small sanity subset on both sides, then one full comparison, then agreed repeats.

### Separate historical evidence

- **Oracle:** 830/830, mean reward 1.0, zero errors in the published oracle rerun. This checks task/solution/verifier wiring and does not establish model parity.
- **Supplementary Claude Code + gpt-5-mini:** one Harbor-only run, 27.6% on 29 completed tasks.
- **Supplementary Claude Code + Haiku:** historical mean 25.6% ± 2.2% SEM over three reported runs (30.00, 23.33, 23.33). The first completed 24 trials with six infrastructure errors; subsequent runs were resumed. They are not clean matched parity evidence.
- **Earlier Daytona high scores:** excluded because absent indices caused retrieval failure and subsequent answer leakage through local-file inspection. These must not be used as benchmark scores.

## Notes & Caveats

### Migration and acceptance

The migration preserves benchmark prompts, oracle behavior, agent installer content, and verifier scoring. Changes address packaging, entry points, dataset task names, asset downloads, empty environment defaults, and import/model-loader failures. See [review continuity](migration/REVIEW_CONTEXT.md) and [local validation](migration/VALIDATION.md).

No live model calls, Docker/Daytona jobs, full 830-task oracle run, new parity upload, or dataset publication were performed for migration. A Docker daemon was unavailable locally. Current acceptance still requires maintainer decisions on historical methodology and dataset publication; coordinate any new runs first.

The guide's Harbor source compatibility reference is `99218a4611e3bd76e49ce3b5f977e8c8134ad3ac`. The standalone package's optional agent dependency and local check versions are recorded separately in `pyproject.toml` and the validation report; neither establishes which Harbor revision produced the historical runs.

### Inherited benchmark deviations

- Generation decrypts queries into instructions and keeps answers in verifier/oracle directories. Those directories must remain outside normal agent exposure; filesystem access restrictions in the instruction alone are not a security boundary.
- The verifier first normalizes answers for exact equality, including shortened year ranges, then uses an optional LLM judge. This is inherited behavior and differs from always judging with the upstream evaluator.
- Without `OPENAI_API_KEY`, non-exact answers are reported as incorrect with a warning. Keep judge credentials and model settings consistent for meaningful evaluations.
- The first-30 sequential sample is small and is not a representative random sample.
- BM25 is the primary documented path. Dense FAISS/ReasonIR require additional upstream Tevatron/model/GPU dependencies; they have no fresh end-to-end validation here.
- Historical corpus-download dependencies float; download availability is checked separately from actual runtime indexing. Cloud runs may fetch large BM25 assets and need additional storage.
- Generated data and full traces can contain benchmark plaintext. This PR carries source code and safe aggregate evidence only, while publication is coordinated in harbor-datasets#246.

## Installation / Prerequisites

Use Python **3.12+** and uv. Install generation dependencies with `uv sync`. Install `--extra agent` for the external Harbor CLI and the packaged custom agent. Development checks use `uv sync --group dev`.

Local evaluation requires Docker and the provided task image. Java 21 / Pyserini are installed in that image; the original-side runner needs them on its own host. BM25 generation does not require host CUDA, FAISS, or flash-attn. API credentials are required for model execution and semantic judging, independently of task generation.

Set `OPENAI_API_KEY`, `OPENAI_BASE_URL` (normally ending in `/v1`), and `JUDGE_MODEL` for the judge. `run_parity.yaml` passes model credentials to the custom agent explicitly. Exporting environment variables alone is not a substitute for the config's agent/verifier env mapping. For Claude Code experiments, configure its own Anthropic credentials and restrict its tools to the benchmark protocol; historical `ANTHROPIC_BASE_URL` must omit `/v1`.

## Troubleshooting

| Issue | Action |
|-------|--------|
| `huggingface-cli` missing | Generation now uses the declared `huggingface_hub` Python dependency; no legacy CLI is required. |
| Historical run download unavailable | Historical runs are optional and no longer part of task generation. Use preserved artifact links for evidence. |
| Custom agent import fails | Install `uv sync --extra agent` and use `browsecomp_plus.deep_research_agent:DeepResearchAgent`. |
| Empty searcher/index/number environment values | Runtime helpers and compose defaults now handle empty settings consistently. |
| Corpus unavailable | Keep `indices/bm25` next to tasks, or supply `--indices-dir`; check mount/network/storage before model runs. |
| Missing model judge key | Exact matches still work, but other responses score incorrectly; configure verifier credentials first. |
| Nonzero generator exit | Inspect the load/filter/generation error; incomplete generation no longer silently exits successfully. |
| Docker connection fails | Start Docker before evaluation; offline unit tests and generation checks do not need it. |

## Citation

```bibtex
@article{chen2025BrowseCompPlus,
  title={BrowseComp-Plus: A More Fair and Transparent Evaluation Benchmark of Deep-Research Agent},
  author={Chen, Zijian and Ma, Xueguang and Zhuang, Shengyao and Nie, Ping and Zou, Kai and Liu, Andrew and Green, Joshua and Patel, Kshama and Meng, Ruoxi and Su, Mingyi and Sharifymoghaddam, Sahel and Li, Yanxi and Hong, Haoran and Shi, Xinyu and Liu, Xuye and Thakur, Nandan and Zhang, Crystina and Gao, Luyu and Chen, Wenhu and Lin, Jimmy},
  year={2025},
  journal={arXiv preprint arXiv:2508.06600}
}
```

## Authors & Contributions

Developed and maintained by [Zhenheng Tang](mailto:coolzhtang@gmail.com). The original contribution and review history remain at [harbor#1511](https://github.com/harbor-framework/harbor/pull/1511). Original BrowseComp-Plus: Zijian Chen, Xueguang Ma, and the benchmark authors credited in each task's `[task].authors`.

Submit adapter issues and changes to [harbor-framework/adapters](https://github.com/harbor-framework/adapters). This migration preserves attribution and existing evidence; related BrowseComp work is independently credited in adapters#44.

## Acknowledgement

Historical parity inference compute was generously supported by [2077AI](https://www.2077ai.com/).
