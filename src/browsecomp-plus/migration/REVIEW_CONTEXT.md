# BrowseComp-Plus migration: review continuity and historical evidence

This note was checked on 2026-10-28. It preserves review context; it is not a new
parity experiment or a maintainer acceptance decision. No model calls or live
Docker/Daytona jobs were run to produce this note. Only synthetic records are
used by the migration regression tests.

## Source and destination

- Replacement migration: [adapters#61](https://github.com/harbor-framework/adapters/pull/61) (draft; review and acceptance pending).

- Original contribution: [harbor#1511](https://github.com/harbor-framework/harbor/pull/1511)
  by Zhenheng Tang (`@wizard1203`). Original remote head inspected:
  [`eedc646d0637ebbefe459a5bd965fa242faecac6`](https://github.com/harbor-framework/harbor/tree/eedc646d0637ebbefe459a5bd965fa242faecac6/adapters/browsecomp_plus).
- Existing local Harbor checkout used for migration:
  `fbed8d852571dd4a42d0b33a1d008deb47a80a06`. Its tracked adapter files match the remote PR head; existing fixes are
  identified below rather than represented as newly discovered fixes.
- Destination `harbor-framework/adapters` main inspected at
  [`7b4df9deb2381ae32f26e6cebec06aaa2975dc56`](https://github.com/harbor-framework/adapters/tree/7b4df9deb2381ae32f26e6cebec06aaa2975dc56).
  See its [human adapter guide](https://github.com/harbor-framework/adapters/blob/7b4df9deb2381ae32f26e6cebec06aaa2975dc56/docs/adapters-human.mdx).
- [Maintainer migration request](https://github.com/harbor-framework/harbor/pull/1511#issuecomment-6004919513):
  carry review context and reproducible evidence, fix download/import blockers,
  and coordinate any new matched-model parity or methodology changes first.
  The subsequent email requested a replacement PR link by 2026-10-30.

## Review items carried forward

The [latest full review on the original PR](https://github.com/harbor-framework/harbor/pull/1511#issuecomment-5013517293)
reported two blocking reproduction bugs and two recommended changes. Those
bot conclusions are historical review evidence, not a substitute for the
current checks below.

| Item | Source | State carried into migration |
| --- | --- | --- |
| Historical run-file downloads blocked all task generation when unavailable | [Download finding](https://github.com/harbor-framework/harbor/pull/1511#discussion_r3170060369) | Existing local follow-up already changed failure to a warning. Migration separates optional historical-run acquisition from task generation. |
| `search_agent.prompts` import was invalid in the host evaluation helper | [Import finding](https://github.com/harbor-framework/harbor/pull/1511#discussion_r3169015524) | Existing local follow-up imports `origin_agents.prompts`; preserve and exercise the helper import. |
| Interrupted index reuse could fail on an existing destination | [Copy fallback finding](https://github.com/harbor-framework/harbor/pull/1511#discussion_r3163831965) | Existing local follow-up already uses `dirs_exist_ok=True`. |
| Task name should use the original benchmark organization | [Human request](https://github.com/harbor-framework/harbor/pull/1511#discussion_r3140296689) | Existing local follow-up added `texttron/`; migration uses one organization separator in `texttron/browsecomp-plus-<id>`. |
| Blank Compose environment values crash integer conversion in search tools | [July tool-default finding](https://github.com/harbor-framework/harbor/pull/1511#discussion_r3625152422) | Still present in the migration source; fix and test the blank-value path during migration. |
| ReasonIR model loader override is never invoked by the parent constructor | [July ReasonIR finding](https://github.com/harbor-framework/harbor/pull/1511#discussion_r3625152568) | Still present in the migration source; preserve the upstream loading hook and test with stubs. This concerns an optional backend, not a new dense-retrieval parity claim. |

Earlier [answer-leakage review](https://github.com/harbor-framework/harbor/pull/1511#discussion_r3141299318)
found ground truth copied/mounted into the agent environment. The template
subsequently stopped copying `tests/` and `solution/` into the image or mounting
`tests/` through Compose. The [requested complete parity rerun](https://github.com/harbor-framework/harbor/pull/1511#discussion_r3141305963)
remains relevant when interpreting historical standard-CLI results. The current
synthetic generation test checks generated environment assets and mount sources;
it does not establish runtime isolation on an unexecuted provider.

## Public artifact provenance

The [Hugging Face parity discussion #246](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/246)
was reachable through the Hub API on 2026-10-28 and was **draft**, not merged.
Its public artifact commit is
[`43f79cfe925071d01dcf4dc3b1efc6831b0c00db`](https://huggingface.co/datasets/harborframework/parity-experiments/tree/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus).
This immutable commit contains the original-side evaluations, Harbor jobs,
supplementary CLI runs, oracle results, and aggregate result collection. Existing
raw traces remain at their original location; this migration adds no copies of
real task text, answers, or trial traces to the adapter repository.

Useful immutable links:

- [Artifact bundle README](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/README.md)
- [Historical Harbor parity rerun configuration](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/config.yaml)
- [Original-side evaluation directories](https://huggingface.co/datasets/harborframework/parity-experiments/tree/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/original_parity)
- [Five primary Harbor parity jobs](https://huggingface.co/datasets/harborframework/parity-experiments/tree/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/harbor_parity/search_agent_gpt5_mini)
- [Full oracle job](https://huggingface.co/datasets/harborframework/parity-experiments/tree/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/oracle/browsecomp-plus-oracle-rerun-20260429-prebuilt-nodelete)
- [Aggregate result collection](https://huggingface.co/datasets/harborframework/parity-experiments/tree/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection)
- [Original-style parity fork](https://github.com/wizard1203/BrowseComp-Plus-parity)
- [Single original-PR trial attachment](https://github.com/user-attachments/files/24848346/1__YfUNx2H.zip)
  (historical link preserved; attachment contents were not downloaded for this migration).

## Historical model comparison: retain the results and their limits

The primary reported comparison uses original `search-agent@1.0.0` and Harbor
`deep-research-agent@1.0.11`, both with the `gpt-5-mini` model name, BM25, `k=5`,
and snippet length 512. Recorded original evaluations are dated 2026-02-10
through 2026-02-13; Harbor job timestamps are 2026-02-25 through 2026-02-26.
The parity metadata date, 2026-03-02, is a reporting date rather than evidence
that both sides were executed that day. The published model name is an alias;
the summaries do not establish a dated provider model snapshot.

The following counts were verified directly from public summary JSON, using
original `per_query_metrics` arrays and Harbor `reward_stats` plus `n_errors`:

| Run | Original correct / evaluated | Original accuracy | Harbor correct / evaluated | Harbor accuracy |
| --- | --- | --- | --- | --- |
| 1 | [4 / 29](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_original_run1.json) | 13.79% | [5 / 30](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_harbor_run1.json) | 16.67% |
| 2 | [6 / 30](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_original_run2.json) | 20.00% | [5 / 30](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_harbor_run2.json) | 16.67% |
| 3 | [5 / 25](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_original_run3.json) | 20.00% | [7 / 30](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_harbor_run3.json) | 23.33% |
| 4 | [6 / 30](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_original_run4.json) | 20.00% | [6 / 30](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_harbor_run4.json) | 20.00% |
| 5 | [4 / 30](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_original_run5.json) | 13.33% | [7 / 30](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_harbor_run5.json) | 23.33% |

Reported mean and sample SEM are original **17.4% ± 1.6%** and Harbor
**20.0% ± 1.5%**. Keep these historical numbers unchanged: they are means over
the reported per-run accuracies, not a newly completed matched experiment.
All five Harbor summaries record 30 trials and zero infrastructure errors.
Original runs 1 and 3 evaluate fewer than the intended 30 tasks. The summaries
alone do not establish why outputs are absent, so they must not be silently
reclassified as successful 30-task evaluations or imputed as failures.

Methodology still requiring coordination:

- Resolve missing-output treatment and explicitly pin the same 30 IDs before a
  new comparison. Historical subset wording alternates between “sampled,”
  “selected,” and “first 30”; retain exact task manifests rather than relying
  on the wording alone.
- Align and record budgets, prompts, tools, model snapshot, judge configuration,
  dependency versions, and exact source revisions. The public rerun config
  specifies Harbor `max_turns: 30` and `max_tokens: 10000`, while the documented
  original-side command uses `--max-iterations 50`. The summaries do not prove
  those are matched historical budgets.
- A README command that decrypts the full dataset into `queries.tsv` does not
  itself select the historical 30-task manifest. Any future reproduction must
  make that filtering explicit.
- Range overlap is descriptive evidence; it does not establish equivalence,
  resolve the denominator mismatch, or replace maintainer acceptance.

Do not initiate new paid parity runs or change methodology solely to satisfy a
metadata check. The migration request explicitly asks for coordination first.

## Oracle and supplementary runs are separate evidence

The [oracle aggregate](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_oracle_run1.json)
records 830 trials, zero errors, and mean reward 1.0 under
`oracle__BrowseComp-Plus-Prebuilt`. This supports historical task/reference-solution
wiring, not matched model parity, independent judge agreement, or current
Docker/Daytona compatibility.

Supplementary Harbor-only evidence remains outside the primary parity row:

- [Claude Code + GPT-5 mini aggregate](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_harbor_claude_code_gpt5_mini_run1.json):
  historical adapter documentation reports `claude-code@2.1.79`, 27.6% on 29
  completed tasks, one run. There is no corresponding original-side run.
- [Claude Haiku run 1](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_harbor_claude_code_claude_haiku_run1.json),
  [run 2](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_harbor_claude_code_claude_haiku_run2.json),
  [run 3](https://huggingface.co/datasets/harborframework/parity-experiments/blob/43f79cfe925071d01dcf4dc3b1efc6831b0c00db/adapters/browsecomp_plus/results_collection/result_harbor_claude_code_claude_haiku_run3.json):
  `claude-code@2.1.119` / `claude-haiku-4-5-20251001`, recorded accuracies
  30.00%, 23.33%, 23.33%. Run 1 had six infrastructure/setup errors; the later
  runs completed 30 tasks after targeted resumes. Historical mean ± sample SEM
  is 25.6% ± 2.2%; no original-side comparison is claimed.
- Earlier high Daytona Claude Code scores affected by answer leakage are
  invalid benchmark scores. The adapter documentation already records that
  incident; migrating the source does not rehabilitate those scores.

No separate controlled verifier-agreement experiment was established by this
audit. Oracle success and use of an LLM judge must not be described as verifier
agreement or new model parity.

## Dataset publication and related contribution scope

[harbor-datasets#180](https://github.com/harbor-framework/harbor-datasets/pull/180)
was merged on 2026-04-07. It is a historical dataset contribution link, not proof
that the migrated runtime or a `harbor run --dataset` registry entry is current.
The open [publication/contamination issue #246](https://github.com/harbor-framework/harbor-datasets/issues/246)
reports plaintext BrowseComp-Plus exposure and proposes encrypted/scaffolding-only
publication. Its registry-availability observations are that issue author's
report, not independently re-audited here. Keep migration artifacts free of
decrypted tasks and seek maintainer direction before any dataset republication.

The email's related [harbor#2355](https://github.com/harbor-framework/harbor/pull/2355)
by `@JoyboyBrian` was migrated to
[adapters#44](https://github.com/harbor-framework/adapters/pull/44), which was open
when checked. It implements **BrowseComp**, the 1,266-question OpenAI benchmark,
with a pinned one-shot reference protocol and a separate agentic web-search
lane. This migration implements **BrowseComp-Plus**, the 830-query fixed-corpus
variant from `texttron/BrowseComp-Plus`. Their task counts, retrieval settings,
reference agents, and parity artifacts must not be conflated. Cross-link the
contributions for review coordination; no shared implementation or combined
parity result is claimed.
