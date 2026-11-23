Offline runtime and parity tests
================================

These tests exercise the production task-template game server/client/verifier,
production parity_runner.py, and production Harbor BaseAgent bridge. All model
responses are fake. They never call a paid API, and do not require real API keys.
Loopback TCP is required for the game tests and Windows asyncio.

Use separate interpreters/processes for the two groups. The adapter and upstream
Python packages are both named balrog. Tests load adapter files by explicit file
path and reserve the balrog import name for upstream. Do not collect these tests
in a process that has already imported the adapter package as balrog.

Python 3.10 runtime environment:
- Set BALROG_SOURCE to a clone of balrog-ai/BALROG at
  b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5.
- Install the same locked dependencies as task-template/environment/Dockerfile.game,
  including requirements-agent.lock and the Minigrid fork at
  cf73dd148e51276bd675a37e3bfb0bf2b42329b2. No model server is needed.
- Set HARBOR_PYTHON to the absolute Python 3.12 executable with Harbor 0.26.0;
  test_parity.py invokes it only to validate actual ATIF trajectory artifacts.
  Without HARBOR_PYTHON, that one test explicitly skips.

From this adapter project directory:
  python3.10 tests/runtime/test_runtime.py
  python3.10 tests/runtime/test_parity.py
  python3.10 tests/runtime/test_native_batch.py

Python 3.12 Harbor environment:
  python3.12 tests/runtime/test_bridge.py
This group needs Harbor 0.26.0 but does not need BALROG_SOURCE or BabyAI libraries.
It instantiates the actual BaseAgent with a fake environment; no Docker starts.

PowerShell example, replacing paths with local interpreter/clone locations:
  $env:BALROG_SOURCE = 'C:\path\to\BALROG'
  $env:HARBOR_PYTHON = 'C:\path\to\harbor-venv\Scripts\python.exe'
  & 'C:\path\to\babyai-venv\Scripts\python.exe' tests/runtime/test_runtime.py
  & 'C:\path\to\babyai-venv\Scripts\python.exe' tests/runtime/test_parity.py
  & 'C:\path\to\babyai-venv\Scripts\python.exe' tests/runtime/test_native_batch.py
  & $env:HARBOR_PYTHON tests/runtime/test_bridge.py

Coverage:
- Frozen mission/initial-observation/budget validation and replay integrity.
- Oracle score 1, valid unfinished/failed score 0, infrastructure errors without
  a reward file, token protection, stale actions and long invalid model output.
  Runtime verification now collects through environment/export_result.py and
  grades that trusted file offline with the frozen task_config.json. The grader
  receives neither the game token nor a live server URL.
- Actual upstream Evaluator.run_episode versus HTTP transport: every prompt,
  converted OpenAI request, parsed action and observation hash must agree for a
  successful oracle trajectory and a 64-step long-invalid-output trajectory.
- API failures and model-call limits fail closed; raw completions and token usage
  survive in evidence. Exact ATIF is checked against Harbor's Pydantic schema.
- Bridge credentials appear only in child environment, task shell instructions
  never enter model prompts, and runner failure raises a Harbor agent exception.
- Native batch rejects unsafe/duplicate/empty manifests and template settings
  before a child launches, refuses old artifacts, and rejects failed or missing
  child reports without continuing to the next episode. It also checks the
  settings/runner snapshots and their hashes remain stable across children.

Temporary artifacts are created in this test directory and removed by the tests.
The tests use the committed fixtures/manifest.json; no research directory is read.

Host-only collection/grading contracts (Python 3.12, no game dependencies):
  python3.12 -m unittest discover -s tests -p test_separate_verifier.py
These tests use a localhost fake HTTP service for collection and subprocesses
for offline grading. They check authenticated collection, missing/corrupt
artifacts, task identity, stale-output removal, and preserved fractional scores.
They do not establish a real separate-container Harbor pass or cryptographic
freshness of a same-task historical result; artifact trust comes from Harbor's
game-service-only collection. Allow loopback sockets in the test environment.

Additional six-environment checks:
  test_suite_verification.py validates fractional scores and the explicit Crafter
  native-state scoring policy. test_crafter_failure_policy.py ensures simulator
  errors, invalid scores and failures in other games cannot use that exception.
  test_minihack_initial_score.py requires the Linux NLE/MiniHack runtime; it
  verifies the original BaseProgress initial class attribute at zero actions.

check_suite_agents.py --environment ENV --output FILE runs a strict scripted
native-agent versus HTTP-agent comparison in a pinned game image. Set
BALROG_SOURCE=/opt/balrog, use a dummy OPENAI_API_KEY, and disable Docker network
access with --network none (loopback still serves the local game). Results are
OFFLINE_TEST_ONLY. Crafter is excluded from this exact long-trajectory check
because of documented upstream object-identity ordering; its authoritative
scoring behavior has separate regression and real Harbor diagnostic coverage.
