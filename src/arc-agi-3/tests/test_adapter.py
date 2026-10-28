import importlib.util
import json
import threading
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest
from arc_runtime_env.server import RuntimeHttpServer, ServerConfig

from arc_agi_3.adapter import GAMES_FILE, RUNTIME_DIR, TEMPLATE_DIR, ArcAgi3Adapter


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verifier = load_module("arc_verifier", TEMPLATE_DIR / "tests/verify.py")
oracle = load_module("arc_oracle", TEMPLATE_DIR / "solution/replay.py")
GAMES = json.loads(GAMES_FILE.read_text())
ORACLES = sorted((GAMES_FILE.parent / "oracles").glob("*.json"))


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    servers = []

    def start(game_id):
        root = tmp_path / game_id
        monkeypatch.setenv("ARC_LOG_DIR", str(root / "logs"))
        server = RuntimeHttpServer(
            ServerConfig(
                game_id=game_id,
                environments_dir=str(RUNTIME_DIR / "games"),
                host="127.0.0.1",
                port=0,
                workspace_root=str(root / "workspaces"),
                workspace_backend="directory",
            )
        )
        thread = threading.Thread(target=server._server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return server, f"http://127.0.0.1:{server._server.server_port}"

    yield start
    for server, thread in servers:
        server.shutdown()
        thread.join(timeout=5)


def get(url):
    with urlopen(url, timeout=20) as response:
        return json.load(response)


def test_generates_all_pinned_tasks(tmp_path):
    ArcAgi3Adapter(tmp_path).run()
    assert len(list(tmp_path.iterdir())) == 25
    for game in GAMES:
        task = tmp_path / game["game_id"]
        for name in ["task.toml", "instruction.md", "solution/solve.sh", "tests/test.sh"]:
            assert (task / name).is_file()
        scoring = json.loads((task / "tests/scoring.json").read_text())
        assert len(scoring["baseline_actions"]) == game["total_levels"]
        assert not (task / "environment/harness-assets/scoring.json").exists()


def test_unknown_game_fails_before_generating(tmp_path):
    with pytest.raises(ValueError, match="Unknown game IDs"):
        ArcAgi3Adapter(tmp_path / "output", task_ids=["typo"]).run()
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("game", GAMES, ids=lambda g: g["game_id"])
def test_runtime_api_and_verifier(game, runtime, tmp_path):
    server, url = runtime(game["game_id"])
    root = tmp_path / "tasks"
    ArcAgi3Adapter(root, task_ids=[game["game_id"]]).run()
    scoring = root / game["game_id"] / "tests/scoring.json"
    assert verifier.verify(url, scoring, tmp_path / "before")["is_win"] == 0
    action = next(a for a in server.runtime._available_actions() if a != "reset")
    payload = {"action": action}
    if action == "click":
        payload.update(x=0, y=0)
    req = Request(
        url + "/action",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req) as response:
        assert json.load(response)["ok"]
    for route in ["health", "observations", "observation", "progress", "action_log"]:
        assert "baseline_actions" not in json.dumps(get(url + "/" + route))
    private_log = server.runtime.action_log()
    assert private_log and "baseline_actions" in private_log[-1]
    result = verifier.verify(url, scoring, tmp_path / "after")
    expected = verifier.reward(
        private_log[-1], private_log[-1]["baseline_actions"], game["total_levels"]
    )
    assert result == expected


@pytest.mark.parametrize("trajectory", ORACLES, ids=lambda p: p.stem)
def test_oracle_replay(trajectory, runtime):
    _, url = runtime(trajectory.stem)
    assert oracle.replay(trajectory, url)["state"] == "win"


@pytest.mark.parametrize(
    "actions,baselines,total,state,expected",
    [
        ([10, 20], [10, 20], 2, "win", 1.0),
        ([5, 10], [10, 20], 2, "win", 1.0),
        ([20, 40], [10, 20], 2, "win", 0.25),
        ([10], [10, 20], 2, "not_finished", 0.3333),
        ([], [10, 20], 2, "game_over", 0.0),
        ([0], [10], 1, "win", 1.0),
        ([1, 1], [1], 1, "win", 1.0),
    ],
)
def test_reward_edge_cases(actions, baselines, total, state, expected):
    result = verifier.reward(
        {"actions_per_level": actions, "levels_completed": len(actions), "state": state},
        baselines,
        total,
    )
    assert result["efficiency"] == expected
    assert result["is_win"] == int(state == "win")


def test_transport_error_does_not_leave_a_zero_score(tmp_path):
    scoring = tmp_path / "scoring.json"
    scoring.write_text('{"game_id":"test","baseline_actions":[1]}')
    output = tmp_path / "output"
    output.mkdir()
    (output / "reward.json").write_text('{"is_win":1}')
    with pytest.raises(URLError):
        verifier.verify("http://127.0.0.1:1", scoring, output)
    assert not (output / "reward.json").exists()
    assert json.loads((output / "metrics.json").read_text())["state"] == "error"


def test_missing_oracle_is_not_a_pass(tmp_path):
    with pytest.raises(FileNotFoundError, match="No validated oracle"):
        oracle.replay(tmp_path / "missing.json", "http://127.0.0.1:1")
