"""Harbor integration probe: native public calls plus deliberate local forgery."""
import asyncio
import json
from pathlib import Path
import tempfile
from harbor.agents.base import BaseAgent
from bizagentbench.agent import BizAgentBenchAgent


class OfflineSmokeAgent(BaseAgent):
    @staticmethod
    def name():
        return "bizagentbench-offline-smoke"

    def version(self):
        return "0.1.0"

    async def setup(self, environment):
        result = await environment.exec("test ! -e /opt/bizagentbench && test ! -e /tests/grade.py && test ! -e /service/private.json")
        assert result.return_code == 0, "Private grader/data entered the main container"

    async def run(self, instruction, environment, context):
        # These paths deliberately collide with authoritative artifact paths.
        # They must not affect evidence collected from the business service.
        forge = await environment.exec(
            "mkdir -p /private/runs /logs/verifier; "
            "echo '{\"forged\":true}' > /private/runs/evidence.json; "
            "echo 1 > /logs/verifier/reward.txt; echo '{\"reward\":1}' > /logs/verifier/reward.json"
        )
        assert forge.return_code == 0
        deny = await environment.exec("python -c \"import urllib.request,urllib.error; "
            "r=urllib.request.Request('http://business:8000/collect',data=b'{}'); "
            "exec('try:\\n urllib.request.urlopen(r)\\n raise AssertionError(\\\"private route exposed\\\")\\nexcept urllib.error.HTTPError as e:\\n assert e.code==404')\"")
        assert deny.return_code == 0, deny.stderr
        reject = await environment.exec("python -c \"import sys;sys.path.insert(0,'/app');from biz import call;import urllib.error;"
            "exec('try:\\n call(\\\"/respond\\\", {\\\"turn_id\\\":\\\"fake\\\",\\\"status\\\":401,\\\"body\\\":{}})\\n raise AssertionError(\\\"fake provider status accepted\\\")\\nexcept urllib.error.HTTPError as e:\\n assert e.code==409')\"")
        assert reject.return_code == 0, reject.stderr
        count = 0
        seen = set()
        while True:
            result = await environment.exec("python /app/biz.py turn", timeout_sec=20)
            assert result.return_code == 0, result.stderr
            turn = json.loads(result.stdout)
            if turn["state"] in ("finished", "error"):
                return
            if turn["state"] != "turn" or turn["turn_id"] in seen:
                await asyncio.sleep(0.1)
                continue
            seen.add(turn["turn_id"])
            # The real native policy and 19-ish public schemas must be present;
            # hidden user instructions and acceptance predicates must be absent.
            request = turn["request"]
            assert request["messages"][0]["role"] == "system"
            names = {item["function"]["name"] for item in request["tools"]}
            assert "get_clock" in names and "decide_request" not in names
            if count == 0:
                message = {"tool_calls": [{"id": "clock", "type": "function", "function": {"name": "get_clock", "arguments": "{}"}}]}
            else:
                assert any(item["role"] == "tool" and '"minute": 0' in item["content"] for item in request["messages"])
                message = {"content": "I cannot complete this payment. Goodbye."}
            count += 1
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "message.json"
                path.write_text(json.dumps(message), "utf-8")
                await environment.upload_file(path, "/app/message.json")
            result = await environment.exec("python /app/biz.py respond --turn-id " + turn["turn_id"] + " --file /app/message.json")
            if result.return_code:
                final = await environment.exec("python /app/biz.py turn", timeout_sec=20)
                assert json.loads(final.stdout)["state"] == "finished", result.stderr
                return


class OfflineRelayAgent(BizAgentBenchAgent):
    """Exercise the production host relay against a local fixture provider."""
    async def setup(self, environment):
        from http.server import ThreadingHTTPServer
        from fixtures.provider import Handler
        import threading
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.config = dict(self.config, base_url=f"http://127.0.0.1:{self.server.server_port}/v1")
        await super().setup(environment)

    async def run(self, instruction, environment, context):
        try:
            await super().run(instruction, environment, context)
        finally:
            await asyncio.to_thread(self.server.shutdown)
