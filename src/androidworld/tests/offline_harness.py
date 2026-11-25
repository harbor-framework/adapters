"""Offline verification of the oracles against the REAL upstream task classes.

Runs inside a Linux container that has `android_world` installed (e.g. the task image):
  docker run --rm --platform linux/amd64 --entrypoint python3 \
     -v <adapter>/src/androidworld:/adapter aw-test /adapter/tests/offline_harness.py [names...]

A fake "device" executes adb shell commands locally (GNU coreutils standing in for toybox) and
fakes pull/push for SQLite files; app/UI-dependent calls are stubbed. For every covered task:
    task.initialize_task(env); oracles.run(...); assert task.is_successful(env) == 1.0
Tasks needing a real emulator (UI, MediaStore, app DB schemas, Chrome, SMS stack, ...) are
reported as SKIP; they can only be verified on a KVM host.
"""
import base64
import contextlib
import dataclasses
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from unittest import mock

sys.path.insert(0, "/adapter/src/androidworld/task-template/environment/aw")
sys.path.insert(0, "/adapter/src")
from android_env.proto import adb_pb2  # noqa: E402

import oracles  # noqa: E402
from android_world import registry  # noqa: E402
from android_world.env import adb_utils  # noqa: E402
from android_world.task_evals import task_eval  # noqa: E402
from android_world.task_evals.utils import sqlite_schema_utils  # noqa: E402

from androidworld.adapter import oracle_kind  # noqa: E402

TASKS = json.load(open("/adapter/src/androidworld/tasks.json"))


MEDIA = {}
SETTINGS = {}


class FakeController:
    def execute_adb_call(self, req):
        which = req.WhichOneof("command")
        resp = adb_pb2.AdbResponse(status=adb_pb2.AdbResponse.Status.OK)
        if which == "generic":
            args = list(req.generic.args)
            if args and args[0] == "shell":
                cmd = " ".join(args[1:])
                cmd = re.sub(r"^ls (\S+) -ll -au$", r"ls -l --full-time -a \1", cmd)  # toybox -> GNU
                m = re.match(r"svc (wifi|bluetooth) (enable|disable)$", cmd)
                if m:
                    SETTINGS[m.group(1) + "_on"] = "1" if m.group(2) == "enable" else "0"
                    return resp
                m = re.match(r"settings put system screen_brightness (\d+)$", cmd)
                if m:
                    SETTINGS["screen_brightness"] = m.group(1)
                    return resp
                m = re.match(r"settings get (?:global|system) (wifi_on|bluetooth_on|screen_brightness)$", cmd)
                if m:
                    resp.generic.output = (SETTINGS.get(m.group(1), "128" if "bright" in m.group(1) else "0") + "\n").encode()
                    return resp
                m = re.search(r"content query --uri content://media/external/audio/media .*title='(.*)'\"", cmd)
                if m:  # fake MediaStore for songs the task "wrote"
                    resp.generic.output = MEDIA.get(m.group(1).replace("''", "'"), b"No result found.\n")
                    return resp
                p = subprocess.run(["sh", "-c", cmd], capture_output=True)
                resp.generic.output = p.stdout + p.stderr
                if p.returncode != 0:
                    resp.status = adb_pb2.AdbResponse.Status.ADB_ERROR
        elif which == "pull":
            try:
                resp.pull.content = open(req.pull.path, "rb").read()
            except OSError as e:
                resp.status = adb_pb2.AdbResponse.Status.ADB_ERROR
                resp.error_message = str(e)
        elif which == "push":
            os.makedirs(os.path.dirname(req.push.path), exist_ok=True)
            open(req.push.path, "wb").write(req.push.content)
        return resp

    @contextlib.contextmanager
    def pull_file(self, remote, timeout_sec=None):
        d = tempfile.mkdtemp()
        shutil.copy(remote, d)
        yield d
        shutil.rmtree(d, ignore_errors=True)

    def push_file(self, local, remote, timeout_sec=None):
        shutil.copy(local, remote)


class FakeEnv:
    interaction_cache = ""

    def __init__(self):
        self.controller = FakeController()


def make_task(name):
    t = next(x for x in TASKS if x["name"] == name)
    cls = registry.TaskRegistry().get_registry("android_world")[name]
    return cls(pickle.loads(base64.b64decode(t["params_pickle_b64"])))


def py2sql(tp):
    s = str(tp)
    return "INTEGER" if "int" in s else "REAL" if "float" in s else "TEXT"


def create_db(task):
    os.makedirs(os.path.dirname(task.db_path), exist_ok=True)
    if os.path.exists(task.db_path):
        os.remove(task.db_path)
    cols = []
    for f in dataclasses.fields(task.row_type):
        if f.name == task.db_key and "str" in str(f.type):
            cols.append(f"{f.name} TEXT PRIMARY KEY")
        elif f.name == task.db_key:
            cols.append(f"{f.name} INTEGER PRIMARY KEY AUTOINCREMENT")
        else:
            cols.append(f"{f.name} {py2sql(f.type)}")
    conn = sqlite3.connect(task.db_path)
    conn.execute(f"CREATE TABLE {task.table_name} ({', '.join(cols)})")
    conn.commit()
    conn.close()


import sqlite3  # noqa: E402

CLIP = {}
SQL_FAMILIES = ("Expense", "Recipe", "SimpleCalendar")
FILE_TASKS = ("FilesDeleteFile", "FilesMoveFile", "MarkorCreateFolder", "MarkorDeleteAllNotes",
              "MarkorDeleteNewestNote", "MarkorCreateNote", "MarkorDeleteNote", "MarkorMoveNote",
              "MarkorCreateNoteFromClipboard", "MarkorEditNote", "MarkorChangeNoteContent",
              "MarkorAddNoteHeader", "MarkorMergeNotes", "MarkorTranscribeReceipt",
              "MarkorTranscribeVideo", "SaveCopyOfReceiptTaskEval", "SimpleDrawProCreateDrawing",
              "CameraTakePhoto")


def setup_extra(task, name):
    """Create the app-DB schemas (as the real apps would) for music/video tasks."""
    def mk(path, *ddl):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            os.remove(path)
        c = sqlite3.connect(path)
        for d in ddl:
            c.execute(d)
        c.commit()
        c.close()

    if name.startswith("Retro"):
        from android_world.task_evals.single import retro_music as rm
        mk(rm._PLAYLIST_DB_PATH,
           "CREATE TABLE PlaylistEntity (playlist_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, playlist_name TEXT NOT NULL)",
           "CREATE TABLE SongEntity (song_key INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, playlist_creator_id INTEGER NOT NULL, id INTEGER NOT NULL, title TEXT NOT NULL, track_number INTEGER NOT NULL, year INTEGER NOT NULL, duration INTEGER NOT NULL, data TEXT NOT NULL, date_modified INTEGER NOT NULL, album_id INTEGER NOT NULL, album_name TEXT NOT NULL, artist_id INTEGER NOT NULL, artist_name TEXT NOT NULL, composer TEXT, album_artist TEXT)")
        mk(rm._PLAYBACK_DB_PATH,
           "CREATE TABLE playing_queue (_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, id INTEGER NOT NULL, title TEXT NOT NULL, duration INTEGER NOT NULL, data TEXT NOT NULL)")
        files = task.params["files"]
        dur = int(47.5 * 60 * 1000 / len(files)) if name == "RetroPlaylistDuration" else 200000
        for i, f in enumerate(files):
            t = f.split(".")[0]
            MEDIA[t] = (f"Row: 0 _id={i + 1}, title={t}, duration={dur}, _data=/sdcard/Music/{f}, "
                        f"album_id=1, album=Alb, artist_id=1, artist=Art, year=2020\n").encode()
    elif name.startswith("Vlc"):
        from android_world.task_evals.single import vlc
        mk(vlc._DB_PATH,
           "CREATE TABLE Playlist (id_playlist INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, name TEXT NOT NULL, file_count INTEGER NOT NULL DEFAULT 0, creation_date INTEGER NOT NULL)",
           "CREATE TABLE Media (id_media INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, type INTEGER NOT NULL, title TEXT NOT NULL, filename TEXT NOT NULL)",
           "CREATE TABLE PlaylistMediaRelation (media_id INTEGER NOT NULL, mrl TEXT NOT NULL, playlist_id INTEGER NOT NULL, position INTEGER NOT NULL)")
    elif name.startswith("AudioRecorder"):
        from android_world.env import device_constants as dc
        os.makedirs(dc.AUDIORECORDER_DATA, exist_ok=True)  # created by the real app
    elif name.startswith("OsmAnd"):
        os.makedirs("/data/media/0/Android/data/net.osmand/files/tracks", exist_ok=True)


EXTRA = ("RetroCreatePlaylist", "RetroSavePlaylist", "RetroPlaylistDuration", "RetroPlayingQueue",
         "VlcCreatePlaylist", "VlcCreateTwoPlaylists", "OsmAndFavorite", "OsmAndMarker", "OsmAndTrack", "AudioRecorderRecordAudio",
         "AudioRecorderRecordAudioWithFileName", "CameraTakeVideo", "SystemWifiTurnOn", "SystemWifiTurnOff",
         "SystemBluetoothTurnOn", "SystemBluetoothTurnOff", "SystemBrightnessMax", "SystemBrightnessMin",
         "SystemCopyToClipboard", "TurnOffWifiAndTurnOnBluetooth")


def covered(t):
    if t["name"] in EXTRA:
        return True
    n = t["name"]
    if t["family"] == "abc":
        return False  # IR answers: checked in check_ir() (state setup needs real apps)
    return t["oracle"] in {"sql_add", "sql_delete", "sql_delete_duplicate"} and n.startswith(SQL_FAMILIES) or n in FILE_TASKS


def run_one(t):
    env = FakeEnv()
    task = make_task(t["name"])
    if t["oracle"].startswith("sql") or t["name"] == "OsmAndMarker":
        create_db(task)
    setup_extra(task, t["name"])
    with contextlib.ExitStack() as st:
        for target in (
            mock.patch.object(task_eval.TaskEval, "initialize_device_time", lambda *a, **k: None),
            mock.patch.object(task_eval.TaskEval, "_initialize_apps", lambda *a, **k: None),
            mock.patch.object(adb_utils, "close_app", lambda *a, **k: None),
            mock.patch.object(adb_utils, "launch_app", lambda *a, **k: None),
            mock.patch.object(adb_utils, "set_root_if_needed", lambda *a, **k: None),
            mock.patch("android_world.task_evals.utils.user_data_generation.write_mp3_file_to_device", lambda *a, **k: None),
            mock.patch("time.sleep", lambda *a, **k: None),
            mock.patch.object(adb_utils, "set_clipboard_contents", lambda text, env: CLIP.update(v=text)),
            mock.patch.object(adb_utils, "get_clipboard_contents", lambda env: CLIP.get("v", "")),
        ):
            st.enter_context(target)
        for mod in ("android_world.utils.datetime_utils",):
            try:
                st.enter_context(mock.patch(mod + ".advance_system_time", lambda *a, **k: None))
            except Exception:  # noqa: BLE001
                pass
        task.initialize_task(env)
        before = task.is_successful(env)
        assert before == 0.0, f"is_successful already {before} before oracle (invalid test)"
        oracles.run(env, task, {"name": t["name"], "oracle": t["oracle"]})
        return task.is_successful(env)


def check_ir():
    from android_world.task_evals.information_retrieval import information_retrieval as ir
    from android_world.task_evals.information_retrieval import proto_utils
    ok = 0
    for t in TASKS:
        if t["family"] != "abc":
            continue
        task = make_task(t["name"])
        proto_utils.initialize_proto(task.task, task.params)
        ir._maybe_replace_date(task.params)
        task.initialized = True  # skip device-side setup (needs real apps)
        env = FakeEnv()
        env.interaction_cache = ", ".join(oracles._fmt_answer(a) for a in proto_utils.get_expected_answer(task.task))
        ok += task.is_successful(env) == 1.0
    return ok


def unit_tests():
    # maze
    lay = [list(" #  "), list("    "), list("#  #"), list("   $")]
    assert oracles.solve_maze(lay), "no path"
    pos = (0, 0)
    for m in oracles.solve_maze(lay):
        d = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}[m]
        pos = (pos[0] + d[0], pos[1] + d[1])
        assert lay[pos[0]][pos[1]] != "#"
    assert pos == (3, 3)
    # content parser incl. commas in values
    rows = oracles.parse_content_rows("Row: 0 _id=5, title=Hi, There, duration=1000, _data=/a/b.mp3\n",
                                      ["_id", "title", "duration", "_data"])
    assert rows == [{"_id": "5", "title": "Hi, There", "duration": "1000", "_data": "/a/b.mp3"}], rows
    # introspective insert
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE S (k INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, d INTEGER NOT NULL, x REAL NOT NULL, y TEXT)")
    insert_row = oracles.insert_row
    insert_row(c, "S", {"title": "a", "unknown": 1})
    assert c.execute("SELECT title,d,x,y FROM S").fetchall() == [("a", 0, 0.0, None)]
    # gpx
    g = oracles.add_gpx_waypoint("<gpx xmlns='http://www.topografix.com/GPX/1/1'/>", 1.5, 2.5, "n")
    assert 'lat="1.5"' in g and "<name>n</name>" in g
    assert "trkpt" in oracles.gpx_track([(1.0, 2.0)])
    print("unit tests OK")


if __name__ == "__main__":
    unit_tests()
    print("IR answers accepted by upstream is_successful:", check_ir(), "/ 25")
    want = set(sys.argv[1:])
    res = {"PASS": [], "FAIL": [], "SKIP": []}
    for t in TASKS:
        t = dict(t)
        t["oracle"] = oracle_kind(t)
        if want and t["name"] not in want:
            continue
        if not covered(t):
            res["SKIP"].append(t["name"])
            continue
        try:
            s = run_one(t)
            res["PASS" if s == 1.0 else "FAIL"].append(t["name"] + ("" if s == 1.0 else f" (score {s})"))
        except Exception as e:  # noqa: BLE001
            res["FAIL"].append(f"{t['name']}: {type(e).__name__}: {str(e)[:200]}")
            if os.environ.get("TB"):
                traceback.print_exc()
    for k, v in res.items():
        print(f"{k} ({len(v)}):", *v, sep="\n  ")
