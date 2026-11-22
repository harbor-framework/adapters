import asyncio
import socket
import threading
import time
import urllib.request
from types import SimpleNamespace

import uvicorn


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class RunningClinic:
    def __init__(self, mcp):
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        config = uvicorn.Config(mcp.http_app(), host="127.0.0.1", port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        for _ in range(100):
            try:
                urllib.request.urlopen(self.url + "/health", timeout=1)
                return self
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("clinic server did not start")

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(5)


class LocalEnvironment:
    def __init__(self):
        self.commands = []

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.commands.append(command)
        process = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec or 60)
        return SimpleNamespace(stdout=stdout.decode(), stderr=stderr.decode(), return_code=process.returncode)
