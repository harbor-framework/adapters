"""Deterministic reference ("oracle") solutions for AndroidWorld tasks.

AndroidWorld ships NO reference solutions. Every oracle here puts the device (or the answer
file) into the state that the task's own, unmodified `is_successful` checks, using the same
seed-fixed parameters the task was initialised with. Three methods are used (recorded per task
in task.toml tags and in NOTES.md):

  computed   question-answering tasks: answer derived from the task's ground-truth proto.
  injection  state written directly (adb file ops, settings, app SQLite DBs, GPX files, ...),
             i.e. the end state of the app/UI work, bypassing the UI.
  ui-script  deterministic scripted UI/automation (upstream helpers, adb intents, Chrome
             DevTools), for tasks whose checker reads the live UI or a web page.

All device I/O goes through `Dev` so the logic can be unit-tested with a fake (see
tests/test_oracles.py in the adapter). Handler names must match ORACLE_KINDS in adapter.py.
"""
import contextlib
import datetime
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ANSWER_FILE = Path("/workspace/answer.txt")
MARKOR = "/storage/emulated/0/Documents/Markor"
DOWNLOAD = "/storage/emulated/0/Download"


# --------------------------------------------------------------------------- device wrapper
class Dev:
    """Thin wrapper over the AndroidWorld env (kept tiny so tests can fake it)."""

    def __init__(self, env):
        self.env = env

    def sh(self, *args) -> str:
        from android_world.env import adb_utils

        r = adb_utils.issue_generic_request(["shell", *args], self.env.controller)
        return r.generic.output.decode(errors="replace").replace("\r", "")

    def cat(self, path: str) -> str:
        return self.sh("cat", shlex.quote(path))

    def write_bytes(self, remote: str, data: bytes) -> None:
        from android_world.utils import file_utils

        self.sh("mkdir", "-p", shlex.quote(os.path.dirname(remote)))
        with tempfile.TemporaryDirectory() as d:
            local = os.path.join(d, os.path.basename(remote) or "f")
            Path(local).write_bytes(data)
            file_utils.copy_file_to_device(local, remote, self.env.controller)

    def write_text(self, remote: str, text: str) -> None:
        self.write_bytes(remote, text.encode())

    @contextlib.contextmanager
    def edit_db(self, remote_db: str, app_name: str | None = None):
        """Pull a SQLite DB, yield a connection, commit, push back, close the app."""
        from android_world.env import adb_utils

        if app_name:
            adb_utils.close_app(app_name, self.env.controller)
        with self.env.controller.pull_file(remote_db, 10) as d:
            local = os.path.join(d, os.path.basename(remote_db))
            conn = sqlite3.connect(local)
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()
            self.sh("rm", "-f", shlex.quote(remote_db + "-wal"), shlex.quote(remote_db + "-shm"))
            self.env.controller.push_file(local, remote_db, 10)
        if app_name:
            adb_utils.close_app(app_name, self.env.controller)

    # --- UI helpers (used only by ui-script oracles)
    def ui_elements(self):
        return self.env.controller.get_ui_elements()

    def tap_label(self, labels, timeout=20.0, exact=True) -> bool:
        """Tap the first visible element whose text/content-desc equals one of `labels`."""
        from android_world.env import adb_utils

        labels = [x.lower() for x in ([labels] if isinstance(labels, str) else labels)]
        attempts = max(1, int(timeout))
        for _ in range(attempts):
            for el in self.ui_elements():
                if getattr(el, "is_visible", True) is False:
                    continue
                bbox = getattr(el, "bbox_pixels", None)
                if not bbox or bbox.width <= 0 or bbox.height <= 0:
                    continue
                for attr in (el.text, el.content_description):
                    if attr and (
                        attr.strip().lower() in labels
                        if exact
                        else any(l in attr.lower() for l in labels)
                    ):
                        x, y = bbox.center
                        adb_utils.tap_screen(int(x), int(y), self.env.controller)
                        time.sleep(1.0)
                        return True
            time.sleep(1.0)
        return False

    def has_label(self, labels) -> bool:
        labels = [x.lower() for x in ([labels] if isinstance(labels, str) else labels)]
        return any(
            getattr(el, "is_visible", True) is not False
            and a
            and a.strip().lower() in labels
            for el in self.ui_elements()
            for a in (el.text, el.content_description)
        )


def _dev(env_or_dev) -> Dev:
    return env_or_dev if isinstance(env_or_dev, Dev) else Dev(env_or_dev)


# --------------------------------------------------------------------------- pure helpers
def _fmt_answer(a):
    from android_world.task_evals.information_retrieval import datetime_utils as dtu

    if isinstance(a, datetime.datetime):
        return a.strftime(dtu.DATE_FORMAT + " %H:%M")
    if isinstance(a, datetime.date):
        return a.strftime(dtu.DATE_FORMAT)
    if isinstance(a, datetime.time):
        return a.strftime("%H:%M")
    if isinstance(a, float):
        return str(int(a)) if a == int(a) else repr(a)
    return str(a)


def insert_row(conn, table: str, values: dict) -> int:
    """Insert `values` into `table`, filling any other NOT-NULL, no-default column with a
    type-appropriate zero value. Unknown keys in `values` are ignored (schema introspection)."""
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()  # cid,name,type,notnull,dflt,pk
    row = {}
    for _cid, name, typ, notnull, dflt, pk in cols:
        if name in values:
            row[name] = values[name]
        elif pk and "INT" in (typ or "").upper():
            continue  # rowid alias: let SQLite assign
        elif notnull and dflt is None:
            t = (typ or "").upper()
            row[name] = 0 if "INT" in t else 0.0 if ("REAL" in t or "FLOA" in t or "DOUB" in t) else ""
    keys = list(row)
    cur = conn.execute(
        f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})",
        [row[k] for k in keys],
    )
    return cur.lastrowid


def parse_content_rows(out: str, keys: list[str]) -> list[dict]:
    """Parse `adb shell content query` output; `keys` must be in projection order."""
    rows = []
    for chunk in re.split(r"(?:^|\n)Row: \d+ ", out):
        if "=" not in chunk:
            continue
        d, pos = {}, []
        for k in keys:
            m = re.search(rf"(?:^|, ){re.escape(k)}=", chunk)
            pos.append((m.start(), m.end()) if m else None)
        for i, k in enumerate(keys):
            if pos[i] is None:
                continue
            end = len(chunk)
            for j in range(i + 1, len(keys)):
                if pos[j] is not None:
                    end = pos[j][0]
                    break
            d[k] = chunk[pos[i][1] : end].strip()
        rows.append(d)
    return rows


def solve_maze(layout: list[list[str]]) -> list[str]:
    """BFS from (0,0) to the '$' cell; returns moves among up/down/left/right ('#' = wall)."""
    n, m = len(layout), len(layout[0])
    goal = next((r, c) for r in range(n) for c in range(m) if layout[r][c] == "$")
    steps = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
    prev, q = {(0, 0): None}, [(0, 0)]
    while q:
        cur = q.pop(0)
        if cur == goal:
            break
        for name, (dr, dc) in steps.items():
            nxt = (cur[0] + dr, cur[1] + dc)
            if 0 <= nxt[0] < n and 0 <= nxt[1] < m and layout[nxt[0]][nxt[1]] != "#" and nxt not in prev:
                prev[nxt] = (cur, name)
                q.append(nxt)
    path, cur = [], goal
    while prev[cur] is not None:
        cur, name = prev[cur]
        path.append(name)
    return path[::-1]


def gpx_track(points: list[tuple[float, float]], name: str = "oracle") -> str:
    pts = "".join(f'<trkpt lat="{la}" lon="{lo}"></trkpt>' for la, lo in points)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="oracle" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><name>{name}</name><trkseg>{pts}</trkseg></trk></gpx>"
    )


def add_gpx_waypoint(gpx_text: str | None, lat: float, lon: float, name: str) -> str:
    ns = "http://www.topografix.com/GPX/1/1"
    ET.register_namespace("", ns)
    if gpx_text and gpx_text.strip().startswith("<"):
        root = ET.fromstring(gpx_text)
    else:
        root = ET.Element(f"{{{ns}}}gpx", {"version": "1.1", "creator": "oracle"})
    wpt = ET.SubElement(root, f"{{{ns}}}wpt", {"lat": str(lat), "lon": str(lon)})
    ET.SubElement(wpt, f"{{{ns}}}name").text = name
    return ET.tostring(root, encoding="unicode")


# --------------------------------------------------------------------------- computed (IR)
def answer_from_ground_truth(env, task, spec):
    from android_world.task_evals.information_retrieval import proto_utils

    answers = proto_utils.get_expected_answer(task.task)
    text = ", ".join(_fmt_answer(a) for a in answers)
    ANSWER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ANSWER_FILE.write_text(text + "\n")
    return text


# --------------------------------------------------------------------------- system settings
def _wait_setting(d: Dev, namespace: str, key: str, expected: set[str], retries: int = 10) -> None:
    for _ in range(retries):
        if d.sh("settings", "get", namespace, key).strip() in expected:
            return
        time.sleep(0.5)


def system_toggle(env, task, spec):
    from android_world.env import adb_utils

    d = _dev(env)
    name, p = spec["name"], task.params
    if name == "TurnOffWifiAndTurnOnBluetooth":
        adb_utils.toggle_wifi(env.controller, "off")
        adb_utils.toggle_bluetooth(env.controller, "on")
        _wait_setting(d, "global", "wifi_on", {"0"})
        _wait_setting(d, "global", "bluetooth_on", {"1"})
    elif "Wifi" in name:
        adb_utils.toggle_wifi(env.controller, p["on_or_off"])
        _wait_setting(d, "global", "wifi_on", {"1", "2"} if p["on_or_off"] == "on" else {"0"})
    elif "Bluetooth" in name:
        adb_utils.toggle_bluetooth(env.controller, p["on_or_off"])
        _wait_setting(d, "global", "bluetooth_on", {"1"} if p["on_or_off"] == "on" else {"0"})
    elif "Brightness" in name:
        adb_utils.set_brightness(p["max_or_min"], env.controller)
        _wait_setting(d, "system", "screen_brightness", {"255"} if p["max_or_min"] == "max" else {"1"})
    else:
        raise NotImplementedError(name)


def system_copy_clipboard(env, task, spec):
    from android_world.env import adb_utils

    adb_utils.set_clipboard_contents(task.params["clipboard_content"], env.controller)


def system_open_app(env, task, spec):
    from android_world.env import adb_utils

    d = _dev(env)
    if spec["name"] == "TurnOnWifiAndOpenApp":
        adb_utils.toggle_wifi(env.controller, "on")
        _wait_setting(d, "global", "wifi_on", {"1", "2"})
    adb_utils.launch_app(task.params["app_name"], env.controller)
    for _ in range(10):
        act, _ = adb_utils.get_current_activity(env.controller)
        if act and "launcher" not in act.lower():
            break
        time.sleep(1.0)


# --------------------------------------------------------------------------- files / markor
def files_delete(env, task, spec):
    t = task.delete_file_task
    _dev(env).sh("rm", "-f", shlex.quote(os.path.join(t.data_directory, task.params["file_name"])))


def files_move(env, task, spec):
    d, t, f = _dev(env), task.move_file_task, task.params["file_name"]
    d.sh("mkdir", "-p", shlex.quote(t.dest_directory))
    d.sh("mv", shlex.quote(os.path.join(t.source_directory, f)), shlex.quote(os.path.join(t.dest_directory, f)))


def markor_create_folder(env, task, spec):
    _dev(env).sh("mkdir", "-p", shlex.quote(f"{MARKOR}/{task.params['folder_name']}"))


def markor_delete_all(env, task, spec):
    # single string on purpose: adb joins args and the device shell expands the globs
    _dev(env).sh(f"rm -rf {MARKOR}/* {MARKOR}/.[!.]* 2>/dev/null; true")


def markor_delete_newest(env, task, spec):
    newest = task.initial_file_list_sorted[-1]  # ascending by change_time
    _dev(env).sh("rm", "-f", shlex.quote(f"{MARKOR}/{newest.file_name}"))


def markor_create_note(env, task, spec):
    _dev(env).write_text(f"{MARKOR}/{task.params['file_name']}", task.params["text"] + "\n")


def markor_create_file_from_validator(env, task, spec):
    """CreateNoteFromClipboard / TranscribeReceipt / TranscribeVideo: all end in a Markor file
    whose (fuzzy-matched) content is known from the task params (CreateFile validator)."""
    p = task.create_file_task.params
    _dev(env).write_text(f"{MARKOR}/{p['file_name']}", p["text"] + "\n")


def markor_edit_note(env, task, spec):
    d, p = _dev(env), task.params
    path = f"{MARKOR}/{p['file_name']}"
    cur = d.cat(path).strip()
    if p["edit_type"] == "header":
        new = p["header"] + "\n" + cur
    elif p["edit_type"] == "footer":
        new = cur + "\n" + p["footer"]
    else:
        new = p["replace_text"]
    d.write_text(path, new + "\n")


def markor_change_note_content(env, task, spec):
    d, p = _dev(env), task.params
    d.sh("rm", "-f", shlex.quote(f"{MARKOR}/{p['original_name']}"))
    d.write_text(f"{MARKOR}/{p['new_name']}", p["updated_content"] + "\n")


def markor_add_note_header(env, task, spec):
    d, p = _dev(env), task.params
    d.sh("rm", "-f", shlex.quote(f"{MARKOR}/{p['original_name']}"))
    # checker: exact match of header + "\n\n" + original_content + "\n"
    d.write_text(f"{MARKOR}/{p['new_name']}", p["header"] + "\n\n" + p["original_content"] + "\n")


def markor_merge_notes(env, task, spec):
    p = task.params
    text = "\n\n".join([p["file1_content"], p["file2_content"], p["file3_content"]]) + "\n"
    _dev(env).write_text(f"{MARKOR}/{p['new_file_name']}", text)


# --------------------------------------------------------------------------- SQLite apps
def _ids(task, rows):
    return [getattr(r, task.db_key) for r in rows]


def sql_add(env, task, spec):
    """Add the task's reference rows to the app DB (same API upstream uses to seed noise)."""
    from android_world.task_evals.common_validators import sqlite_validators as sv

    task.add_rows(task.params[sv.ROW_OBJECTS], env)


def _delete_ids(env, task, ids):
    d = _dev(env)
    with d.edit_db(task.db_path, task.app_name_with_db) as conn:
        conn.execute(
            f"DELETE FROM {task.table_name} WHERE {task.db_key} IN ({','.join('?' * len(ids))})", ids
        )


def sql_delete(env, task, spec):
    _delete_ids(env, task, _ids(task, task.rows_to_delete))


def sql_delete_duplicate(env, task, spec):
    # checker accepts removal of exactly one of the two identical rows
    _delete_ids(env, task, _ids(task, task.rows_to_delete[:1]))


# --------------------------------------------------------------------------- SMS / contacts
def _send_sms(env, number, message):
    from android_world.env import adb_utils, tools

    d = _dev(env)
    clean_num = re.sub(r"[-\s]", "", number)

    def _sent_count() -> int:
        raw = d.sh("content", "query", "--uri", "content://sms/sent", "--projection", "address:body")
        rows = parse_content_rows(raw, ["address", "body"])
        return sum(
            1
            for r in rows
            if re.sub(r"[-\s]", "", r.get("address", "")) == clean_num and r.get("body") == message
        )

    before_count = _sent_count()
    adb_utils.close_app("simple sms messenger", env.controller)
    time.sleep(0.5)
    if any(ch in message for ch in ('"', "$", "`", "\\")):
        safe_msg = message.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
        adb_utils.send_android_intent(
            command="start",
            action="android.intent.action.SENDTO",
            env=env.controller,
            data_uri=f"sms:{number}",
            extras={"sms_body": safe_msg},
        )
        time.sleep(5.0)
        pkg = adb_utils.extract_package_name(adb_utils.get_current_activity(env.controller)[0] or "")
        send_label = tools.SMS_SEND_TEXT if pkg == "com.google.android.apps.messaging" else tools.SIMPLE_SMS_SEND_TEXT
        assert d.tap_label(send_label), f"SMS send button {send_label!r} not found"
    else:
        tools.AndroidToolController(env.controller).send_sms(number, message)

    for _ in range(15):
        if _sent_count() > before_count:
            break
        time.sleep(1.5)
    adb_utils.launch_app("simple sms messenger", env.controller)  # checker wants this app in front
    time.sleep(2.0)


def sms_send(env, task, spec):
    _send_sms(env, task.params["number"], task.params["message"])


def markor_create_note_and_sms(env, task, spec):
    p = task.params
    _dev(env).write_text(f"{MARKOR}/{p['file_name']}", p["text"] + "\n")
    _send_sms(env, p["number"], p["text"])


def contacts_add(env, task, spec):
    from android_world.utils import contacts_utils

    contacts_utils.add_contact(task.params["name"], task.params["number"], env.controller)


def contacts_draft(env, task, spec):
    from android_world.env import adb_utils

    p = task.params
    ptype = {"Home": 1, "Work": 3, "Mobile": 2}[p["phone_label"]]
    adb_utils.close_app("contacts", env.controller)
    full_name = shlex.quote(f"{p['first']} {p['last']}")
    phone = shlex.quote(p["phone"])
    cmd = (
        "am start -a android.intent.action.INSERT -t vnd.android.cursor.dir/contact "
        f"-e name {full_name} -e phone {phone} --ei phone_type {ptype}"
    )
    adb_utils.issue_generic_request(["shell", cmd], env.controller)
    time.sleep(3.0)  # editor stays open, NOT saved (task says do not hit save)


# --------------------------------------------------------------------------- clock (ui-script)
def _open_clock(d: Dev):
    from android_world.env import adb_utils

    adb_utils.launch_app("clock", d.env.controller)
    time.sleep(3.0)


def clock_stopwatch_running(env, task, spec):
    d = _dev(env)
    _open_clock(d)
    assert d.tap_label("Stopwatch"), "Stopwatch tab not found"
    assert d.tap_label("Start"), "Start button not found"


def clock_stopwatch_paused(env, task, spec):
    d = _dev(env)
    _open_clock(d)
    assert d.tap_label("Stopwatch"), "Stopwatch tab not found"
    if d.has_label("Pause"):
        d.tap_label("Pause")


def clock_timer_entry(env, task, spec):
    d, p = _dev(env), task.params
    _open_clock(d)
    assert d.tap_label("Timer"), "Timer tab not found"
    digits = f"{p['hours']:02d}{p['minutes']:02d}{p['seconds']:02d}".lstrip("0") or "0"
    for ch in digits:  # keypad fills right-to-left: HHMMSS without leading zeros
        assert d.tap_label(ch), f"keypad digit {ch} not found"


# --------------------------------------------------------------------------- browser (CDP)
def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _cdp_session(port=9222, timeout=60):
    import urllib.request

    import websocket  # websocket-client

    subprocess.run(["adb", "forward", f"tcp:{port}", "localabstract:chrome_devtools_remote"], check=True)
    attempts = max(1, int(timeout // 2))
    for _ in range(attempts):
        try:
            tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5))
            pages = [t for t in tabs if t.get("type") == "page" and "10.0.2.2" in t.get("url", "")]
            if pages:
                return websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=30)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    raise RuntimeError("Chrome DevTools page not found")


def _cdp_eval(ws, expr):
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 1:
            if "exceptionDetails" in msg.get("result", {}):
                raise RuntimeError(msg["result"]["exceptionDetails"])
            return msg["result"]["result"].get("value")


def _open_task_html_in_chrome(d: Dev):
    """Serve the task's own task.html (read from the device) on the container loopback and
    open it in Chrome via 10.0.2.2. Bypasses the Files-app step of the original goal."""
    import functools
    import http.server
    import threading

    web = Path(tempfile.mkdtemp())
    (web / "task.html").write_text(d.cat(f"{DOWNLOAD}/task.html"))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(web))
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    d.sh("am", "start", "-a", "android.intent.action.VIEW", "-d", f"http://10.0.2.2:{port}/task.html",
         "-n", "com.android.chrome/com.google.android.apps.chrome.Main")
    for _ in range(6):  # dismiss Chrome first-run screens if they appear
        time.sleep(3)
        if not d.tap_label(["Accept & continue", "Use without an account", "No thanks", "Got it",
                            "Not now", "Skip"], timeout=3):
            break
    return srv, web


def _browser(env, body):
    d = _dev(env)
    srv, web = _open_task_html_in_chrome(d)
    cdp_port = _free_port()
    ws = None
    try:
        ws = _cdp_session(port=cdp_port)
        body(ws)
        time.sleep(2)
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass
        subprocess.run(["adb", "forward", "--remove", f"tcp:{cdp_port}"], check=False)
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(web, ignore_errors=True)


def browser_maze(env, task, spec):
    def body(ws):
        layout = json.loads(_cdp_eval(ws, "JSON.stringify(mazeLayout)"))
        for mv in solve_maze(layout):
            _cdp_eval(ws, f"moveCharacter('{mv}')")

    _browser(env, body)


def browser_multiply(env, task, spec):
    def body(ws):
        _cdp_eval(ws, "for (let i=0;i<5;i++) handleButtonClick(); "
                      "document.getElementById('answer').value = numbers.reduce((a,b)=>a*b,1); "
                      "checkAnswer(); 1")

    _browser(env, body)


def browser_draw(env, task, spec):
    def body(ws):
        _cdp_eval(ws, "taskColors.forEach((c,i)=>{ctx.fillStyle=c;ctx.fillRect(10,20+i*60,100,30);}); "
                      "document.getElementById('submitButton').click(); 1")

    _browser(env, body)


# --------------------------------------------------------------------------- music / video DBs
def _sql_int(val, default: int = 0) -> int:
    if val is None or val == "" or str(val).upper() == "NULL":
        return default
    return int(val)


def _sql_str(val, default: str = "") -> str:
    if val is None or str(val).upper() == "NULL":
        return default
    return str(val)


def _media_info(d: Dev, titles: list[str]) -> list[dict]:
    keys = ["_id", "title", "duration", "_data", "album_id", "album", "artist_id", "artist", "year"]
    out = []
    for t in titles:
        info = None
        for _ in range(8):  # MediaStore may still be scanning the freshly written files
            safe = t.replace("'", "''")
            raw = d.sh("content", "query", "--uri", "content://media/external/audio/media",
                       "--projection", ":".join(keys), "--where", f'"title=\'{safe}\'"')
            rows = parse_content_rows(raw, keys)
            if rows:
                info = rows[0]
                break
            time.sleep(3)
        if info is None:
            raise RuntimeError(f"song {t!r} not found in MediaStore")
        out.append(info)
    return out


def _song_values(info: dict) -> dict:
    return {"id": _sql_int(info.get("_id")), "title": _sql_str(info.get("title")),
            "duration": _sql_int(info.get("duration")), "data": _sql_str(info.get("_data")),
            "album_id": _sql_int(info.get("album_id")), "album_name": _sql_str(info.get("album")),
            "artist_id": _sql_int(info.get("artist_id")), "artist_name": _sql_str(info.get("artist")),
            "year": _sql_int(info.get("year")), "date_modified": int(time.time())}


def retro_playlist(env, task, spec):
    from android_world.task_evals.single import retro_music as rm

    d, p = _dev(env), task.params
    titles = [f.split(".")[0] for f in p["files"]]
    infos = _media_info(d, titles)
    with d.edit_db(rm._PLAYLIST_DB_PATH, rm._APP_NAME) as conn:
        pid = insert_row(conn, "PlaylistEntity", {"playlist_name": p["playlist_name"]})
        for info in infos:  # insertion order == song_key order == order_in_playlist
            insert_row(conn, "SongEntity", {**_song_values(info), "playlist_creator_id": pid})
    if spec["name"] == "RetroSavePlaylist":
        m3u = "#EXTM3U\n" + "".join(
            f"#EXTINF:{_sql_int(i.get('duration')) // 1000},{_sql_str(i.get('title'))}\n{_sql_str(i.get('_data'))}\n"
            for i in infos
        )
        d.write_text(f"{DOWNLOAD}/{p['playlist_name']}.m3u", m3u)


def retro_queue(env, task, spec):
    from android_world.task_evals.single import retro_music as rm

    d = _dev(env)
    infos = _media_info(d, [f.split(".")[0] for f in task.params["files"]])
    if d.sh(f"test -f {shlex.quote(rm._PLAYBACK_DB_PATH)} && echo OK || echo MISSING").strip() == "MISSING":
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, os.path.basename(rm._PLAYBACK_DB_PATH))
            conn = sqlite3.connect(local)
            conn.execute(
                "CREATE TABLE playing_queue ("
                "_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, "
                "id INTEGER NOT NULL, title TEXT NOT NULL, "
                "duration INTEGER NOT NULL, data TEXT NOT NULL)"
            )
            conn.commit()
            conn.close()
            d.write_bytes(rm._PLAYBACK_DB_PATH, Path(local).read_bytes())
    with d.edit_db(rm._PLAYBACK_DB_PATH, rm._APP_NAME) as conn:
        conn.execute("DELETE FROM playing_queue")
        for info in infos:
            insert_row(conn, "playing_queue", _song_values(info))


def vlc_playlists(env, task, spec):
    from android_world.task_evals.single import vlc

    d = _dev(env)
    specs = (
        [(task.params["playlist_name1"], task.params["files1"]),
         (task.params["playlist_name2"], task.params["files2"])]
        if spec["name"] == "VlcCreateTwoPlaylists"
        else [(task.params["playlist_name"], task.params["files"])]
    )
    with d.edit_db(vlc._DB_PATH, vlc._APP_NAME) as conn:
        for name, files in specs:
            pid = insert_row(conn, "Playlist", {"name": name, "creation_date": int(time.time())})
            for pos, fn in enumerate(files):
                mrl = f"file:///storage/emulated/0/VLCVideos/{fn}"
                row = conn.execute("SELECT id_media FROM Media WHERE filename=?", (fn,)).fetchone()
                mid = row[0] if row else insert_row(
                    conn, "Media", {"filename": fn, "title": fn, "type": 1, "mrl": mrl})
                insert_row(conn, "PlaylistMediaRelation",
                           {"media_id": mid, "playlist_id": pid, "position": pos, "mrl": mrl})


# --------------------------------------------------------------------------- OsmAnd
def osmand_favorite(env, task, spec):
    from android_world.task_evals.single import osmand

    d, loc = _dev(env), task.params["location"]
    lat, lon = osmand._lookup_location_coords(loc)
    try:
        cur = d.cat(osmand._FAVORITES_PATH)
    except Exception:  # noqa: BLE001
        cur = None
    d.write_text(osmand._FAVORITES_PATH, add_gpx_waypoint(cur, lat, lon, loc))


def osmand_marker(env, task, spec):
    from android_world.task_evals.single import osmand

    d, loc = _dev(env), task.params["location"]
    lat, lon = osmand._lookup_location_coords(loc)
    with d.edit_db("/data/data/net.osmand/databases/map_markers_db", "osmand") as conn:
        insert_row(conn, "map_markers", {
            "marker_id": f"oracle_{int(time.time())}", "marker_lat": lat, "marker_lon": lon,
            "marker_description": "", "marker_active": 1, "marker_added": int(time.time() * 1000),
            "title": loc, "marker_map_object_name": loc})


def osmand_track(env, task, spec):
    from android_world.task_evals.single import osmand

    d = _dev(env)
    pts = osmand._lookup_target_waypoints(task.params["waypoints"])
    d.write_text(f"{osmand._DEVICE_FILES}/tracks/oracle_track.gpx", gpx_track(pts))


# --------------------------------------------------------------------------- media files
def _png_bytes(fmt="PNG") -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, fmt)
    return buf.getvalue()


def camera_photo(env, task, spec):
    _dev(env).write_bytes("/sdcard/Pictures/IMG_oracle.jpg", _png_bytes("JPEG"))


def camera_video(env, task, spec):
    from android_world.task_evals.utils import user_data_generation as udg

    udg.write_video_file_to_device("VID_oracle.mp4", "/sdcard/Movies", env, messages=["oracle"],
                                   message_display_time=1, fps=1)


def _m4a_bytes() -> bytes:
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "a.m4a")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1", "-c:a", "aac", out], check=True)
        return Path(out).read_bytes()


def audio_record(env, task, spec):
    from android_world.env import device_constants as dc

    name = (task.params["file_name"] + ".m4a") if spec["name"].endswith("WithFileName") else "oracle_recording.m4a"
    _dev(env).write_bytes(f"{dc.AUDIORECORDER_DATA}/{name}", _m4a_bytes())


def gallery_copy(env, task, spec):
    d, f = _dev(env), task.params["file_name"]
    d.sh("mkdir", "-p", shlex.quote(DOWNLOAD))
    d.sh("cp", shlex.quote(f"/sdcard/DCIM/{f}"), shlex.quote(f"{DOWNLOAD}/{f}"))


def draw_create(env, task, spec):
    f = task.params["file_name"]
    ext = f.rsplit(".", 1)[-1].lower()
    if ext == "svg":
        data = b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="red"/></svg>'
    else:
        data = _png_bytes("JPEG" if ext in ("jpg", "jpeg") else "PNG")
    _dev(env).write_bytes(f"/storage/emulated/0/Pictures/{f}", data)


# --------------------------------------------------------------------------- registry
# kind -> (handler, method)
KINDS = {
    "answer": (answer_from_ground_truth, "computed"),
    "system_toggle": (system_toggle, "injection"),
    "system_clipboard": (system_copy_clipboard, "injection"),
    "system_open_app": (system_open_app, "injection"),
    "files_delete": (files_delete, "injection"),
    "files_move": (files_move, "injection"),
    "markor_create_folder": (markor_create_folder, "injection"),
    "markor_delete_all": (markor_delete_all, "injection"),
    "markor_delete_newest": (markor_delete_newest, "injection"),
    "markor_create_note": (markor_create_note, "injection"),
    "markor_create_file": (markor_create_file_from_validator, "injection"),
    "markor_edit_note": (markor_edit_note, "injection"),
    "markor_change_content": (markor_change_note_content, "injection"),
    "markor_add_header": (markor_add_note_header, "injection"),
    "markor_merge": (markor_merge_notes, "injection"),
    "markor_note_and_sms": (markor_create_note_and_sms, "ui-script"),
    "sql_add": (sql_add, "injection"),
    "sql_delete": (sql_delete, "injection"),
    "sql_delete_duplicate": (sql_delete_duplicate, "injection"),
    "sms_send": (sms_send, "ui-script"),
    "contacts_add": (contacts_add, "ui-script"),
    "contacts_draft": (contacts_draft, "ui-script"),
    "clock_stopwatch_running": (clock_stopwatch_running, "ui-script"),
    "clock_stopwatch_paused": (clock_stopwatch_paused, "ui-script"),
    "clock_timer_entry": (clock_timer_entry, "ui-script"),
    "browser_maze": (browser_maze, "ui-script"),
    "browser_multiply": (browser_multiply, "ui-script"),
    "browser_draw": (browser_draw, "ui-script"),
    "retro_playlist": (retro_playlist, "injection"),
    "retro_queue": (retro_queue, "injection"),
    "vlc_playlists": (vlc_playlists, "injection"),
    "osmand_favorite": (osmand_favorite, "injection"),
    "osmand_marker": (osmand_marker, "injection"),
    "osmand_track": (osmand_track, "injection"),
    "camera_photo": (camera_photo, "injection"),
    "camera_video": (camera_video, "injection"),
    "audio_record": (audio_record, "injection"),
    "gallery_copy": (gallery_copy, "injection"),
    "draw_create": (draw_create, "injection"),
}


def run(env, task, spec):
    kind = spec.get("oracle")
    if kind not in KINDS:
        raise NotImplementedError(f"no oracle for {spec['name']} (kind={kind!r})")
    return KINDS[kind][0](env, task, spec)
