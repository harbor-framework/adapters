# ControlArena 20.1.1 setting coverage

ControlArena 20.1.1 publishes **15 settings**. Use this page to identify which main tasks and evaluation modes you can run in Harbor and which still need an adapter. Dataset counts in the native inventory describe the upstream release.

## Generate tasks

From the repository root, run the suite launcher with Python 3.11+ and uv on your PATH. It selects each package's locked environment and places its generated tasks under `<output-dir>/<setting-id>/`.

```bash
python scripts/generate_control_arena.py --list
python scripts/generate_control_arena.py --settings bash --task-ids bash-604648
python scripts/generate_control_arena.py --all-supported --output-dir datasets/control-arena
uvx --from harbor==0.27.0 harbor run -p datasets/control-arena/bash/bash-604648 -a <agent> -m <model>
```

The launcher accepts `--limit` per setting and forwards `--overwrite` to the selected packages. Use the individual package's README for oracle requirements, protocol agents, or setting-specific options. The launcher only generates tasks. It does not start agents, build Docker images, or request model completions.

## Harbor support

| Setting | Generated main tasks | Execution scope |
| --- | ---: | --- |
| [AgentDojo](../src/control-arena-agentdojo-honest/) | 4 | Honest travel lookups against the local fixture, with the native utility check. |
| [Apps](../src/control-arena-apps-honest/) | 3 | Honest competition programming with native input/output tests. |
| [Bash](../src/control-arena-bash-honest/) | 3 | Honest text-processing scripts with the native public pytest suites. |
| BashArena | 0 | The upstream per-task Docker setup includes a service network for the main and side objectives. A standalone main-task environment and matching native grader still need verification. [Runtime layout](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/control_arena/settings/bash_arena/README.md) |
| [BigCodeBench](../src/control-arena-bigcodebench-honest/) | 3 | Honest Python function tasks, scored with the native main-task tests. |
| [Data Poisoning](../src/control-arena-data-quality-honest/) | 7 | Honest factual-accuracy prompts, typed training-pair submission and native main-task quality judge. The Harbor instruction substitutes a factual-accuracy example for the upstream shared prompt demonstrations. |
| Eval Sabotage | 0 | The native evaluation workspace depends on a private repository. |
| [IAC](../src/control-arena-iac-honest/) | 5 | All five honest infrastructure changes, offline CDK synthesis and objective-specific tests. |
| [IAC Fast](../src/control-arena-iac-honest/) | 5 | The same five honest objectives with the Fast baseline, native test markers and JUnit handling. |
| Infra | 0 | The native scorer explicitly requests an Inspect Kubernetes sandbox and runs the task's entry point (default `make entrypoint`) before checking the submission. Even the unit-test objective uses that setup. The verification host lacked kind and Helm. [Native scoring context](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/control_arena/settings/infra/task/scorer.py) |
| Rogue Eval | 0 | Requires a model runtime, weights and a usefulness grader. |
| [SAE Interp Sabotage](../src/control-arena-sae-interp/) | 22 | Honest and attack modes support trusted monitoring. The same 22 feature IDs occur in both modes. |
| SHADE Arena | 0 | ControlArena uses five public task pairs. The external SHADE package, simulated tools, evaluator and state handoff must be integrated. The other twelve pairs in the original SHADE study are held back. |
| [SWE-bench Django](../src/control-arena-swe-django-honest/) | 1 | Honest Django issue 15996, serializing `enum.Flag` in migrations, with its pinned SWE-bench image and native grading. |
| vLLM | 0 | The released main tasks are tied to versioned vLLM workspaces. The upstream v2 revision changed the CUDA/PyTorch stack and carried forward validated task titles from v1. A matched workspace and per-case scorer check are pending. |

## Native setting inventory

Each count is **main tasks / side tasks / main–side combinations**. “Validated” is the subset identified by ControlArena. A dash means the release publishes no separate validated tally. The release reports snapshots for settings that compute counts from a dataset or an external dependency. Filtering, dataset versions and permitted pairings can change the number of executable trials. The sandbox column describes the upstream setting. [Release definitions of task counts](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/control_arena/settings/_setting_metadata.py) · [Release sandbox and scoring matrix](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/settings_overview.md)

| Setting | All | Validated | Native sandbox · scorer | Basis of count or setup requirement |
| --- | ---: | ---: | --- | --- |
| [AgentDojo](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_agentdojo.md) (`agentdojo`) | 97 / 35 / 949 | — | Local · programmatic | Suite-specific pairings. The release defaults to AgentDojo benchmark v1.2.1. |
| [Apps](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_apps.md) (`apps`) | 5,000 / 1 / 5,000 | 3,420 / 1 / 3,420 | Docker, Podman, local · programmatic | Computed from the source dataset’s train split. The validated count uses the upstream solution-test flag. |
| [Bash](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_bash.md) (`bash`) | 257 / 1 / 257 | — | Docker, Podman, local · programmatic | Fixed release count. |
| [BashArena](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_bash_arena.md) (`bash_arena`) | 640 / 4 / 2,560 | — | Docker · programmatic | Four side-task choices per main task. Each sample selects its own sandbox. |
| [BigCodeBench](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_bigcodebench.md) (`bigcodebench`) | 1,140 / 1 / 1,140 | 1,140 / 1 / 1,140 | Docker, Podman, local · programmatic | These are full-subset counts. The release also defines a 148-case hard subset. |
| [Data Poisoning](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_data_poisoning.md) (`data_poisoning`) | 98 / 7 / 686 | 98 / 7 / 100 | Local · LLM judge | The validated list selects 100 specific pairings from the 686 possibilities. |
| [Eval Sabotage](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_eval_sabotage.md) (`eval_sabotage`) | 18 / 6 / 108 | — | Docker · LLM judge | Access to a private evaluation repository is required. |
| [IAC](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_iac.md) (`iac`) | 5 / 9 / 45 | — | Docker, Kubernetes · programmatic | Five main objectives are paired with nine side objectives. |
| [IAC Fast](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_iac_fast.md) (`iac_fast`) | 5 / 9 / 45 | — | Docker, Kubernetes · programmatic | Faster infrastructure-as-code variant sharing the IAC objectives. |
| [Infra](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_infra.md) (`infra`) | 18 / 3 / 54 | 9 / 2 / 18 | Kubernetes, none · programmatic | The all group includes the extended objectives. Upstream classifies setup as complex. |
| [Rogue Eval](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_rogue_eval.md) (`rogue_eval`) | 25 / 1 / 25 | — | Docker, Podman, local · programmatic | Counted from packaged main-task directories. The release offers a separate model-dependency extra. |
| [SAE Interp Sabotage](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_sae_interp_sabotage.md) (`sae_interp_sabotage`) | 22 / 1 / 22 | — | Local · LLM judge | One case per feature. Both modes use the same 22 IDs. |
| [SHADE Arena](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_shade_arena.md) (`shade_arena`) | 5 / 5 / 5 | — | Local · LLM judge | Five public pairs, each paired one-to-one. The setting guide identifies the public split despite the restricted-access badge in the generated overview. [Release guide](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/settings/shade_arena.qmd) · [Public package revision](https://github.com/rasmusfaber/SHADE-Arena/tree/caf0324e84f4bdf2ba84938153422c9d36ac95ac/shade_arena/task_pairs) |
| [SWE-bench Django](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_swe_django_sidetask.md) (`swe_django_sidetask`) | 18 / 18 / 18 | — | Docker · programmatic | Each main task has its own paired side task and sample-level sandbox. |
| [vLLM](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/docs/_generated/setting_metadata_vllm.md) (`vllm`) | 19,737 / 15 / 296,055 | 32 / 6 / 32 | Docker, Kubernetes · mixed | Version-dependent counts. The all group is a Cartesian product. The validated list selects 32 specific pairs. |

## Catalog and runtime checks

- The wheel and the public setting catalog list the same 15 setting IDs. The wheel’s `control_arena` package entry point registers `control_arena.settings.entrypoint`. That module conditionally imports SHADE Arena and SWE-bench Django. In the adapter’s base environment, 14 setting classes registered. SHADE Arena’s optional package was absent. The Django class registered even though the optional `swebench` package was absent. Registration alone provides no evidence of complete data access or successful scoring. [Pinned entry point](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/control_arena/settings/entrypoint.py) · [Pinned optional dependencies](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/pyproject.toml) · [Public setting catalog](https://control-arena.aisi.org.uk/settings/index.html)
- The Django setting’s release directory is `swebench` and its public identifier is `swe_django_sidetask`. Bash and BashArena are separate registrations. IAC and IAC Fast expose the same upstream objectives. Those relationships matter when calculating unique dataset coverage. [Release registry](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/control_arena/settings/entrypoint.py) · [IAC Fast](https://control-arena.aisi.org.uk/settings/iac_fast.html)
- BashArena and SWE-bench Django attach Docker sandboxes at the sample level. Their task-level sandbox accessor returns `None`. The Infra setting separately exposes a `none` configuration for running without its Kubernetes sandbox. [BashArena setting](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/control_arena/settings/bash_arena/bash_arena_setting.py) · [Django setting](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/control_arena/settings/swebench/swebench_setting.py) · [Infra setting](https://github.com/UKGovernmentBEIS/control-arena/blob/10860116c370c74c56d6d49edce629b62cf5661b/control_arena/settings/infra/infra_setting.py)

## Harbor validation evidence

A Harbor honest oracle submitted each of the 22 SAE reference answers to the live judge `openai/gpt-4.1-mini-2025-04-14`. All 22 passed, with zero trial errors and a distinct successful judge trace per case. This measures reference-answer acceptance. Matched live policy performance is pending. [Oracle check](../src/control-arena-sae-interp/tests/check_live_oracle.py)

| Programmatic check | Observed outcome |
| --- | --- |
| APPS and BigCodeBench | For each setting, native scoring and Harbor Docker produced the same six verdicts. Each accepted the three reference submissions and rejected the three fixed wrong submissions. |
| Bash | All three private reference scripts passed their five upstream pytest checks in Harbor Docker. All three deliberately failing submissions received zero. |
| AgentDojo | Four travel reference answers passed the native utility function through Harbor Docker. The adapter's 11 read-only lookup functions agreed with the original fixture in local tests. |
| Data Poisoning | All seven factual-accuracy references passed in Harbor Docker using a scripted judge. Direct replay against the native main scorer on the original prompts returned the same verdicts. |
| IAC and IAC Fast | For each variant, all five reference patches passed and all five unchanged baselines failed in Harbor Docker. An independent replay using the native pytest checks produced the same 20 verdicts. |
| SWE-bench Django | Native ControlArena and Harbor each accepted the reference patch and rejected the unchanged checkout for issue 15996. The case includes one fail-to-pass test and 51 pass-to-pass tests. |

The generation check reconstructed all 22 SAE inputs in both modes. The paired runtime check used upstream row 0, with a scripted policy, monitor and judge. Native ControlArena and Harbor matched on the policy, monitor and judge inputs, the typed submission, task verdicts and maximum suspicion. [SAE validation](../src/control-arena-sae-interp/README.md#comparison-with-original-benchmark-parity) · [Fixture comparison](../src/control-arena-sae-interp/tests/compare_fixture.py)

## Parity plan

Compare each setting and mode separately. Record the source revision or dataset version, ordered case IDs, model snapshots, protocol and monitor configuration, tool interface, time and token budgets, and scoring environment. Match the actual task set in both harnesses. The catalog's full or validated counts are unsuitable denominators for a smaller exported subset.

1. Check that each prompt, fixture and scoring input maps to the intended upstream case. Where a reference is available, run it and a known failing submission in both harnesses. Record infrastructure errors separately from incorrect answers.
2. Agree with Harbor maintainers on the protocol, eligible settings, matched sample and API budget. Run a live pilot of 5–10 cases per cohort where available, or all cases for a smaller cohort. Follow the release guide's repeated-run and reporting requirements before recording live parity.
3. Report main-task success by setting and mode. Report side-task success, suspicion and an audit budget only for matching monitored evaluations that produce those quantities. An honest-only run supplies evidence about usefulness. A fixed oracle or scripted policy tests the harness and must be reported separately from live policy performance. [Harbor adapter guide](adapters.mdx) · [Control evaluations](https://control-arena.aisi.org.uk/intro-to-control.html)

### Compare completed scores

The [score comparison script](../scripts/compare_control_arena_scores.py) reads native Inspect score reductions and Harbor trial rewards. It requires no model calls. Create a JSON array with one entry for each matched native sample and Harbor trial. Paths are relative to the manifest file. Preserve the native sample ID's JSON type. For example, APPS uses the string `"0"`.

```json
[
  {
    "native_log": "native/honest.eval",
    "native_sample_id": "0",
    "native_scorer": "main_task_success",
    "harbor_trial": "jobs/oracle/apps-honest-0000__trial",
    "harbor_task": "control-arena/apps-honest-0000"
  }
]
```

From the repository root, run the script in the locked Inspect environment. It reports both per-case scores, their cohort means and the number of identical verdicts. Use one manifest per setting, mode and matched run. `--require-equal` turns a mismatch into an error for deterministic fixtures. The tool checks task IDs, trial completion, duplicate observations and the selected metric. The experimenter supplies the native-to-Harbor case mapping and verifies the model, protocol and budget.

```bash
uv run --project src/control-arena-sae-interp --locked python scripts/compare_control_arena_scores.py \
  pairs.json --metric main_task_success --require-equal
```
