"""Regression check for the vita-runtime sidecar, run inside its image (no LLM calls):

    docker run --rm -v "$PWD/src/vita-bench/scripts:/probe:ro" <vita-runtime-image> \
        python3 /probe/test_sidecar_threads.py

VitaBench keeps its data registries (locations, stores, products) per thread. FastMCP
runs sync tools in a worker pool, so tool calls must still reach the thread that built
the environment. Calls a data-backed domain tool through FastMCP's own dispatch, from
several fresh threads, and expects real data back.
"""

import asyncio
import json
import sys
import threading

sys.path.insert(0, "/app")
import server  # noqa: E402  (builds the runtime from /app/task_config.json)


def call_from_new_thread(tool: str, args: dict) -> str:
    out: dict = {}

    def run() -> None:
        try:
            result = asyncio.run(server.mcp.call_tool(tool, args))
            out["text"] = json.dumps(result, default=str)
        except Exception as exc:  # noqa: BLE001
            out["text"] = f"EXC {type(exc).__name__}: {exc}"

    t = threading.Thread(target=run)
    t.start()
    t.join()
    return out["text"]


tools = {t.name for t in server.runtime.environment.get_tools()}
assert "address_to_longitude_latitude" in tools, sorted(tools)
from vita.data_model.tasks import Location  # noqa: E402

# Any address the task's own data knows; read on the thread that owns the registries.
on_vita_thread = getattr(server, "on_vita_thread", lambda fn: fn())
probe = on_vita_thread(lambda: next(iter(Location.get_all())))
# start_conversation would call the user-simulator LLM; only its gate flag is needed here.
server.runtime.start_tool_called = True
for i in range(3):
    text = call_from_new_thread("address_to_longitude_latitude", {"address": probe})
    assert "list index out of range" not in text and "EXC" not in text, f"call {i}: {text[:300]}"
    print(f"call {i} OK: {text[:120]}")
print("test_sidecar_threads: OK")
