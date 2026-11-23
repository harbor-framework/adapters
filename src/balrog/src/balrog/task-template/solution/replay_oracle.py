"""Execute the frozen expert actions through the public game interface."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

SERVER = "http://game:8080"
payload = json.loads(Path("/solution/oracle_actions.json").read_text(encoding="utf-8"))
actions = payload["actions"] if isinstance(payload, dict) else payload
with urlopen(SERVER + "/observation", timeout=10) as response:
    observation = json.load(response)
for action in actions:
    if observation["done"]:
        raise RuntimeError("Episode ended before the expert trajectory was consumed")
    request = Request(SERVER + "/action",
        data=json.dumps({"action": action, "expected_step": observation["step"]}).encode(),
        headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        observation = json.load(response)
if not observation["terminated"]:
    raise RuntimeError("Expert trajectory did not terminate the mission")
print(json.dumps({"steps": observation["step"], "terminated": observation["terminated"]}))
