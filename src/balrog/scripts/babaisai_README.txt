Baba Is AI fixture generation and verification

Scope: all 40 task names in pinned BALROG config, in original order, for each
seed 0, 1, 2. The list was frozen before oracle search. There is no seed or
task replacement. All 120 cases have complete native-action oracles.

Source pins:
  BALROG: b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5
  nacloos/baba-is-ai: 40ae1b29dbc67f2ecea06cc161ed5ca51719e5e3

Run in the Baba runtime image, with source paths BALROG_SOURCE=/opt/balrog
and BABA_SOURCE=/opt/baba. No API key or model is used. From adapter root:

  python scripts/babaisai_oracles.py --freeze --output frozen.json
  python scripts/babaisai_oracles.py --solve frozen.json --output solved.json
  python scripts/babaisai_oracles.py --verify src/balrog/fixtures/babaisai_manifest.json --output verification.json

The verifier checks the complete configured case list and requires both fresh
full-wrapper replays to match every frozen observation hash, executed action,
reward, termination flag, and native progression. It fails on any mismatch.
The image uses original BALROG imports, including the unrelated NLE dependency.

Search uses weighted A* over cloned native raw environments and the native
target_plan only to create offline reference solutions. Every transition uses
the original public action enum and step method; the environment is never
edited or teleported. Subject routing provides one intermediate subgoal for
the top-row WALL IS WIN puzzles. Search is a bounded planner, not a proof of
optimality. All accepted trajectories are replayed through original BALROG
make_env/reset/check_action_validity/step/get_stats, twice independently.

Actions are idle/up/right/down/left. Invalid actions use the original idle
fallback. The original budget is 100 actions. Native progression is binary;
the original time-shaped reward is not substituted for benchmark progression.
These tasks have no mission field or separate downloaded level assets.

Windows-only oracle search may set BABA_WINDOWS_IMPORT_SHIM=1 to bypass the
unused NLE package initializer while importing its untouched Gym compatibility
class. This does not change Baba dynamics, but is prohibited on Linux and is
not accepted as final runtime validation. The committed oracle traces were
also verified in Linux without the shim.

Known upstream behavior: breaking the active IS YOU rule resets the puzzle.
The wrapper embeds a defaultdict/function/PIL repr in the observation, including
memory addresses. The service keeps the original prompt text and normalizes
only those two known address locations in replay audit hashes. Oracles never
rely on this reset shortcut. The model may still see the native malformed text.
