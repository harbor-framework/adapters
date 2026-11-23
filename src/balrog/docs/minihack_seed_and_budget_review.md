# MiniHack reset ordering and Boxoban budget review

The fixed scope remains the eight native configured task types and seeds 0..4
for every task. No task or seed was replaced to obtain a successful oracle.
The native maximum episode length remains 100 actions.

**Reason for the remaining 39/40 result:** `minihack-boxoban-hard-v0-seed-0`
cannot be solved within that upstream budget. Independent push-level A* and
single-action breadth-first search both give a shortest solution of **104
legal cardinal moves** for the correctly seeded board and the movement rules
validated below. The unmodified native game truncates at action **100**, at
progression 0. This is an upstream episode-budget constraint, not a failure
introduced by the Harbor adapter. It does not describe the other 39 instances.

The proposed remedy is already filed as [BALROG PR #70](https://github.com/balrog-ai/BALROG/pull/70).
It remains an unmerged Draft proposal as of 2026-11-21. The separate 200-action
experiment passes all 40 cases; it has not changed the canonical benchmark.

This WIP review links committed [baseline results](../validation/baseline.json)
and a separately labeled [budget-proposal summary](../validation/proposals/minihack_200.json).
They summarize saved local audits; full research jobs, solver programs and
candidate datasets have not been uploaded. The proposal is not adopted by the
production adapter or included in its full-oracle count.

## Reset ordering fixed to match the original evaluator

At BALROG `b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5`,
`Evaluator.run_episode` creates the environment, resets the agent, then seeds
Python and NumPy immediately before `env.reset(seed=seed)`.

MiniHack Boxoban samples a map both during construction and during reset using
Python's global `random.choice`. Seeding only before construction therefore
selects the second random map at reset. That does not match the original
evaluator, which reseeds and selects the first map at reset.

The adapter now also seeds Python and NumPy immediately before reset, including
verification replays. The original evaluator remains unchanged. The audit used
two different pre-construction random states (113 and 907) for every task:
all 40 original resets agree after the episode seed is applied; precisely the
10 Boxoban initial hashes differ from the old service ordering, while all other
30 initial hashes remain unchanged. All ten Boxoban fixtures were regenerated.
The earlier 40/40 oracle result used the wrong Boxoban map selection and is
superseded; it must not be cited as evidence for the final dataset.

## One native instance exceeds the configured budget

For correctly seeded `MiniHack-Boxoban-Hard-v0`, seed 0, an A* solver exhausted
the static Sokoban state space within 100 moves without a solution. Increasing
only the **offline abstract search bound** to 300 found a shortest 104-action
solution. The search uses only the four native cardinal moves, exact walking
costs between pushes, an admissible minimum-matching Manhattan heuristic, and
static non-goal corner deadlock pruning. It does not stop at a search limit for
this result: the 100-bound search exhausted 6,446 states; the 104-action solution
was found after 9,017 expansions in the higher-bound search.

The baseline native game was never given a larger budget. Its replay of the solution's
first 100 actions truncates with progression 0.0, identically in two fresh
original-environment replays. MiniHack disables random monster spawning and
this task exposes only cardinal moves. The 104 value is an exact result for
the stated static Sokoban model; it is not a claim of a successful native
104-step episode under a 100-step limit.

The final fixture keeps this instance, stores `oracle: null`, and labels its
100-action tape `diagnostic_not_full_oracle`. It records both the native limit
and the abstract minimum. The other nine Boxoban instances have genuine native
full-progression oracles, as do the other thirty MiniHack instances: **39/40 full
oracles**, plus this explicitly documented diagnostic.

Maintainers need to decide whether to accept this documented upstream-budget
exception or change the upstream task budget symmetrically for both parity
sides with a new pin. This adapter does not change the budget, replace seed 0,
filter the task, or award full credit to the truncated trajectory.

## Independent oracle feasibility re-audit

A second solver independently searched single native movement actions rather
than the earlier solver's push-level A* graph. Its state is the exact player
cell and the unordered four-boulder positions. It uses ordinary breadth-first
search with no heuristic, deadlock pruning, random sampling or expansion cap.
Blocked self-loop moves cannot shorten a solution. The board has 39 walkable
cells. All **796,766 states reachable in at most 100 actions** were exhausted
without a goal; continuing the search first reached a goal at **104 actions**.
The result therefore does not rely on the earlier A* heuristic or pruning.

The goal also matches the native scorer: `BoxoHack._is_episode_end` requires
the four visible boulder positions to equal the initial fountain positions.
Its success reward is exactly 1. For this Hard task, a nonterminal reward is
`-0.001 + 0.1 * newly_covered_goals`, at most 0.099 for a single legal move;
the progress wrapper therefore cannot obtain full credit through a different
positive-reward path before solving the board.

The actual pinned runtime exposes exactly `north`, `east`, `south`, and `west`
at both the text and native action interfaces. Diagonal movement, multi-square
movement, kicking, using a wand, teleporting and dropping objects are absent;
invalid strings default to the original `north` action. Four-direction input
also cannot encode a second action in the same game step.

The audit separately considered NetHack's ability to squeeze onto a blocked
boulder. Adding that mechanic to the abstract model produced a 76-action
candidate, but the unmodified native game rejected its first squeeze attempt
at action 7. This is explained by the pinned
[balrog-nle 0.9.0 source archive](https://files.pythonhosted.org/packages/74/3d/a1a258ec07611cd48a25955b6537d63a8afb2db1b1fa7fc436b3878c5b8d/balrog_nle-0.9.0.tar.gz):
`src/hack.c` requires inventory weight minus carrying capacity to be at most
`-850` for this non-tiny, non-rock-throwing character. Its two spellbooks and
four water potions alone weigh 180; carrying capacity is capped at 1,000, so
the difference cannot fall below `-820`. Equipment adds further weight. The
movement-only action set cannot remove or consume those items. The fixed
level supplies no polymorph traps or monsters that could enable a different
form, and teleporting is disabled. Thus the tested squeeze shortcut is not a
legal shortcut for this seed's elf priest.

Two fresh native executions of the independent 104-action tape's first 100
actions agreed exactly with the production game service and its fresh replay.
All 99 observable pretermination player/boulder states matched the independent
model. At action 100, native truncation replaces the board with its termination
screen; progression remains 0. No seed, budget, scorer, simulator or fixture was
changed, and no model API was used.

The [committed proposal summary](../validation/proposals/minihack_200.json)
records the separate 100-action and first-goal BFS findings, rejected squeeze
candidate, native/service comparisons and source/artifact hashes. Source-archive
checksums are separate from runtime-image and installed Python-source hashes.
The original full solver and Docker research outputs remain local; this summary
does not replace their eventual publication or independent reproduction.

An **unapplied** upstream proposal adds a
configurable 200-action allowance for Boxoban families while leaving the other
MiniHack families at 100. This is a proposed benchmark policy change, not an
oracle for the present benchmark. A separate isolated experiment temporarily
supplied a 200-action configuration and episode without modifying
the official source or fixtures. The same 104-action tape reached native score
1 in both fresh executions, with termination at action 104 and matching service
replay and verifier scores. All first 99 transitions matched the unchanged
100-action experiment. This validates the proposed budget remedy, not an
oracle under the current 100-action limit.
The patch itself remains unapplied and passed `git apply --check`. Applying it would require maintainer
agreement, a new upstream pin, regenerated manifests and symmetric native/
Harbor validation. The unchanged 100-action instance remains in the dataset
with `oracle: null`.

## Reproducibility and evidence

### Complete Harbor validation of the budget proposal

A separate generated proposal dataset was exercised with the actual Harbor
0.26.0 `oracle` agent on Linux Docker.
Only the ten Boxoban instances use the proposed 200-action budget; the other
30 MiniHack instances retain 100 actions. Seeds, task selection, source pins,
initial-state hashes and native scoring are unchanged. Proposal task names and
metadata explicitly identify the unapproved variant.

The completed job has **40/40 native/verifier rewards of 1.0 and zero trial
exceptions**. Its saved validator verified exact coverage, job/trial
completion, all 1,531 recorded native transitions, reward files, fresh replay,
proposal artifact hashes and unchanged original fixtures. The
[proposal summary](../validation/proposals/minihack_200.json) retains this evidence.
Hard Boxoban seed 0
terminates successfully on the 104th action. This is a validated candidate
remedy, not a fortieth oracle for the original 100-action benchmark.

The earlier attempt was interrupted by a local Docker engine outage and is
retained in the local attempt history. The completed replacement's CLI
then encountered a Windows GBK encoding error while printing its final summary,
after all results had been saved. Strict validation passed, and the same Harbor
summary renderer subsequently printed the saved results successfully with
Python UTF-8 mode. On Windows, enable `PYTHONUTF8=1` and
`PYTHONIOENCODING=utf-8` before launching Harbor. No trial result was edited or
rerun to hide a failure.

### Native initial score serialization

Before the first action, pinned MiniHack `BaseProgress` stores `progression=0.0`
and `episode_return=0.0` as class attributes. Its wrapper's `get_stats` exposes
only the instance `__dict__`, which is empty immediately after reset. Reading
`get_stats()["progression"]` therefore raised `KeyError` when Harbor's no-op
agent took no actions, even though the native progress object's initial value
was defined and equal to zero.

The adapter compatibility branch is restricted to MiniHack, zero recorded
actions, and a missing dictionary key. It type-checks the actual native
`BaseProgress` object and reads its `progression` attribute for both live scoring
and fresh replay. It does not hard-code a replacement score or take an extra
action. A missing key after an action, a different environment, or an unexpected
progress-object class remains an error. The regression tests are in
`tests/runtime/test_minihack_initial_score.py`.

All 40 frozen MiniHack instances were also checked with actual zero-action
finalization and independent fresh replay; the
[validation provenance](../validation/provenance.json) identifies the local evidence.
This check is separate from full-oracle coverage: a correct no-op score of zero
does not count as an oracle success.

### Runtime provenance

Sources are MiniHack `3ecb6da4eadcac7a4dbc5f8e801ccf636e34d7ec`, Boxoban maps
`78011d8c86ad423bfb2e1005012393b4c3c24409`, and `balrog-nle==0.9.0`.
`scripts/prepare_nle_sources.py` rebuilds the exact source/map archives and
checks their SHA256 values against `fixtures/runtime_sources.json`.

The [validation index](../validation/README.md) separates the saved baseline
validators, source provenance and unapproved proposal. Original-agent/HTTP
bridge checks use a scripted fake client and do not count as model experiments.

All scores retain the original BALROG progression semantics. Native environment
checks, adapter replay checks, and fake-client equivalence are not model parity
and do not by themselves establish Ready for Review status.

## Requested maintainer decision

For parity against the current published pin, we propose retaining the original
100-action instance as a documented upstream-budget exception, subject to
maintainer acceptance. Alternatively, should the existing upstream proposal
for a 200-action allowance for the two Boxoban families be adopted
symmetrically on both parity sides? The latter
requires an agreed source change, regenerated manifests and fresh validation;
the separate 40/40 proposal does not make the current baseline 40/40.
