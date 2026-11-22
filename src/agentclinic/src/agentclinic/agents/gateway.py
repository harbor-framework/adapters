import json
import shlex

from .errors import RuntimeRequestError

CLIENT_SCRIPT = r"""
import json
import sys
import time
import urllib.error
import urllib.request

base, action, payload, wait = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
deadline = time.time() + wait
while True:
    try:
        urllib.request.urlopen(base + "/health", timeout=2)
        break
    except OSError:
        if time.time() > deadline:
            print(json.dumps({"status": 0, "body": {"error": "clinic unreachable at " + base}}))
            sys.exit(0)
        time.sleep(0.5)
request = urllib.request.Request(
    base + "/api/" + action, data=payload.encode(), headers={"Content-Type": "application/json"}, method="POST"
)
try:
    with urllib.request.urlopen(request, timeout=300) as response:
        print(json.dumps({"status": response.status, "body": json.load(response)}))
except urllib.error.HTTPError as exc:
    try:
        body = json.loads(exc.read())
    except ValueError:
        body = {"error": "non-JSON error body"}
    print(json.dumps({"status": exc.code, "body": body}))
"""


class ClinicGateway:
    def __init__(
        self,
        environment,
        base_url: str = "http://clinic:8000",
        python: str = "python3",
        wait_sec: float = 60,
        timeout_sec: int = 960,
    ):
        self.environment = environment
        self.base_url = base_url
        self.python = python
        self.wait_sec = wait_sec
        self.timeout_sec = timeout_sec

    async def post(self, action: str, text: str) -> tuple[str, str]:
        command = " ".join(
            [
                shlex.quote(self.python),
                "-c",
                shlex.quote(CLIENT_SCRIPT),
                shlex.quote(self.base_url),
                shlex.quote(action),
                shlex.quote(json.dumps({"text": text})),
                str(self.wait_sec),
            ]
        )
        result = await self.environment.exec(command, timeout_sec=self.timeout_sec)
        if result.return_code != 0:
            raise RuntimeRequestError(f"clinic client exited with {result.return_code}: {(result.stderr or '')[:300]}")
        lines = [line for line in (result.stdout or "").splitlines() if line.strip()]
        try:
            outcome = json.loads(lines[-1])
        except (IndexError, ValueError) as exc:
            raise RuntimeRequestError(f"unreadable clinic client output: {(result.stdout or '')[:300]!r}") from exc
        if outcome["status"] != 200:
            raise RuntimeRequestError(f"clinic returned {outcome['status']}: {outcome['body'].get('error')}")
        return outcome["body"]["status"], outcome["body"]["reply"]
