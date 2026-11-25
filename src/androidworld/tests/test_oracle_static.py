"""Static regression tests for AndroidWorld boot, Dockerfile, daemon/client, and oracles.

Runs completely offline without an Android emulator or Docker daemon.
"""

from __future__ import annotations

import base64
import contextlib
import dataclasses
import importlib.util
import io
import json
import os
import pickle
import re
import sqlite3
import subprocess
import sys
import tempfile
import types
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TESTS_DIR.parent
ADAPTER_SRC = PROJECT_DIR / "src"
REPO_ROOT = PROJECT_DIR.parents[2]
AW_DIR = ADAPTER_SRC / "androidworld" / "task-template" / "environment" / "aw"
DOCKERFILE_PATH = ADAPTER_SRC / "androidworld" / "task-template" / "environment" / "Dockerfile"
BOOT_SH = AW_DIR / "boot.sh"
ORACLES_PY = AW_DIR / "oracles.py"
DAEMON_PY = AW_DIR / "daemon.py"
CLIENT_PY = AW_DIR / "client.py"
TASKS_JSON = ADAPTER_SRC / "androidworld" / "tasks.json"
REF_AW_ROOT = REPO_ROOT / "ref" / "android_world"

for p in (str(ADAPTER_SRC), str(AW_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import oracles  # noqa: E402
from androidworld.adapter import ANSWER_FAMILY, ORACLE_KINDS, oracle_kind  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers for loading upstream ref/android_world checkers offline
# ---------------------------------------------------------------------------


def _install_upstream_stubs(monkeypatch: pytest.MonkeyPatch) -> dict[str, types.ModuleType]:
    """Install minimal stubs so ref/android_world task modules import without android_env."""
    stubs: dict[str, types.ModuleType] = {}

    def _pkg(name: str, real_path: Path | None = None) -> types.ModuleType:
        mod = types.ModuleType(name)
        mod.__path__ = [str(real_path)] if real_path else []  # type: ignore[attr-defined]
        stubs[name] = mod
        return mod

    # absl
    absl_mod = _pkg("absl")
    absl_logging = types.ModuleType("absl.logging")
    absl_logging.info = lambda *a, **k: None  # type: ignore[attr-defined]
    absl_logging.warning = lambda *a, **k: None  # type: ignore[attr-defined]
    absl_logging.warn = lambda *a, **k: None  # type: ignore[attr-defined]
    absl_logging.error = lambda *a, **k: None  # type: ignore[attr-defined]
    absl_logging.debug = lambda *a, **k: None  # type: ignore[attr-defined]
    stubs["absl.logging"] = absl_logging
    absl_mod.logging = absl_logging  # type: ignore[attr-defined]

    # immutabledict
    imm_mod = types.ModuleType("immutabledict")
    imm_mod.immutabledict = dict  # type: ignore[attr-defined]
    stubs["immutabledict"] = imm_mod

    # numpy / cv2 / pydub / requests / dm_env (only needed for imports in ref modules)
    for mod_name in ("numpy", "cv2", "pydub", "requests"):
        if mod_name not in sys.modules:
            m = types.ModuleType(mod_name)
            if mod_name == "numpy":
                m.ndarray = Any  # type: ignore[attr-defined]
                m.isnan = lambda x: False  # type: ignore[attr-defined]
            stubs[mod_name] = m
    dm_env_mod = types.ModuleType("dm_env")
    dm_env_mod.TimeStep = Any  # type: ignore[attr-defined]
    stubs["dm_env"] = dm_env_mod

    # android_env
    android_env_pkg = _pkg("android_env")
    env_iface = types.ModuleType("android_env.env_interface")
    env_iface.AndroidEnvInterface = Any  # type: ignore[attr-defined]
    stubs["android_env.env_interface"] = env_iface
    loader_mod = types.ModuleType("android_env.loader")
    stubs["android_env.loader"] = loader_mod
    android_env_pkg.loader = loader_mod  # type: ignore[attr-defined]

    comp_pkg = _pkg("android_env.components")
    comp_err = types.ModuleType("android_env.components.errors")
    comp_err.AdbControllerError = RuntimeError  # type: ignore[attr-defined]
    stubs["android_env.components.errors"] = comp_err
    action_type_mod = types.ModuleType("android_env.components.action_type")
    action_type_mod.ActionType = SimpleNamespace(LIFT=1)  # type: ignore[attr-defined]
    stubs["android_env.components.action_type"] = action_type_mod
    config_mod = types.ModuleType("android_env.components.config_classes")
    config_mod.AndroidEnvConfig = Any  # type: ignore[attr-defined]
    stubs["android_env.components.config_classes"] = config_mod
    comp_pkg.action_type = action_type_mod  # type: ignore[attr-defined]
    comp_pkg.config_classes = config_mod  # type: ignore[attr-defined]
    comp_pkg.errors = comp_err  # type: ignore[attr-defined]

    wrappers_pkg = _pkg("android_env.wrappers")
    a11y_wrap = types.ModuleType("android_env.wrappers.a11y_grpc_wrapper")
    a11y_wrap.A11yGrpcWrapper = Any  # type: ignore[attr-defined]
    base_wrap = types.ModuleType("android_env.wrappers.base_wrapper")
    base_wrap.BaseWrapper = object  # type: ignore[attr-defined]
    stubs["android_env.wrappers.a11y_grpc_wrapper"] = a11y_wrap
    stubs["android_env.wrappers.base_wrapper"] = base_wrap
    wrappers_pkg.a11y_grpc_wrapper = a11y_wrap  # type: ignore[attr-defined]
    wrappers_pkg.base_wrapper = base_wrap  # type: ignore[attr-defined]

    _pkg("android_env.proto")
    _pkg("android_env.proto.a11y")
    a11y_pb2 = types.ModuleType("android_env.proto.a11y.android_accessibility_forest_pb2")
    a11y_pb2.AndroidAccessibilityForest = Any  # type: ignore[attr-defined]
    stubs["android_env.proto.a11y.android_accessibility_forest_pb2"] = a11y_pb2
    adb_pb2 = types.ModuleType("android_env.proto.adb_pb2")

    class _Status:
        OK = 0
        ADB_ERROR = 1

    class _AdbResponse:
        Status = _Status

        def __init__(self, status=0, output=b""):
            self.status = status
            self.generic = SimpleNamespace(output=output)
            self.error_message = ""
            self.get_current_activity = SimpleNamespace(full_activity="")

    adb_pb2.AdbResponse = _AdbResponse  # type: ignore[attr-defined]

    class _SettingsRequest:
        Namespace = Any
        Put = staticmethod(lambda **kw: SimpleNamespace(**kw))

    class _AdbRequest:
        SettingsRequest = _SettingsRequest
        GenericRequest = staticmethod(lambda **kw: SimpleNamespace(**kw))

        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    adb_pb2.AdbRequest = _AdbRequest  # type: ignore[attr-defined]
    stubs["android_env.proto.adb_pb2"] = adb_pb2

    # android_world packages pointing at ref/android_world
    aw_pkg_root = REF_AW_ROOT / "android_world"
    _pkg("android_world", aw_pkg_root)
    _pkg("android_world.env", aw_pkg_root / "env")
    _pkg("android_world.env.setup_device", aw_pkg_root / "env" / "setup_device")
    _pkg("android_world.utils", aw_pkg_root / "utils")
    _pkg("android_world.task_evals", aw_pkg_root / "task_evals")
    _pkg("android_world.task_evals.single", aw_pkg_root / "task_evals" / "single")
    _pkg("android_world.task_evals.composite", aw_pkg_root / "task_evals" / "composite")
    _pkg("android_world.task_evals.common_validators", aw_pkg_root / "task_evals" / "common_validators")
    _pkg("android_world.task_evals.utils", aw_pkg_root / "task_evals" / "utils")
    _pkg("android_world.task_evals.information_retrieval", aw_pkg_root / "task_evals" / "information_retrieval")
    stubs["android_world.task_evals.information_retrieval.joplin_app_utils"] = types.ModuleType(
        "android_world.task_evals.information_retrieval.joplin_app_utils"
    )

    for k, v in stubs.items():
        monkeypatch.setitem(sys.modules, k, v)
    return stubs


def _load_ref_module(mod_name: str, rel_path: str, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(mod_name, REF_AW_ROOT / rel_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, mod_name, mod)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. Registry & Oracle Completeness
# ---------------------------------------------------------------------------


def test_all_116_tasks_have_oracle_kinds_and_handlers() -> None:
    tasks = json.loads(TASKS_JSON.read_text(encoding="utf-8"))
    assert len(tasks) == 116
    for t in tasks:
        kind = oracle_kind(t)
        assert kind != "none", f"Missing oracle for {t['name']}"
        assert kind in oracles.KINDS, f"Missing handler in oracles.KINDS for {t['name']} ({kind})"
        if t["family"] == ANSWER_FAMILY:
            assert kind == "answer"
        else:
            assert ORACLE_KINDS[t["name"]] == kind


# ---------------------------------------------------------------------------
# 2. Boot, Dockerfile, daemon.py, client.py checks
# ---------------------------------------------------------------------------


def test_boot_sh_syntax_and_hardening_guards() -> None:
    text = BOOT_SH.read_text(encoding="utf-8")
    assert os.access(BOOT_SH, os.X_OK), "boot.sh must be executable"
    res = subprocess.run(["bash", "-n", str(BOOT_SH)], capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stderr

    # Must use bracket trick in pgrep, wait-for-device after adb root, and check boot_completed
    assert 'pgrep -f "[a]w/daemon.py"' in text
    assert "adb root" in text
    assert "adb wait-for-device" in text
    assert text.index("adb root") < text.index("adb wait-for-device")
    assert text.index("adb wait-for-device") < text.index("settings put global")
    assert 'if [ "$booted" != "1" ]' in text
    assert "ANDROID_I_WANT_MY_TCG=yes" in text
    assert "-no-metrics" in text
    assert "package_verifier_enable 0" in text
    assert "verifier_verify_adb_installs 0" in text
    assert "GRPC_VERBOSITY=ERROR" in text


def test_boot_sh_executes_wait_for_device_after_adb_root_with_mock_binaries(tmp_path: Path) -> None:
    # Create a sandboxed copy of boot.sh pointing logs/pid/lock into tmp_path
    logs_dir = tmp_path / "logs_aw"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    call_log = tmp_path / "adb_calls.log"
    daemon_py = tmp_path / "daemon.py"
    daemon_py.write_text("import time; time.sleep(0.05)\n", encoding="utf-8")

    # Fake adb, emulator, pgrep
    adb_script = bin_dir / "adb"
    adb_script.write_text(
        f"""#!/bin/bash
echo "$*" >> "{call_log}"
case "$1" in
  devices) echo "List of devices attached" ;;
  shell)
    if [ "$2" = "getprop" ] && [ "$3" = "sys.boot_completed" ]; then
      echo "1"
    fi
    exit 0
    ;;
  *) exit 0 ;;
esac
""",
        encoding="utf-8",
    )
    emu_script = bin_dir / "emulator"
    emu_script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    pgrep_script = bin_dir / "pgrep"
    pgrep_script.write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")
    flock_script = bin_dir / "flock"
    flock_script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    for p in (adb_script, emu_script, pgrep_script, flock_script):
        p.chmod(0o755)

    patched_boot = tmp_path / "boot_test.sh"
    body = BOOT_SH.read_text(encoding="utf-8")
    body = body.replace("/logs/aw", str(logs_dir))
    body = body.replace("/tmp/aw_boot.lock", str(tmp_path / "aw_boot.lock"))
    body = body.replace("/opt/aw/daemon.py", str(daemon_py))
    patched_boot.write_text(body, encoding="utf-8")
    patched_boot.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["ANDROID_HOME"] = str(tmp_path / "android_sdk")
    if not Path("/dev/kvm").exists():
        res_fail = subprocess.run(["bash", str(patched_boot)], env=env, capture_output=True, text=True, check=False)
        assert res_fail.returncode == 1
        assert "ANDROIDWORLD_ALLOW_TCG=1" in res_fail.stderr
        assert "ANDROIDWORLD_ALLOW_TCG=1" in (logs_dir / "boot.log").read_text(encoding="utf-8")

    env["ANDROIDWORLD_ALLOW_TCG"] = "1"
    res = subprocess.run(["bash", str(patched_boot)], env=env, capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stderr
    if not Path("/dev/kvm").exists():
        assert "accel='-accel off -qemu -accel tcg,thread=multi'" in (logs_dir / "boot.log").read_text(encoding="utf-8")

    calls = call_log.read_text(encoding="utf-8").splitlines()
    root_idx = next(i for i, c in enumerate(calls) if c == "root")
    wait_idx = next(i for i, c in enumerate(calls) if c == "wait-for-device")
    settings_idx = next(i for i, c in enumerate(calls) if "settings put global" in c)
    assert root_idx < wait_idx < settings_idx
    assert (logs_dir / "boot.log").exists()


def test_docker_compose_yaml_passes_kvm_and_healthcheck() -> None:
    compose_path = DOCKERFILE_PATH.parent / "docker-compose.yaml"
    assert compose_path.is_file()
    text = compose_path.read_text(encoding="utf-8")
    assert "/dev/kvm" in text
    assert "privileged: true" not in text
    assert "ANDROIDWORLD_ALLOW_TCG" in text
    assert "http://127.0.0.1:5000/ready" in text


def test_dockerfile_defines_android_home_and_sdk_root() -> None:
    text = DOCKERFILE_PATH.read_text(encoding="utf-8")
    assert "ENV ANDROID_HOME=/opt/android" in text
    assert "ENV ANDROID_SDK_ROOT=/opt/android" in text
    assert "${ANDROID_HOME}/platform-tools" in text
    assert "${ANDROID_HOME}/emulator" in text
    assert "Pillow==" in text
    assert "websocket-client==" in text
    assert "hw.keyboard = yes" in text
    assert "GRPC_VERBOSITY=ERROR" in text
    assert "GRPC_ENABLE_FORK_SUPPORT=0" in text


def test_client_py_handles_non_json_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("aw_client_mod", CLIENT_PY)
    assert spec and spec.loader
    client_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client_mod)

    def fake_urlopen(req, timeout=900):
        raise urllib.error.HTTPError(
            req.full_url, 502, "Bad Gateway", {}, io.BytesIO(b"upstream text error")
        )

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", fake_urlopen)
    code, body = client_mod.call("/score", "POST")
    assert code == 502
    assert body == {"error": "upstream text error"}


def test_daemon_py_uses_android_home_fallback_and_guarded_sys_path() -> None:
    text = DAEMON_PY.read_text(encoding="utf-8")
    assert "ANDROID_HOME" in text
    assert "ANDROID_SDK_ROOT" in text
    assert 'if "/opt/aw" not in sys.path:' in text


# ---------------------------------------------------------------------------
# 3. Pure helpers & SQLite / GPX / Content query / Maze tests
# ---------------------------------------------------------------------------


def test_sql_null_helpers_and_parse_content_rows() -> None:
    assert oracles._sql_int("NULL") == 0
    assert oracles._sql_int(None) == 0
    assert oracles._sql_int("") == 0
    assert oracles._sql_int("42") == 42
    assert oracles._sql_str("NULL") == ""
    assert oracles._sql_str(None) == ""
    assert oracles._sql_str("Rock") == "Rock"

    raw = (
        "Row: 0 _id=12, title=Dreamer's Awake, duration=200000, "
        "_data=/sdcard/Music/Dreamer's Awake.mp3, album_id=3, album=NULL, "
        "artist_id=4, artist=Liam, year=NULL\n"
    )
    keys = ["_id", "title", "duration", "_data", "album_id", "album", "artist_id", "artist", "year"]
    rows = oracles.parse_content_rows(raw, keys)
    assert len(rows) == 1
    vals = oracles._song_values(rows[0])
    assert vals["id"] == 12
    assert vals["title"] == "Dreamer's Awake"
    assert vals["duration"] == 200000
    assert vals["album_name"] == ""
    assert vals["year"] == 0


def test_insert_row_and_gpx_helpers() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE Media (id_media INTEGER PRIMARY KEY AUTOINCREMENT, "
        "filename TEXT NOT NULL, title TEXT NOT NULL, type INTEGER NOT NULL, "
        "rating REAL NOT NULL, mrl TEXT NOT NULL UNIQUE)"
    )
    mid = oracles.insert_row(
        conn,
        "Media",
        {"filename": "a.mp4", "title": "a.mp4", "type": 1, "mrl": "file:///a.mp4", "extra_col": "ignored"},
    )
    assert mid == 1
    assert conn.execute("SELECT filename, rating, mrl FROM Media").fetchall() == [
        ("a.mp4", 0.0, "file:///a.mp4")
    ]
    conn.close()

    # Missing file output from cat should still produce valid GPX XML
    xml_out = oracles.add_gpx_waypoint(
        "cat: /data/media/0/favorites.gpx: No such file or directory",
        47.1303814,
        9.5930117,
        "47.1303814, 9.5930117",
    )
    root = ET.fromstring(xml_out)
    ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
    wpts = root.findall("gpx:wpt", ns)
    assert len(wpts) == 1
    assert wpts[0].attrib["lat"] == "47.1303814"


def test_solve_maze_on_upstream_browser_maze_seeded_layout() -> None:
    # Reproduce BrowserMaze SeededRNG + generateMaze from ref/android_world/task_evals/single/browser.py
    tasks = json.loads(TASKS_JSON.read_text(encoding="utf-8"))
    maze_entry = next(t for t in tasks if t["name"] == "BrowserMaze")
    seed = pickle.loads(base64.b64decode(maze_entry["params_pickle_b64"]))["browser_task_seed"]

    # JS SeededRNG LCG
    state = seed
    def js_rand() -> float:
        nonlocal state
        state = (1664525 * state + 1013904223) % (2**32)
        return state / (2**32)

    maze_size = 4
    layout = [["#" for _ in range(maze_size)] for _ in range(maze_size)]
    stack = [(0, 0)]
    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    while stack:
        r, c = stack.pop()
        layout[r][c] = " "
        if r == maze_size - 1 and c == maze_size - 1:
            break
        for i in range(len(dirs) - 1, 0, -1):
            j = int(js_rand() * (i + 1))
            dirs[i], dirs[j] = dirs[j], dirs[i]
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < maze_size and 0 <= nc < maze_size and layout[nr][nc] == "#":
                stack.append((nr, nc))
    layout[0][0] = " "
    layout[maze_size - 1][maze_size - 1] = "$"

    moves = oracles.solve_maze(layout)
    assert moves
    r, c = 0, 0
    deltas = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
    for mv in moves:
        dr, dc = deltas[mv]
        r, c = r + dr, c + dc
        assert layout[r][c] != "#"
    assert (r, c) == (3, 3)


# ---------------------------------------------------------------------------
# 4. Retro Music, VLC, OsmAnd oracle verification against upstream checkers
# ---------------------------------------------------------------------------


def test_retro_music_oracles_with_null_mediastore_and_missing_playback_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_upstream_stubs(monkeypatch)
    monkeypatch.setattr(oracles.time, "sleep", lambda _s: None)

    adb_mod = _load_ref_module("android_world.env.adb_utils", "android_world/env/adb_utils.py", monkeypatch)
    _load_ref_module("android_world.env.device_constants", "android_world/env/device_constants.py", monkeypatch)
    _load_ref_module("android_world.env.interface", "android_world/env/interface.py", monkeypatch)
    _load_ref_module("android_world.utils.fuzzy_match_lib", "android_world/utils/fuzzy_match_lib.py", monkeypatch)
    _load_ref_module("android_world.utils.file_utils", "android_world/utils/file_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.task_eval", "android_world/task_evals/task_eval.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.sqlite_schema_utils", "android_world/task_evals/utils/sqlite_schema_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.sqlite_utils", "android_world/task_evals/utils/sqlite_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.common_validators.sqlite_validators", "android_world/task_evals/common_validators/sqlite_validators.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.user_data_generation", "android_world/task_evals/utils/user_data_generation.py", monkeypatch)
    rm = _load_ref_module("android_world.task_evals.single.retro_music", "android_world/task_evals/single/retro_music.py", monkeypatch)

    playlist_db = tmp_path / "playlist.db"
    playback_db = tmp_path / "music_playback_state.db"
    conn = sqlite3.connect(playlist_db)
    conn.execute("CREATE TABLE PlaylistEntity (playlist_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, playlist_name TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE SongEntity (song_key INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, "
        "playlist_creator_id INTEGER NOT NULL, id INTEGER NOT NULL, title TEXT NOT NULL, "
        "track_number INTEGER NOT NULL, year INTEGER NOT NULL, duration INTEGER NOT NULL, "
        "data TEXT NOT NULL, date_modified INTEGER NOT NULL, album_id INTEGER NOT NULL, "
        "album_name TEXT NOT NULL, artist_id INTEGER NOT NULL, artist_name TEXT NOT NULL, "
        "composer TEXT, album_artist TEXT)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(rm, "_PLAYLIST_DB_PATH", str(playlist_db))
    monkeypatch.setattr(rm, "_PLAYBACK_DB_PATH", str(playback_db))
    monkeypatch.setattr(adb_mod, "close_app", lambda *a, **k: None)

    class _MockRetroEnv:
        def __init__(self):
            self.files: dict[str, bytes] = {}
            self.controller = self

        def execute_adb_call(self, req):
            args = list(getattr(getattr(req, "generic", None), "args", []))
            if args and args[0] == "shell":
                cmd = " ".join(args[1:])
                if "content query" in cmd:
                    m = re.search(r"title='(.*)'\"", cmd)
                    title = m.group(1).replace("''", "'") if m else ""
                    out = (
                        f"Row: 0 _id=7, title={title}, duration=190000, "
                        f"_data=/sdcard/Music/{title}.mp3, album_id=NULL, album=NULL, "
                        f"artist_id=2, artist=Ava, year=NULL\n"
                    ).encode()
                    return SimpleNamespace(status=0, generic=SimpleNamespace(output=out))
                if cmd.startswith("test -f "):
                    target = str(playback_db)
                    out = b"OK\n" if Path(target).exists() else b"MISSING\n"
                    return SimpleNamespace(status=0, generic=SimpleNamespace(output=out))
            return SimpleNamespace(status=0, generic=SimpleNamespace(output=b""))

        @contextlib.contextmanager
        def pull_file(self, remote, timeout_sec=None):
            d = tempfile.mkdtemp()
            Path(d, os.path.basename(remote)).write_bytes(Path(remote).read_bytes())
            try:
                yield d
            finally:
                import shutil
                shutil.rmtree(d, ignore_errors=True)

        def push_file(self, local, remote, timeout_sec=None):
            Path(remote).write_bytes(Path(local).read_bytes())

    env = _MockRetroEnv()
    # Copy bytes helper for missing playback DB creation
    monkeypatch.setattr(
        oracles.Dev,
        "write_bytes",
        lambda self, remote, data: Path(remote).write_bytes(data),
    )

    # 1. RetroCreatePlaylist with apostrophe + NULL fields
    task_pl = rm.RetroCreatePlaylist({
        "playlist_name": "Hip Hop Bangers 270",
        "files": ["Golden Days.mp3", "Dreamer's Awake.mp3"],
        "noise_files": [],
    })
    oracles.retro_playlist(env, task_pl, {"name": "RetroCreatePlaylist"})
    assert task_pl.is_successful(env) == 1.0

    # 2. RetroPlayingQueue when playback DB doesn't exist yet on device
    assert not playback_db.exists()
    task_q = rm.RetroPlayingQueue({
        "playlist_name": "Indie",
        "files": ["Through the Storm.mp3", "Hidden Paths.mp3"],
        "noise_files": [],
    })
    oracles.retro_queue(env, task_q, {"name": "RetroPlayingQueue"})
    assert playback_db.exists()
    assert task_q.is_successful(env) == 1.0


def test_vlc_oracle_with_unique_mrl_constraint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_upstream_stubs(monkeypatch)
    monkeypatch.setattr(oracles.time, "sleep", lambda _s: None)

    adb_mod = _load_ref_module("android_world.env.adb_utils", "android_world/env/adb_utils.py", monkeypatch)
    _load_ref_module("android_world.env.device_constants", "android_world/env/device_constants.py", monkeypatch)
    _load_ref_module("android_world.env.interface", "android_world/env/interface.py", monkeypatch)
    _load_ref_module("android_world.utils.fuzzy_match_lib", "android_world/utils/fuzzy_match_lib.py", monkeypatch)
    _load_ref_module("android_world.utils.file_utils", "android_world/utils/file_utils.py", monkeypatch)
    _load_ref_module("android_world.env.tools", "android_world/env/tools.py", monkeypatch)
    _load_ref_module("android_world.task_evals.information_retrieval", "android_world/task_evals/information_retrieval/__init__.py", monkeypatch)
    joplin_stub = types.ModuleType("android_world.task_evals.information_retrieval.joplin_app_utils")
    monkeypatch.setitem(sys.modules, "android_world.task_evals.information_retrieval.joplin_app_utils", joplin_stub)
    _load_ref_module("android_world.env.setup_device.apps", "android_world/env/setup_device/apps.py", monkeypatch)
    _load_ref_module("android_world.task_evals.task_eval", "android_world/task_evals/task_eval.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.sqlite_schema_utils", "android_world/task_evals/utils/sqlite_schema_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.sqlite_utils", "android_world/task_evals/utils/sqlite_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.common_validators.sqlite_validators", "android_world/task_evals/common_validators/sqlite_validators.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.user_data_generation", "android_world/task_evals/utils/user_data_generation.py", monkeypatch)
    vlc_mod = _load_ref_module("android_world.task_evals.single.vlc", "android_world/task_evals/single/vlc.py", monkeypatch)

    db_path = tmp_path / "vlc_media.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Playlist (id_playlist INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, name TEXT NOT NULL, file_count INTEGER NOT NULL DEFAULT 0, creation_date INTEGER NOT NULL);
        CREATE TABLE Media (id_media INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, type INTEGER NOT NULL, title TEXT NOT NULL, filename TEXT NOT NULL, mrl TEXT NOT NULL UNIQUE);
        CREATE TABLE PlaylistMediaRelation (media_id INTEGER NOT NULL, mrl TEXT NOT NULL, playlist_id INTEGER NOT NULL, position INTEGER NOT NULL);
        """
    )
    conn.close()

    monkeypatch.setattr(vlc_mod, "_DB_PATH", str(db_path))
    monkeypatch.setattr(adb_mod, "close_app", lambda *a, **k: None)

    class _MockVlcEnv:
        def __init__(self):
            self.controller = self

        def execute_adb_call(self, req):
            return SimpleNamespace(status=0, generic=SimpleNamespace(output=b""))

        @contextlib.contextmanager
        def pull_file(self, remote, timeout_sec=None):
            d = tempfile.mkdtemp()
            Path(d, os.path.basename(remote)).write_bytes(Path(remote).read_bytes())
            try:
                yield d
            finally:
                import shutil
                shutil.rmtree(d, ignore_errors=True)

        def push_file(self, local, remote, timeout_sec=None):
            Path(remote).write_bytes(Path(local).read_bytes())

    env = _MockVlcEnv()
    task = vlc_mod.VlcCreateTwoPlaylists({
        "playlist_name1": "Ultimate Fails Series",
        "files1": ["clip_1.mp4", "clip_2.mp4"],
        "noise_files1": [],
        "playlist_name2": "Adventure Marathon",
        "files2": ["clip_3.mp4", "clip_4.mp4"],
        "noise_files2": [],
    })
    task.initialized = True
    task.task1.initialized = True
    task.task2.initialized = True
    oracles.vlc_playlists(env, task, {"name": "VlcCreateTwoPlaylists"})
    assert task.is_successful(env) == 1.0


def test_osmand_oracles_with_pinned_tasks_json_params(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_upstream_stubs(monkeypatch)
    _load_ref_module("android_world.env.adb_utils", "android_world/env/adb_utils.py", monkeypatch)
    _load_ref_module("android_world.env.device_constants", "android_world/env/device_constants.py", monkeypatch)
    _load_ref_module("android_world.env.interface", "android_world/env/interface.py", monkeypatch)
    _load_ref_module("android_world.utils.fuzzy_match_lib", "android_world/utils/fuzzy_match_lib.py", monkeypatch)
    _load_ref_module("android_world.utils.file_utils", "android_world/utils/file_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.task_eval", "android_world/task_evals/task_eval.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.sqlite_schema_utils", "android_world/task_evals/utils/sqlite_schema_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.sqlite_utils", "android_world/task_evals/utils/sqlite_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.common_validators.sqlite_validators", "android_world/task_evals/common_validators/sqlite_validators.py", monkeypatch)
    osmand = _load_ref_module("android_world.task_evals.single.osmand", "android_world/task_evals/single/osmand.py", monkeypatch)

    tasks = json.loads(TASKS_JSON.read_text(encoding="utf-8"))
    fav = next(t for t in tasks if t["name"] == "OsmAndFavorite")
    trk = next(t for t in tasks if t["name"] == "OsmAndTrack")
    fav_params = pickle.loads(base64.b64decode(fav["params_pickle_b64"]))
    trk_params = pickle.loads(base64.b64decode(trk["params_pickle_b64"]))

    written: dict[str, str] = {}
    monkeypatch.setattr(oracles.Dev, "cat", lambda self, path: "cat: No such file")
    monkeypatch.setattr(oracles.Dev, "write_text", lambda self, remote, txt: written.setdefault(remote, txt))

    fake_env = SimpleNamespace(controller=SimpleNamespace())
    oracles.osmand_favorite(fake_env, SimpleNamespace(params=fav_params), {"name": "OsmAndFavorite"})
    fav_xml = ET.fromstring(written[osmand._FAVORITES_PATH])
    assert osmand._favorites_contains(fav_xml, fav_params["location"])

    oracles.osmand_track(fake_env, SimpleNamespace(params=trk_params), {"name": "OsmAndTrack"})
    trk_xml = ET.fromstring(written[f"{osmand._DEVICE_FILES}/tracks/oracle_track.gpx"])
    pts = list(osmand._track_points(trk_xml))
    target = osmand._lookup_target_waypoints(trk_params["waypoints"])
    assert osmand._track_matches(pts, target)


# ---------------------------------------------------------------------------
# 5. Emulator-only UI-script / Intent / System oracle static tests
# ---------------------------------------------------------------------------


def test_contacts_draft_and_sms_send_static(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_upstream_stubs(monkeypatch)
    monkeypatch.setattr(oracles.time, "sleep", lambda _s: None)

    adb_mod = _load_ref_module("android_world.env.adb_utils", "android_world/env/adb_utils.py", monkeypatch)
    _load_ref_module("android_world.utils.contacts_utils", "android_world/utils/contacts_utils.py", monkeypatch)
    _load_ref_module("android_world.env.actuation", "android_world/env/actuation.py", monkeypatch)
    _load_ref_module("android_world.env.android_world_controller", "android_world/env/android_world_controller.py", monkeypatch)
    tools_mod = _load_ref_module("android_world.env.tools", "android_world/env/tools.py", monkeypatch)

    closed: list[str] = []
    launched: list[str] = []
    adb_cmds: list[list[str]] = []
    sent_sms: list[tuple[str, str]] = []

    monkeypatch.setattr(adb_mod, "close_app", lambda name, ctrl: closed.append(name))
    monkeypatch.setattr(adb_mod, "launch_app", lambda name, ctrl: launched.append(name))

    def fake_issue(args, ctrl, timeout_sec=None):
        adb_cmds.append(list(args))
        if len(args) >= 2 and args[0] == "shell" and args[1] == "content":
            return SimpleNamespace(
                status=0,
                generic=SimpleNamespace(
                    output=b"Row: 0 address=+13192815309, body=Actions speak louder than words.\n"
                ),
            )
        return SimpleNamespace(status=0, generic=SimpleNamespace(output=b""))

    monkeypatch.setattr(adb_mod, "issue_generic_request", fake_issue)

    class _FakeTools:
        def __init__(self, ctrl):
            self.ctrl = ctrl

        def send_sms(self, number, message):
            sent_sms.append((number, message))

    monkeypatch.setattr(tools_mod, "AndroidToolController", _FakeTools)

    env = SimpleNamespace(controller=SimpleNamespace())
    oracles.contacts_draft(
        env,
        SimpleNamespace(params={"first": "Grace", "last": "Taylor", "phone": "799-802-1530", "phone_label": "Work"}),
        {"name": "ContactsNewContactDraft"},
    )
    assert closed == ["contacts"]
    assert any("android.intent.action.INSERT" in " ".join(c) and "--ei phone_type 3" in " ".join(c) for c in adb_cmds)

    written: dict[str, str] = {}
    monkeypatch.setattr(oracles.Dev, "write_text", lambda self, remote, text: written.setdefault(remote, text))
    oracles.markor_create_note_and_sms(
        env,
        SimpleNamespace(params={
            "file_name": "fair_ant_XOdi.txt",
            "text": "Actions speak louder than words.",
            "number": "+13192815309",
        }),
        {"name": "MarkorCreateNoteAndSms"},
    )
    assert written[f"{oracles.MARKOR}/fair_ant_XOdi.txt"] == "Actions speak louder than words.\n"
    assert sent_sms == [("+13192815309", "Actions speak louder than words.")]
    assert launched == ["simple sms messenger"]


def test_clock_and_tap_label_visibility_filtering(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_upstream_stubs(monkeypatch)
    monkeypatch.setattr(oracles.time, "sleep", lambda _s: None)
    adb_mod = _load_ref_module("android_world.env.adb_utils", "android_world/env/adb_utils.py", monkeypatch)

    taps: list[tuple[int, int]] = []
    monkeypatch.setattr(adb_mod, "launch_app", lambda *a, **k: None)
    monkeypatch.setattr(adb_mod, "tap_screen", lambda x, y, ctrl: taps.append((x, y)))

    bbox = lambda x1, x2, y1, y2: SimpleNamespace(
        x_min=x1, x_max=x2, y_min=y1, y_max=y2, width=x2 - x1, height=y2 - y1, center=((x1 + x2) / 2, (y1 + y2) / 2)
    )

    elements = [
        SimpleNamespace(text="Timer", content_description=None, is_visible=False, bbox_pixels=bbox(0, 10, 0, 10)),
        SimpleNamespace(text="Timer", content_description=None, is_visible=True, bbox_pixels=bbox(100, 200, 100, 200)),
        SimpleNamespace(text="1", content_description=None, is_visible=True, bbox_pixels=bbox(10, 30, 10, 30)),
        SimpleNamespace(text="6", content_description=None, is_visible=True, bbox_pixels=bbox(30, 50, 10, 30)),
        SimpleNamespace(text="3", content_description=None, is_visible=True, bbox_pixels=bbox(50, 70, 10, 30)),
        SimpleNamespace(text="5", content_description=None, is_visible=True, bbox_pixels=bbox(70, 90, 10, 30)),
    ]
    env = SimpleNamespace(controller=SimpleNamespace(get_ui_elements=lambda: elements))
    oracles.clock_timer_entry(
        env,
        SimpleNamespace(params={"hours": 0, "minutes": 16, "seconds": 35}),
        {"name": "ClockTimerEntry"},
    )
    # First tap must be visible Timer (150, 150), NOT invisible Timer (5, 5), followed by 1, 6, 3, 5
    assert taps == [(150, 150), (20, 20), (40, 20), (60, 20), (80, 20)]


def test_system_open_app_and_verify_toggles(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_upstream_stubs(monkeypatch)
    monkeypatch.setattr(oracles.time, "sleep", lambda _s: None)
    adb_mod = _load_ref_module("android_world.env.adb_utils", "android_world/env/adb_utils.py", monkeypatch)

    state = {"wifi_on": "0", "bluetooth_on": "0", "screen_brightness": "128", "activity": "com.google.android.apps.nexuslauncher/.NexusLauncherActivity"}
    monkeypatch.setattr(adb_mod, "toggle_wifi", lambda ctrl, on_off: state.__setitem__("wifi_on", "1" if on_off == "on" else "0"))
    monkeypatch.setattr(adb_mod, "toggle_bluetooth", lambda ctrl, on_off: state.__setitem__("bluetooth_on", "1" if on_off == "on" else "0"))
    monkeypatch.setattr(adb_mod, "set_brightness", lambda m, ctrl: state.__setitem__("screen_brightness", "255" if m == "max" else "1"))
    monkeypatch.setattr(adb_mod, "launch_app", lambda app, ctrl: state.__setitem__("activity", f"com.example.{app}/.Main"))
    monkeypatch.setattr(adb_mod, "get_current_activity", lambda ctrl: (state["activity"], None))

    def fake_issue(args, ctrl, timeout_sec=None):
        if len(args) >= 4 and args[:3] == ["shell", "settings", "get"]:
            val = state.get(args[4], "")
            return SimpleNamespace(status=0, generic=SimpleNamespace(output=f"{val}\n".encode()))
        return SimpleNamespace(status=0, generic=SimpleNamespace(output=b""))

    monkeypatch.setattr(adb_mod, "issue_generic_request", fake_issue)

    env = SimpleNamespace(controller=SimpleNamespace())
    oracles.system_open_app(env, SimpleNamespace(params={"app_name": "settings"}), {"name": "TurnOnWifiAndOpenApp"})
    assert state["wifi_on"] == "1"
    assert state["activity"] == "com.example.settings/.Main"

    for task_name, params, key, expected in [
        ("SystemWifiTurnOnVerify", {"on_or_off": "on"}, "wifi_on", "1"),
        ("SystemWifiTurnOffVerify", {"on_or_off": "off"}, "wifi_on", "0"),
        ("SystemBluetoothTurnOnVerify", {"on_or_off": "on"}, "bluetooth_on", "1"),
        ("SystemBluetoothTurnOffVerify", {"on_or_off": "off"}, "bluetooth_on", "0"),
        ("SystemBrightnessMaxVerify", {"max_or_min": "max"}, "screen_brightness", "255"),
        ("SystemBrightnessMinVerify", {"max_or_min": "min"}, "screen_brightness", "1"),
    ]:
        oracles.system_toggle(env, SimpleNamespace(params=params), {"name": task_name})
        assert state[key] == expected


def test_browser_oracles_use_ephemeral_port_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oracles.time, "sleep", lambda _s: None)

    seen_urls: list[str] = []
    adb_fwds: list[list[str]] = []
    eval_exprs: list[str] = []

    monkeypatch.setattr(oracles.Dev, "cat", lambda self, path: "<html><body></body></html>")
    monkeypatch.setattr(
        oracles.Dev,
        "sh",
        lambda self, *args: seen_urls.append(args[5]) if len(args) > 5 and args[0] == "am" else "",
    )
    monkeypatch.setattr(oracles.Dev, "tap_label", lambda self, *a, **k: False)
    monkeypatch.setattr(oracles.subprocess, "run", lambda cmd, **kw: adb_fwds.append(list(cmd)))

    class _FakeWS:
        def __init__(self):
            self.closed = False

        def send(self, payload: str) -> None:
            eval_exprs.append(json.loads(payload)["params"]["expression"])

        def recv(self) -> str:
            expr = eval_exprs[-1]
            val = json.dumps([[" ", "#"], [" ", "$"]]) if "mazeLayout" in expr else 1
            return json.dumps({"id": 1, "result": {"result": {"value": val}}})

        def close(self) -> None:
            self.closed = True

    cdp_ports_used: list[int] = []
    fake_ws = _FakeWS()
    monkeypatch.setattr(
        oracles,
        "_cdp_session",
        lambda port=9222, timeout=60: (cdp_ports_used.append(port), fake_ws)[1],
    )

    env = SimpleNamespace(controller=SimpleNamespace())
    oracles.browser_draw(env, SimpleNamespace(params={}), {"name": "BrowserDraw"})
    oracles.browser_multiply(env, SimpleNamespace(params={}), {"name": "BrowserMultiply"})
    oracles.browser_maze(env, SimpleNamespace(params={}), {"name": "BrowserMaze"})

    assert len(seen_urls) == 3
    # Ephemeral port must NOT be hardcoded 8123 unless OS happened to assign it (check valid 10.0.2.2:<port>)
    assert all(re.match(r"^http://10\.0\.2\.2:\d+/task\.html$", u) for u in seen_urls)
    assert len(cdp_ports_used) == 3
    assert all(isinstance(p, int) and p > 0 and p != 9222 for p in cdp_ports_used)
    for p in cdp_ports_used:
        assert ["adb", "forward", "--remove", f"tcp:{p}"] in adb_fwds
    assert any("ctx.fillRect" in e for e in eval_exprs)
    assert any("checkAnswer()" in e for e in eval_exprs)
    assert any("moveCharacter('down')" in e for e in eval_exprs)
    assert fake_ws.closed is True


def test_osmand_favorite_tolerates_missing_favorites_file(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_upstream_stubs(monkeypatch)
    _load_ref_module("android_world.task_evals.task_eval", "android_world/task_evals/task_eval.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.sqlite_schema_utils", "android_world/task_evals/utils/sqlite_schema_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.utils.sqlite_utils", "android_world/task_evals/utils/sqlite_utils.py", monkeypatch)
    _load_ref_module("android_world.task_evals.common_validators.sqlite_validators", "android_world/task_evals/common_validators/sqlite_validators.py", monkeypatch)
    osmand = _load_ref_module("android_world.task_evals.single.osmand", "android_world/task_evals/single/osmand.py", monkeypatch)

    tasks = json.loads(TASKS_JSON.read_text(encoding="utf-8"))
    fav = next(t for t in tasks if t["name"] == "OsmAndFavorite")
    fav_params = pickle.loads(base64.b64decode(fav["params_pickle_b64"]))

    written: dict[str, str] = {}

    def _fail_cat(self, path: str) -> str:
        raise RuntimeError(f"cat: {path}: No such file or directory")

    monkeypatch.setattr(oracles.Dev, "cat", _fail_cat)
    monkeypatch.setattr(oracles.Dev, "write_text", lambda self, remote, txt: written.__setitem__(remote, txt))

    fake_env = SimpleNamespace(controller=SimpleNamespace())
    oracles.osmand_favorite(fake_env, SimpleNamespace(params=fav_params), {"name": "OsmAndFavorite"})
    fav_xml = ET.fromstring(written[osmand._FAVORITES_PATH])
    assert osmand._favorites_contains(fav_xml, fav_params["location"])


def test_send_sms_resend_waits_for_count_increment(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_upstream_stubs(monkeypatch)
    sleeps: list[float] = []
    monkeypatch.setattr(oracles.time, "sleep", lambda s: sleeps.append(s))

    adb_mod = _load_ref_module("android_world.env.adb_utils", "android_world/env/adb_utils.py", monkeypatch)
    _load_ref_module("android_world.utils.contacts_utils", "android_world/utils/contacts_utils.py", monkeypatch)
    _load_ref_module("android_world.env.actuation", "android_world/env/actuation.py", monkeypatch)
    _load_ref_module("android_world.env.android_world_controller", "android_world/env/android_world_controller.py", monkeypatch)
    tools_mod = _load_ref_module("android_world.env.tools", "android_world/env/tools.py", monkeypatch)

    monkeypatch.setattr(adb_mod, "launch_app", lambda *a, **k: None)
    closed: list[str] = []
    monkeypatch.setattr(adb_mod, "close_app", lambda name, ctrl: closed.append(name))

    rows_state = {"sent": 1, "post_polls": 0}

    class _FakeTools:
        def __init__(self, ctrl):
            self.ctrl = ctrl

        def send_sms(self, number, message):
            assert closed == ["simple sms messenger"]
            rows_state["sent_called"] = True

    monkeypatch.setattr(tools_mod, "AndroidToolController", _FakeTools)

    def _fake_query(args, ctrl, timeout_sec=None):
        if len(args) >= 2 and args[:2] == ["shell", "content"]:
            if rows_state.get("sent_called"):
                rows_state["post_polls"] += 1
                if rows_state["post_polls"] >= 2:
                    rows_state["sent"] = 2
            lines = "".join(
                f"Row: {i} address=+17620559636, body=Inconceivable!\n"
                for i in range(rows_state["sent"])
            )
            return SimpleNamespace(status=0, generic=SimpleNamespace(output=lines.encode()))
        return SimpleNamespace(status=0, generic=SimpleNamespace(output=b""))

    monkeypatch.setattr(adb_mod, "issue_generic_request", _fake_query)

    oracles._send_sms(SimpleNamespace(controller=SimpleNamespace()), "+17620559636", "Inconceivable!")
    assert rows_state["post_polls"] == 2
    assert sleeps.count(1.5) == 1
