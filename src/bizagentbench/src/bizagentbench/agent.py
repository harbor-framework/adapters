"""Harbor custom agent: forward the native assistant request without rewriting it."""
from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
import uuid

import httpx
from harbor.agents.base import BaseAgent


class BizAgentBenchAgent(BaseAgent):
    @staticmethod
    def name():
        return "bizagentbench-llm-agent"

    def version(self):
        return "0.1.0"

    def __init__(self, *args, model_config=None, **kwargs):
        super().__init__(*args, **kwargs)
        path = model_config or os.environ.get("BIZ_MODEL_CONFIG")
        if not path:
            raise ValueError("Set BIZ_MODEL_CONFIG to the same model config used for generation")
        self.config = json.loads(Path(path).read_text("utf-8"))["agent"]
        if self.model_name and self.model_name != self.config["model"]:
            if self.model_name.split("/", 1)[-1] != self.config["model"]:
                raise ValueError("Harbor model metadata differs from the native model config")

    async def setup(self, environment):
        result = await environment.exec("python /app/biz.py --help", timeout_sec=15)
        if result.return_code:
            raise RuntimeError(result.stderr)

    async def answer(self, request):
        if request["model"] != self.config["model"]:
            raise ValueError("Agent model differs from generated native request")
        key = os.environ.get(self.config["api_key_env"], "")
        if not key:
            raise ValueError("Missing agent credential environment variable: " + self.config["api_key_env"])
        # Forward the exact streaming request. The native side assembles it,
        # checks provider identity, compacts context and performs retries.
        headers = {"Authorization": "Bearer " + key}
        async with httpx.AsyncClient(
            timeout=self.config["timeout_seconds"], trust_env=self.config.get("trust_env", False),
            **({"proxy": self.config["proxy"]} if self.config.get("proxy") else {}),
        ) as client:
            try:
                async with client.stream("POST", self.config["base_url"].rstrip("/") + "/chat/completions",
                                         json=request, headers=headers) as response:
                    data = await response.aread()
                    if response.status_code == 200:
                        return {"status": 200, "body": {"sse": data.decode("utf-8")}}
                    try:
                        body = json.loads(data)
                    except ValueError:
                        body = {"error": data.decode("utf-8", errors="replace")}
                    return {"status": response.status_code, "body": body}
            except httpx.HTTPError as exc:
                return {"status": 503, "body": {"error": "Bridge provider transport: " + type(exc).__name__}}

    async def run(self, instruction, environment, context):
        seen = set()
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        while True:
            response = await environment.exec("python /app/biz.py turn", timeout_sec=20)
            if response.return_code:
                raise RuntimeError(response.stderr)
            turn = json.loads(response.stdout)
            if turn["state"] == "finished":
                return
            if turn["state"] == "error":
                raise RuntimeError(turn["error"])
            if turn["state"] != "turn" or turn["turn_id"] in seen:
                await asyncio.sleep(0.2)
                continue
            seen.add(turn["turn_id"])
            # The native absolute timer includes in-flight provider requests.
            # Cancel the host relay when native finalization wins the race,
            # including providers that keep streaming beyond the episode budget.
            async def watch_finalization():
                while True:
                    await asyncio.sleep(1)
                    probe = await environment.exec("python /app/biz.py turn", timeout_sec=20)
                    if probe.return_code:
                        raise RuntimeError(probe.stderr)
                    state = json.loads(probe.stdout)
                    if state["state"] in ("finished", "error"):
                        return state

            answer = asyncio.create_task(self.answer(turn["request"]))
            watcher = asyncio.create_task(watch_finalization())
            try:
                done, _ = await asyncio.wait((answer, watcher), return_when=asyncio.FIRST_COMPLETED)
                if watcher in done:
                    state = watcher.result()
                    if state["state"] == "error":
                        raise RuntimeError(state["error"])
                    return
                result = answer.result()
            finally:
                for task in (answer, watcher):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(answer, watcher, return_exceptions=True)
            # Only trusted adapter code can report provider HTTP/SSE failures.
            # The untrusted main-container API accepts assistant messages only.
            # Chunk below Linux's argument-size limit, with no shell interpolation
            # of model text. No provider response/credential is staged in main.
            target = "/private/relay-" + uuid.uuid4().hex + ".json"
            encoded = base64.b64encode(json.dumps({"turn_id": turn["turn_id"], **result}).encode()).decode()
            try:
                for offset in range(0, len(encoded), 32768):
                    chunk = encoded[offset:offset + 32768]
                    reply = await environment.service_exec(
                        'python -I -c "import base64; from pathlib import Path; '
                        'Path(\'/private\').mkdir(exist_ok=True); '
                        f'open(\'{target}\',\'ab\').write(base64.b64decode(\'{chunk}\'))"',
                        service="business", timeout_sec=20,
                    )
                    if reply.return_code:
                        raise RuntimeError(reply.stderr)
                reply = await environment.service_exec(
                    "python -I /service/submit_response.py " + target,
                    service="business", timeout_sec=20,
                )
            finally:
                await environment.service_exec(
                    f'python -I -c "from pathlib import Path; Path(\'{target}\').unlink(missing_ok=True)"',
                    service="business", timeout_sec=20,
                )
            if reply.return_code:
                # A native deadline can finalize between polling and delivery.
                probe = await environment.exec("python /app/biz.py turn", timeout_sec=20)
                if not probe.return_code and json.loads(probe.stdout)["state"] == "finished":
                    return
                raise RuntimeError(reply.stderr)
            with (self.logs_dir / "bridge.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"turn_id": turn["turn_id"], "status": result["status"]}) + "\n")
