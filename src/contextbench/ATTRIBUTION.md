# ContextBench-on-Harbor attribution rule

`attribution_version: 6`

This document defines how the Harbor ContextBench adapter attributes repository
context to an agent from its ATIF trajectory. The code in
`src/contextbench/attribution/` implements it; where they disagree, the code has
a bug. The verifier records `attribution_version` in
`contextbench-metrics.json`, and scores produced under different versions are
not comparable.

## Why a written rule

ContextBench scores which repository context an agent examined against gold
annotations. Upstream defines "examined" per agent framework, through one
extractor per framework. This adapter applies one rule to every agent, states it
here, versions it, and labels every score with it.

## Inputs

The verifier attributes one ATIF trajectory (with its continuation and subagent
trajectories) against a clean checkout of the task's base commit. It also reads
the task's repository roots from `tests/attribution.json`.

### Repository roots

The roots are the absolute paths at which the agent's environment mounts the
repository:

- A generated task lists `/workspace` and the task's native repository path:
  `/testbed` for SWE-bench Verified and SWE-PolyBench, `/app` for SWE-bench Pro,
  and `/home/<repo>` for Multi-SWE-bench. In the agent image `/workspace` is a
  link to the native path.
- A parity task, prepared by `parity/prepare.py`, lists its OpenHands
  workspace, `/workspace/<owner>__<repo>__<version>`, and the SWE-bench image's
  own checkout, `/testbed`, which the parity image keeps. Calibration and the
  rescores of the retained parity trajectories use the same two roots. `/workspace`
  itself is not a root there: it holds only the workspace directory.

A path resolves as follows:

- An absolute path under a root resolves exactly, relative to the longest root
  it is under. There is no suffix search, and the directory test applies only to
  the exact path.
- A relative path resolves against the call's working directory: the checkout
  root, a `workdir`-style argument, or the target of a `cd` in the command.
- Any other absolute path names nothing in the checkout. It earns no request
  credit, but it can still be a receipt hint (below).

## Evidence

Credit comes from two sources, and from nothing else.

### Structured reads

A call of a read or multi-read tool whose path argument resolves to a checkout
file is credited with that file. A path that resolves to a directory is
discovery. A path that does not resolve earns no request credit; the call's
output is then validated as receipts.

A read credits the lines it declares, clamped to the base file. A range that
starts past the end of the file is dropped, and a read without a usable range
credits the file without spans. Declared lines are 1-based and inclusive. The
range arguments and their index bases come from each agent's published tool
schema at the version Harbor 0.26.0 installs:

| Tool schema | Range arguments | First line |
| --- | --- | --- |
| OpenHands `str_replace_editor`, OpenHands SDK `file_editor`, Strands `sandbox_file_editor`, Copilot CLI `view` | `view_range` | 1 |
| Claude Code `Read`, OpenCode `read`, Pi `read`, OpenClaw `read`, Hermes `read_file`, MiMo `read`, muse-code `read_file`, Devin `read`, Cursor `read_file`, and every other `offset` | `offset`, `limit` | 1 |
| Qwen Code `read_file` (with `file_path`) | `offset`, `limit` | 0 |
| Mistral Vibe `read_file` (with `path`) and Cortex Code `read` (with `file_path`), in a trajectory whose `agent.name` is `vibe` or `cortex-code` | `offset`, `limit` | 0 |
| kimi-code `Read`, kimi-cli `ReadFile` | `line_offset`, `n_lines` | 1; a negative `line_offset` is a tail read without declared lines |
| fx `read_file` | `start_line`, `line_count` | 1 |
| Gemini CLI `read_file` | `start_line`, `end_line` | 1 |

Any other range argument declares no lines, and the read credits its file
without spans. A `view_range` that ends at `-1`, to the end of the file,
declares no lines either, as in the upstream OpenHands extractor. No inspected
schema names its path `absolute_path`, the key of older Gemini CLI and Qwen
Code releases.

The rule chooses the index base by tool name and path key. Two 0-based
schemas share both with a 1-based one: Mistral Vibe's `read_file` (`path`, as
in muse-code) and Cortex Code's `read` (`file_path`, as in Claude Code).
Trajectory decoding tells them apart by the trajectory's ATIF `agent.name` and
restates their `offset` as 1-based before the rule reads it. Some read tools
name their path in a way the rule does not model, so only their receipts count:
Grok Build's `read_file` (`target_file`), Antigravity CLI's `view_file`
(`AbsolutePath`), Gemini CLI's `read_many_files` (`include` patterns), and
Cline's `read_files`, which is not a read-family tool name. None of these
agents appears in a retained corpus.

Once a structured mutation (an edit or write tool, or a file editor's non-view
command, that did not report failure) has changed a file earlier in the same
trajectory, a read of that file earns the file plus only the spans that its own
output validates against the base. Declared lines would name the edited file.

### Receipts

Text in a tool observation is credited when it validates against the base
checkout. The receipt kinds are:

1. **Diffs.** A unified-diff hunk is read by its header counts: context lines
   validate at their old and new coordinates, `-` lines at their old ones and
   `+` lines at their new ones. A normal-diff record (`3,4c3`) is read by its
   change ranges, against the command's first and second path hint. Only
   diff-shaped lines are consumed, whether or not they validate. A line that
   does not fit closes the hunk or record and goes to the other receipts, so a
   `cat` before a `git diff`, or a two-commit `git log -p`, keeps its credit.
2. **`path:line:content` and `path-line-content` lines.** One such line credits
   its line, and so its file. Upstream credits multi-file grep output with
   nothing; this difference is intentional and measured below.
3. **Numbered lines** (`N:`, `N<tab>`, `N<two spaces>`, `N|`). With a path hint,
   each line counts on its own if the hinted file has that text at that line.
   Without one, a line counts only among two or more consecutive output lines
   that locate in the same file. When the command names exactly one file,
   grep's `N-content` context lines are numbered lines too. A nested
   `grep -n ... FILE | grep -n ...` line is read by its inner line number when
   that reading validates in exactly one named file.
4. **Path-prefixed runs** (`path:content`, `path-content`). Consecutive lines
   that name the same file and match a unique source run of it, with at least
   two non-blank lines.
5. **Unnumbered runs.** Consecutive output lines that match one checkout-unique
   run of source. A run in a hinted file needs two non-blank lines, and any other
   run needs three (below).

Output that only lists checkout paths is discovery. Everything else, including
program output and test runs that show no source, is `non_base_context`.

#### Hints

Command text never earns credit. It supplies hints:

- the working directory;
- path hints: every command token that resolves to a checkout file, including
  glob matches. A relative token may also match one checkout path by suffix,
  and an absolute token outside the roots loses leading components until it
  names a file, as ContextBench's evaluator does;
- directory hints: tokens that resolve to a checkout directory, except a `cd`
  target, the working directory and the checkout root;
- authored text: command lines, whose echo is ignored.

A file is hinted when it is a path hint or lies under a directory hint. For a
structured call, the path arguments supply the hints in the same way.

#### Blank lines

A blank (whitespace-only) line is never evidence: it does not validate on its
own in a diff, a numbered line, or a run, and a run never starts or ends at one.
A blank line displayed between two validated lines of a file, at a blank source
line, joins them into one span. So lines 10-20 with a blank line 13 are one span
whether a ranged read, `sed -n`, `cat -n`, or `git diff` displayed them. A diff
whose only base-matching lines are blank earns nothing.

#### The unhinted run floor

A two-line run in a file the command did not name is a chance match with
generated output often enough to matter: in the 2026-08-21 corpus, a migration
script's printed output matched two lines of a migration fixture. Runs in
unhinted files therefore need three non-blank lines. Sweeping the floor `N` over
the retained corpora:

| Corpus | N | Gold-file hits | Predicted files | Calls changed against N=3 |
| --- | ---: | ---: | ---: | ---: |
| 2026-08-21 corpus (10 trajectories, 23 gold files) | 2 | 19 | 54 | 3 |
| | 3 | 19 | 53 | 0 |
| | 4 | 19 | 53 | 0 |
| | 5-8 | 19 | 53 | 1 |
| Three-run parity, Harbor side (30 trajectories, 69 gold files) | 2-4 | 53 | 165 | 0 |
| | 5-7 | 53 | 165 | 1 |
| | 8 | 53 | 164 | 2 |

No floor from 2 to 8 changes a gold-file hit. On the native side of the parity
experiment, three changes one call: it removes three lines that
`python -c "...inspect.getsource(...)"` printed from
`lib/matplotlib/__init__.py`, a real display of source, and no file.

#### Whole-file views

When one call's receipts show every non-blank line of a file, the file is
credited without spans. An unranged structured read is credited the same way,
and upstream's extractors treat whole-file views alike: OpenHands credits
unranged reads, `cat` and single-file `grep` with the file only, mini-swe-agent
credits `cat` with the file only, SWE-agent credits nothing for an unranged
view, and Agentless and Prometheus credit only declared locations. So an
unranged read, `cat`, and `cat -n` of one file project identically. A structured
read with an explicit range keeps its clamped spans, which the oracle needs.

The rule has two costs:

- Paging a file in two calls earns spans where one call earns none. Upstream
  has the same cliff.
- `sed -n '1,200p'`, or `head`, on a short file counts as `cat`. In the
  retained corpora no `sed -n` call was affected. On the Harbor parity side one
  call, `cat tests/README.rst | head -30` on a ten-line file, keeps no spans,
  and the corpus's 15,115 predicted lines become 15,105. On the native side one
  unranged view of a file the agent had edited, credited from its output, keeps
  no spans, and 14,972 lines become 14,803.

#### Ignored text

Before validation the observation is split into lines at `\n`, with one trailing
`\r` removed, as ContextBench numbers lines; checkout files are split the same
way. ANSI escapes and `[stdout]`/`[stderr]` prefixes are removed. These lines
are ignored:

- lines equal to the command's own lines, also after a shell prompt;
- pytest's failure markers: a line starting in column 0 with `>` or `E` followed
  by three spaces;
- the line after a Python traceback frame (`File "...", line N`), which repeats
  the frame's source.

Indented `>>>` doctest prompts are source.

## Failure precedence

A result is failed when its producer metadata says so: an `error` payload,
`is_error`/`isError`/`tool_result_is_error` set, `success` set to false, or
mini-swe-agent's `exception_info`. Precedence depends on the family:

- A failed read or multi-read earns nothing, because its credit would come from
  its arguments.
- Every other family that reaches receipt validation, including background
  polls and offloaded content, is credited for what its output validates.
  Validated receipts prove themselves. A failed call whose output validates
  nothing is a `tool_error`.

Harbor's OpenHands converter records no failure metadata, so the parity
trajectories never exercise this.

## Classification

Every tool call receives one classification in the verifier's evidence:

- `projected`: credit was emitted.
- `discovery_only`: a path-discovery tool, a read of a directory, output that
  only lists checkout paths, or a search tool whose output shows no source.
- `intentional_non_context`: a mutation, agent bookkeeping, subagent
  coordination (the subagent's own trajectory is scored), copied continuation
  context, or output already credited through a background or offloaded source
  call.
- `non_base_context`: a known tool whose output has no base-checkout source, or
  that recorded no output at all; external fetches.
- `tool_error`: a failed call that earned nothing.
- `unmapped`: an unknown tool whose output validated nothing, or a known tool
  without an attribution contract (`lsp`, `read_mcp_resource`). This is the
  false-negative surface: tools the rule set does not model, such as Claude
  Code's `Monitor`, `Workflow`, `ListAgents` and `ReportFindings`.
- `malformed`: a call whose results cannot be matched to it (below), or a call
  whose examination raised; the latter keeps a truncated traceback.

`unmapped_tool_call_count` counts `unmapped` and `malformed` calls.

Each evidence record names, in `heuristic`, the step of the rule that decided
the call. `rules.py` defines every step. They apply in this order, and the
first that decides a call wins:

1. `atif.copied_context` and `atif.unpaired_results`, decided before the call
   is examined.
2. `common.background.deduplicate` and `common.offloaded.deduplicate`. A poll
   of an uncredited shell call is decided by the steps below, with that call's
   arguments.
3. `common.static`: discovery, mutation, bookkeeping, external, unattributed
   and subagent tools.
4. `common.tool_error`, `common.read` and `common.multi_read`: structured reads.
5. `common.observation`: receipts.
6. `common.known_no_credit`: a known tool whose call shows no output.
7. `registry.unmapped`: an unknown tool that no step above decides.

`registry.contained_failure` marks a call whose examination raised.

Structural trajectory errors stay verifier errors, not classifications: a
non-object step or call, a non-string call ID, duplicate call IDs, a result
that names an unknown call, and missing, remote, escaping or cyclic trajectory
references.

## Producer decoding

Decoding may depend on the producer; attribution may not.
Decoding recovers what each call and observation was:

- **Result matching.** A result matches the call it names. When no result in a
  step names a call and there is one result per call, they pair in order. A
  Terminus batch of shell calls with one shared terminal result is split at the
  shell prompts. Otherwise, when results without a call ID carry content, the
  step's calls that no result names are `malformed`, and the rest of the
  trajectory is scored.
- **Envelopes.** Codex's `Chunk ID`/`Wall time`/`Process exited` header,
  Cursor's `{"success"}`/`{"failure"}` JSON, and mini-swe-agent's
  `{"returncode", "output"}` JSON (or its elided `output_head`/`output_tail`
  form, joined around a marker line) are unwrapped.
- **Read offsets.** In a trajectory whose `agent.name` is `vibe` or
  `cortex-code`, the 0-based `offset` of Vibe's `read_file` (with `path`) and
  Cortex Code's `read` (with `file_path`) is restated as 1-based.
- **Background and offloaded output.** A background poll is attributed with the
  arguments of the shell call that started it, and is not counted again when
  that call was credited. Offloaded content already represented by a credited
  call is not counted again.
- **References.** Subagent and continuation trajectories are followed within
  the trajectory directory, and each is traversed once.

Two Harbor 0.26.0 converters lose information that this decoding cannot
recover; both are candidate Harbor issues:

- The OpenHands converter gives every action of a multi-call model response the
  first call's arguments (`harbor/agents/installed/openhands.py:361-366`). A
  structured read is credited from its arguments, so a parallel batch of reads
  would credit the first call's file to every read. None of the 60 retained
  OpenHands logs has a multi-call response.
- The mini-swe-agent converter drops `source_call_id` from tool results, and
  appends the harness's format-error message to the previous step's
  observation. A step with a format error therefore has more results than
  calls. Which result belongs to which call is then not recorded, so the rule
  does not guess: the step's calls are `malformed`, and the credit is lost to
  the converter defect. In the 8 retained mini-swe-agent trials, 8 of 104 calls
  are.

## Differences from upstream's extractors

ContextBench's OpenHands extractor credits requests: a single-file `grep` or
`cat` is credited with its file whatever it printed. This rule credits what was
displayed. Measured on the retained OpenHands trajectories, scored with the
vendored evaluator:

- **File coverage is the same.** On the 30 Harbor parity trajectories the rule
  and the upstream extractor hit the same gold files in every trajectory: 19, 17
  and 17 of 23 per run. On the 30 native histories, converted to ATIF with
  Harbor's converter, the rule hits 18, 18 and 20, as the native extractor does.
  On the 2026-08-21 corpus the rule hits 19 of 23 and the extractor 20. The
  difference is request against receipt semantics: the extractor credits
  `django/db/models/sql/query.py` for a single-file `grep` whose output was
  empty, and the rule credits only what an output shows.
- **The rule predicts more files.** On the 30 Harbor parity trajectories it
  predicts 55, 59 and 51 files per run against the extractor's 52, 52 and 51.
  Of its 12 extra files, 7 come from recursive greps (6 from the
  `path:line:content` lines of one `grep -rn`), 2 from single-file greps with
  context lines piped to `head`, 2 from source lines that pytest displayed in
  tracebacks, and 1 from ten genuine context lines of a historical diff. The
  extractor's 2 extra files come from single-file greps whose output was
  empty.
- **The rule has more, narrower spans.** On the same trajectories it predicts
  631 spans and 15,105 lines against 218 spans and 14,364 lines: receipts credit
  each displayed run, where the extractor credits declared ranges.

## The test oracle and calibration

ContextBench's pinned OpenHands extractor (vendored byte-identical at commit
`1436c28a8eb95496da4ea69ad458b9f8a8eb7d61`) is not a scoring path. It is the
test oracle: the one upstream-authored definition of retrieval that exists for
any agent.

`parity/calibrate.py` fetches the published parity bundle
(`harborframework/parity-experiments`, revision
`8d887bf0ff1ee04a8a6307d85dd187994375e0d8`) and checks every file against the
bundle's checksum manifest, whose own SHA-256 the script pins. It then fetches
the five task repositories at their base commits and projects two corpora under
the rule and through the oracle: the ten 2026-08-21 trajectories and the 30
Harbor trajectories of the three-run parity experiment. It compares both with
the pinned `parity/calibration-summary.json` and
`parity/calibration-summary-parity-runs.json`, which record per trajectory the
file, span, line and gold-file counts of each side and a digest of each
projection, and exits non-zero on any difference. With
`CONTEXTBENCH_CALIBRATION_DIR` set to its work directory, the retained-corpus
tests also run: they recompute the 2026-08-21 rescore through the production
scorer and compare both sides with the pinned summaries.

`parity/calibrate.py` is the required check before any change to the code in
`src/contextbench/attribution/` is merged. This repository has no per-adapter
CI, and a default `pytest` run skips the retained-corpus tests, so nothing else
ties the rule to the retained corpora. A change that alters a pinned summary
changes credit: it bumps `attribution_version`, adds an entry to the version
history below, and rewrites the pins with `--update`.

`parity/run_harness_parity.sh rescore` replays the retained parity trials
through Harbor and the generated tasks' verifier under the current rule, and
writes the harness-by-extractor table (`parity/README.md`).

## What the evidence does and does not prove

- The parity experiment compares OpenHands run natively and through Harbor on
  ten tasks, three runs per side, after aligning prompt, image, workspace and
  collection. It tests the harness, not the default task image or instruction.
- The calibration pins this rule's relationship to the upstream extractor on
  shared inputs, and makes any change to it visible.
- Nothing certifies that any extraction definition is the true one for agents
  ContextBench never covered. The rule is a definition, held to what a
  definition can meet: specified, versioned, applied to every agent alike, and
  calibrated.

## Version history

- **6.** Structured reads declare lines only through the range arguments of an
  inspected Harbor 0.26.0 tool schema. The spellings that no schema uses
  (`viewRange`, `line_ranges`, `lineRanges`, `ranges`, `line_range`,
  `lineRange`, `lineOffset`, `line_start`/`line_end`, `startLine`/`endLine`,
  and OpenHands' `FileReadAction` `start`/`end` with its `start = 0` rule) no
  longer do, and no call in the retained corpora uses them. Mistral Vibe's
  `read_file` and Cortex Code's `read` count `offset` from 0, told apart from
  the 1-based schemas they resemble by the trajectory's `agent.name`; neither
  agent appears in a retained corpus. Every projection is unchanged.
- **5.** Blank lines are never evidence but join validated lines; runs in
  unhinted files need three non-blank lines; unhinted numbered lines need two
  consecutive agreeing lines; grep context lines count with one file named.
  Diffs consume only diff-shaped lines. A whole-file view credits the file
  without spans. Lines split on `\n` only. Paths resolve exactly under
  per-task repository roots; other absolute paths are only receipt hints.
  Declared ranges are clamped, parsed for kimi-code, fx and Qwen Code, and
  replaced by receipts after a structured mutation. Failure precedence covers
  only reads. Results without call IDs pair in order, mini-swe-agent envelopes
  are decoded, and output-less known calls are `non_base_context`. Rule IDs
  lost their `.v1` suffix. On the three-run parity trajectories the Harbor
  scores became 0.826087, 0.739130 and 0.739130 (from 0.869565, 0.826087 and
  0.826087): version 4 credited one task with five gold-file matches across
  the three runs from blank lines in the diff of an older commit.
- **4.** Producer failure metadata takes precedence over all retrieval evidence.
- **3.** One rule for every agent. The isolated OpenHands reference mode was
  removed as a scoring path; the pinned native extractor became the test oracle.
- **2.** Two modes: an OpenHands reference mode, bit-compatible with the pinned
  native extractor, and a receipts rule for all other agents.
- **1.** Profile-based design with per-agent shell vocabularies. Not stamped in
  diagnostics.
