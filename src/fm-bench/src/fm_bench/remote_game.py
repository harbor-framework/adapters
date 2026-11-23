"""RemoteGame: the Game surface the original FM-Bench runner needs, served by
the task's game sidecar instead of an in-process engine.

runner.llm_agent.LLMAgent touches its game object through exactly four
methods: start, advance, call_tool and final_result. RemoteGame implements
those over a transport `rpc(name, args) -> envelope`, so the unmodified
LLMAgent can play a Harbor task. That is what makes parity a claim about
transport only: prompts, tool schemas, turn limits, retries and memory handling
are the original code on both sides.

No Harbor import here, so this module can be tested without Harbor installed.
"""

from __future__ import annotations

from typing import Callable

Rpc = Callable[[str, dict], dict]


class _WorldView:
    """The one attribute LLMAgent reads from game.world: the id of the current
    stop, which it stamps on its log records. The model never sees it."""

    current_stop_id: str | None = None


class RemoteGame:
    def __init__(self, rpc: Rpc, validation_error: type[Exception]):
        self._rpc = rpc
        # engine.actions.validate.ValidationError, passed in so this module
        # does not import the engine; LLMAgent.play catches exactly this type
        self._validation_error = validation_error
        self._packet: dict | None = None
        self.world = _WorldView()

    def start(self) -> dict:
        self._packet = self._rpc("packet", {})
        self.world.current_stop_id = self._packet.get("stop_id")
        return self._packet

    def call_tool(self, name: str, args: dict | None = None) -> dict:
        return self._rpc(name, dict(args or {}))

    def advance(self) -> dict:
        env = self._rpc("advance", {})
        if not env.get("ok"):
            err = env.get("error") or {}
            # the in-process Game raises here (e.g. draft_pending); mirror it
            raise self._validation_error(err.get("code", "advance_refused"),
                                         err.get("hint", "advance refused"))
        self._packet = env["data"]
        # the engine sets world.current_stop_id to the id it puts in the packet
        self.world.current_stop_id = self._packet.get("stop_id")
        return self._packet

    def final_result(self) -> dict:
        """The result as far as the agent can know it. A finished game carries
        its result in the last packet. An unfinished one (spend cap, crash) is
        settled later by the verifier, as abandoned, exactly as the original
        runner's final_result() would settle it."""
        if self._packet and self._packet.get("game_over"):
            return dict(self._packet["result"])
        return {"settle_reason": "unfinished", "s_final": None}
