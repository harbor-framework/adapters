"""Keep a single frozen BALROG episode outside the agent container.

The service exposes observations and actions only. Verifier-only result access
freezes the episode and independently replays its recorded actions before scoring.
Crafter's upstream object-identity ordering can make fresh replays diverge; that
case retains the authoritative native score and explicitly reports the divergence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import random
import re
import threading
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
from omegaconf import OmegaConf
from balrog.environments import make_env


class ReplayDivergence(RuntimeError):
    def __init__(self, message, step):
        super().__init__(message)
        self.step = step


def observation_hash(observation: dict) -> str:
    visible = {"text": observation["text"], "mission": observation.get("mission")}
    serialized = json.dumps(visible, sort_keys=True)
    # The native Baba reset message embeds Python object reprs. Addresses vary
    # across independent replays; ignore only these two known repr addresses in
    # audit hashes. The actual observation/model prompt is never modified.
    if "[...] IS YOU rule was broken, environment reset" in observation["text"].get("long_term_context", ""):
        serialized = re.sub(
            r"(<(?:PIL\.Image\.Image image mode=[^<>]*|function BabaIsAIWrapper\.textworld_process_obsv\.<locals>\.<lambda>) at )0x[0-9a-fA-F]+(>)",
            r"\g<1>0xADDRESS\2", serialized,
        )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class Episode:
    def __init__(self, episode: dict, config_path: Path):
        self.task = episode["task"]
        self.seed = episode["seed"]
        self.env_name = episode.get("env_name", "babyai")
        if self.env_name not in {"babyai", "babaisai", "textworld", "crafter", "nle", "minihack"}:
            raise ValueError("Unsupported BALROG environment")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("seed must be a uint32 integer")
        self.task_id = episode.get("task_id", f"{self.task}/seed-{self.seed}")
        self.config = OmegaConf.load(config_path)
        if self.task not in self.config.tasks[f"{self.env_name}_tasks"]:
            raise ValueError("Unsupported task in pinned BALROG configuration")
        kwargs_key = f"{self.env_name}_kwargs"
        if kwargs_key in episode:
            self.config.envs[kwargs_key] = episode[kwargs_key]
        # TextWorld selects its game at construction time using this seed.
        self.config.envs.env_kwargs.seed = self.seed
        self.feedback = bool(self.config.eval.feedback_on_invalid_action)
        self.env, self.observation = self._new_environment()
        try:
            self.initial_hash = observation_hash(self.observation)
            self.mission = self.observation.get("mission")
            self.instruction = self.env.get_instruction_prompt(instructions=self.mission)
            self.max_steps = int(self.env.max_steps)
            for key, actual, label in (
                ("expected_mission", self.mission, "mission"),
                ("expected_initial_observation_sha256", self.initial_hash, "initial observation"),
                ("expected_max_steps", self.max_steps, "step budget"),
            ):
                if key in episode and episode[key] != actual:
                    raise ValueError(f"Environment {label} differs from frozen manifest")
        except Exception:
            self.env.close()
            raise
        self.transitions: list[dict] = []
        self.terminated = False
        self.truncated = False
        self.finalized = False
        self._result = None
        self._failure = None
        self.lock = threading.RLock()

    def _new_environment(self):
        random.seed(self.seed)
        np.random.seed(self.seed)
        env = make_env(self.env_name, self.task, self.config)
        try:
            # Evaluator.run_episode seeds global RNGs AFTER make_env and just
            # before reset. Boxoban samples in both construction and reset;
            # relying only on the construction seed selects a different level.
            random.seed(self.seed)
            np.random.seed(self.seed)
            observation, _ = env.reset(seed=self.seed)
        except Exception:
            env.close()
            raise
        return env, observation

    def public_observation(self) -> dict:
        with self.lock:
            return {
                "task_id": self.task_id,
                "step": len(self.transitions),
                "max_steps": self.max_steps,
                "done": self.terminated or self.truncated or self.finalized,
                "terminated": self.terminated,
                "truncated": self.truncated,
                "mission": self.mission,
                "instruction": self.instruction,
                "text": copy.deepcopy(self.observation["text"]),
            }

    def _advance(self, env, raw_action: str, step_index: int):
        executed = env.check_action_validity(raw_action)
        observation, reward, terminated, truncated, _ = env.step(executed)
        if executed != raw_action and self.feedback:
            observation["text"]["long_term_context"] = (
                f"\n\nYour previous output did not contain a valid action. Defaulted to action: {executed}\n\nObservation:\n"
                + observation["text"]["long_term_context"]
            )
        # The native evaluator also stops once env.max_steps is reached.
        budget_exhausted = step_index + 1 >= self.max_steps
        transition = {
            "step": step_index,
            "raw_action": raw_action,
            "executed_action": executed,
            "observation_sha256": observation_hash(observation),
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "budget_exhausted": budget_exhausted,
        }
        return observation, transition

    def action(self, raw_action: str, expected_step: int) -> dict:
        with self.lock:
            if self._failure is not None:
                raise RuntimeError("Episode failed; no further actions are accepted")
            if self.finalized or self.terminated or self.truncated:
                raise ValueError("Episode is finished")
            if expected_step != len(self.transitions):
                raise ValueError("Stale expected_step; read the current observation")
            try:
                observation, transition = self._advance(self.env, raw_action, len(self.transitions))
            except Exception as exc:
                self._failure = type(exc).__name__
                self.finalized = True
                raise
            self.observation = observation
            self.transitions.append(transition)
            self.terminated = transition["terminated"]
            self.truncated = transition["truncated"] or (
                transition["budget_exhausted"] and not self.terminated
            )
            return self.public_observation()

    def result(self) -> dict:
        with self.lock:
            self.finalized = True
            if self._failure is not None:
                raise RuntimeError("Episode failed; cannot produce a benchmark score")
            if self._result is not None:
                return copy.deepcopy(self._result)
            replay_env = None
            progression = self._native_progression(self.env)
            if not math.isfinite(progression) or not 0 <= progression <= 1:
                raise RuntimeError("Invalid native progression")
            replay_diagnostic = None
            try:
                replay_env, replay_observation = self._new_environment()
                if observation_hash(replay_observation) != self.initial_hash:
                    raise RuntimeError("Initial observation differs on replay")
                replay_terminated = replay_truncated = False
                for expected in self.transitions:
                    if replay_terminated or replay_truncated:
                        raise ReplayDivergence("Fresh native replay ended earlier", expected["step"])
                    replay_observation, actual = self._advance(
                        replay_env, expected["raw_action"], expected["step"]
                    )
                    if actual != expected:
                        raise ReplayDivergence(f"Replay differs at step {expected['step']}", expected["step"])
                    replay_terminated = actual["terminated"]
                    replay_truncated = actual["truncated"] or (
                        actual["budget_exhausted"] and not replay_terminated
                    )
                replay_progression = self._native_progression(replay_env)
                if not math.isfinite(replay_progression) or not 0 <= replay_progression <= 1:
                    raise RuntimeError("Invalid replay progression")
                if progression != replay_progression:
                    raise ReplayDivergence("Replay progression differs", len(self.transitions))
                if (replay_terminated, replay_truncated) != (self.terminated, self.truncated):
                    raise ReplayDivergence("Replay termination differs", len(self.transitions))
            except ReplayDivergence as exc:
                if self.env_name != "crafter":
                    self._failure = type(exc).__name__
                    raise
                # Never alter the original game, sort its identity-hashed object
                # sets, or use the fresh replay's score. The agent cannot mutate
                # this separate service's state or access the protected result.
                replay_progression = None
                replay_diagnostic = {
                    "code": "crafter_native_object_order_nondeterminism",
                    "first_divergent_step": exc.step,
                    "message": str(exc),
                }
            except Exception as exc:
                self._failure = type(exc).__name__
                raise
            finally:
                if replay_env is not None:
                    replay_env.close()
            self._result = {
                    "schema_version": 1,
                    "env_name": self.env_name,
                    "task_id": self.task_id,
                    "task": self.task,
                    "seed": self.seed,
                    "progression": progression,
                    "replay_progression": replay_progression,
                    "replay_verified": replay_diagnostic is None,
                    "scoring_mode": "authoritative_native_state" if replay_diagnostic else "deterministic_replay",
                    "replay_diagnostic": replay_diagnostic,
                    "finalized": True,
                    "terminated": self.terminated,
                    "truncated": self.truncated,
                    "steps": len(self.transitions),
                    "max_steps": self.max_steps,
                    "initial_observation_sha256": self.initial_hash,
                    "transitions": copy.deepcopy(self.transitions),
                }
            return copy.deepcopy(self._result)

    def _native_progression(self, env):
        stats = env.get_stats()
        if "progression" not in stats and self.env_name == "minihack" and not self.transitions:
            # Pinned BaseProgress declares initial values as class attributes,
            # while get_stats returns only __dict__. Before the first action it
            # therefore returns {}. Read the actual native object's initial
            # value rather than inventing a score or taking an extra action.
            from balrog.environments.nle.progress import BaseProgress
            progress = env.env.gym_env.env.progress
            if not isinstance(progress, BaseProgress):
                raise RuntimeError("Unexpected MiniHack progress object")
            return float(progress.progression)
        return float(stats["progression"])

    def close(self):
        self.env.close()


def build_server(episode: Episode, token: str, address):
    if not token:
        raise ValueError("RESULT_TOKEN must be configured")

    class Handler(BaseHTTPRequestHandler):
        def json_response(self, status, value):
            body = json.dumps(value, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self.json_response(200, {"ok": True})
            elif self.path == "/observation":
                self.json_response(200, episode.public_observation())
            elif self.path == "/result":
                supplied = self.headers.get("Authorization", "")
                if not hmac.compare_digest(supplied, "Bearer " + token):
                    self.json_response(401, {"error": "unauthorized"})
                    return
                try:
                    self.json_response(200, episode.result())
                except Exception:
                    traceback.print_exc()
                    self.json_response(500, {"error": "Environment or replay verification failed"})
            else:
                self.json_response(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/action":
                self.json_response(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024 * 1024:
                    raise ValueError("Request must contain at most 1048576 bytes")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or set(data) != {"action", "expected_step"}:
                    raise ValueError("Expected action and expected_step fields")
                action, expected_step = data["action"], data["expected_step"]
                if not isinstance(action, str) or len(action) > 262144:
                    raise ValueError("action must be a string of at most 262144 characters")
                if type(expected_step) is not int or expected_step < 0:
                    raise ValueError("expected_step must be a nonnegative integer")
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self.json_response(400, {"error": str(exc)})
                return
            try:
                self.json_response(200, episode.action(action, expected_step))
            except ValueError as exc:
                self.json_response(409, {"error": str(exc)})
            except Exception:
                traceback.print_exc()
                self.json_response(500, {"error": "Environment step failed"})

        def log_message(self, *_):
            # Avoid placing authorization material in request logs.
            pass

    return ThreadingHTTPServer(address, Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, default=Path("/app/episode.json"))
    parser.add_argument("--config", type=Path, default=Path("/opt/balrog/balrog/config/config.yaml"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    episode = Episode(json.loads(args.episode.read_text(encoding="utf-8")), args.config)
    server = build_server(episode, os.environ.get("RESULT_TOKEN", ""), (args.host, args.port))
    print(f"BabyAI game service ready on port {args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        episode.close()


if __name__ == "__main__":
    main()
