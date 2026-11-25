"""Tiny client for the daemon: `client.py wait|score|oracle`."""
import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:5000"


def call(path, method="GET", timeout=900):
    req = urllib.request.Request(BASE + path, method=method, data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read() or b"{}"
        try:
            return e.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return e.code, {"error": raw.decode(errors="replace")}


def wait(max_s=1500):
    t0 = time.time()
    while time.time() - t0 < max_s:
        try:
            code, body = call("/ready", timeout=10)
            if code == 200:
                return True
            if code == 500:
                print(body.get("error"), file=sys.stderr)
                return False
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)
    return False


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "wait":
        sys.exit(0 if wait() else 1)
    if cmd in ("score", "oracle"):
        if not wait():
            print("daemon never became ready", file=sys.stderr)
            sys.exit(2)
        code, body = call("/" + cmd, "POST")
        if code != 200 and isinstance(body, dict) and body.get("error"):
            print(body["error"], file=sys.stderr)
        print(json.dumps(body))
        sys.exit(0 if code == 200 else 1)
