"""A separate Inspect process avoids nested Rich displays and global eval state."""

import asyncio
import json
import os
import signal
import sys


async def run_worker(request, logs_dir, api_key=None):
    env = os.environ.copy()
    if api_key is not None:
        env["CHESS_PUZZLES_WORKER_KEY"] = api_key
        request["api_key_name"] = "CHESS_PUZZLES_WORKER_KEY"
    logs_dir.mkdir(parents=True, exist_ok=True)
    result_path = logs_dir / "submitted.json"
    result_path.unlink(missing_ok=True)
    request["result_path"] = str(result_path.resolve())
    with (
        (logs_dir / "inspect-worker.stdout").open("wb") as out,
        (logs_dir / "inspect-worker.stderr").open("wb") as err,
    ):
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "chess_puzzles.worker",
            stdin=asyncio.subprocess.PIPE,
            stdout=out,
            stderr=err,
            env=env,
            start_new_session=True,
        )
        try:
            await process.communicate(json.dumps(request).encode())
        except BaseException:
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
            raise
    if process.returncode != 0:
        raise RuntimeError(
            f"Inspect worker exited {process.returncode}; see inspect-worker.stderr"
        )
    return json.loads(result_path.read_text())
