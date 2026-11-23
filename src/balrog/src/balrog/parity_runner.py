"""Run the pinned upstream BALROG agent against native or HTTP environments.

No Harbor task instruction, shell instruction, tool schema, or wrapper text is
sent to the model. The upstream AgentFactory, prompt builder and API client own
all model-facing behavior. This file is also runnable in the minimal agent image.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import logging
import math
import os
from pathlib import Path
import platform
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid

UPSTREAM_REVISION = "b7afe79e3e4265811cfa985ed7c95c4d1a11e3f5"
MINIGRID_REVISION = "cf73dd148e51276bd675a37e3bfb0bf2b42329b2"


def source_commits(task_id):
    env_name = (task_id or "babyai-").split("-", 1)[0]
    extras = {
        "babyai": {"minigrid": MINIGRID_REVISION},
        "babaisai": {"baba": "40ae1b29dbc67f2ecea06cc161ed5ca51719e5e3"},
        "textworld": {"textworld": "1d56f4765e7b28f04a68eff0bce5a6fe6ecd1a9f", "assets": "bcb4052e6de36a4389e666acd374832cfab1a042"},
        "crafter": {},
        "nle": {"minihack": "3ecb6da4eadcac7a4dbc5f8e801ccf636e34d7ec", "boxoban_levels": "78011d8c86ad423bfb2e1005012393b4c3c24409"},
        "minihack": {"minihack": "3ecb6da4eadcac7a4dbc5f8e801ccf636e34d7ec", "boxoban_levels": "78011d8c86ad423bfb2e1005012393b4c3c24409"},
    }
    if env_name not in extras:
        raise ValueError("Unknown task environment for provenance")
    return {"balrog": UPSTREAM_REVISION, **extras[env_name]}


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode("utf-8")).hexdigest()


def observed_hash(obs):
    serialized = encoded({"text": obs["text"], "mission": obs.get("mission")})
    # Audit-only normalization of the upstream Baba reset's object addresses.
    # Keep model-facing text untouched; game state, actions and scores are exact.
    if "[...] IS YOU rule was broken, environment reset" in obs["text"].get("long_term_context", ""):
        serialized = re.sub(
            r"(<(?:PIL\.Image\.Image image mode=[^<>]*|function BabaIsAIWrapper\.textworld_process_obsv\.<locals>\.<lambda>) at )0x[0-9a-fA-F]+(>)",
            r"\g<1>0xADDRESS\2", serialized,
        )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def runtime_versions():
    packages = {}
    for package in ("openai", "anthropic", "google-genai", "omegaconf", "tqdm"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = "not-installed"
    return {"python": platform.python_version(), "packages": packages}


def write_json(path, value):
    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(target)


def load_config(config_path, settings):
    """Apply the same nonsecret configuration on both sides, without API calls."""
    from omegaconf import OmegaConf

    allowed = {"api_base_url", "agent", "client", "limits"}
    if not isinstance(settings, dict) or set(settings) - allowed:
        raise ValueError("Unknown parity settings fields")
    allowed_agent = {"type", "remember_cot", "max_text_history", "max_image_history", "max_cot_history"}
    allowed_client = {"client_name", "model_id", "generate_kwargs", "timeout", "max_retries", "delay", "alternate_roles"}
    if set(settings.get("agent", {})) - allowed_agent or set(settings.get("client", {})) - allowed_client:
        raise ValueError("Only nonsecret agent/client settings are accepted")
    generate = settings.get("client", {}).get("generate_kwargs", {})
    if set(generate) - {"temperature", "max_tokens", "thinking_budget"}:
        raise ValueError("Unsupported upstream generation parameter")
    limits = settings.get("limits", {})
    if set(limits) - {"max_model_calls"}:
        raise ValueError("Unknown parity limit")
    if "max_model_calls" in limits and (type(limits["max_model_calls"]) is not int or limits["max_model_calls"] < 1):
        raise ValueError("max_model_calls must be a positive integer")
    url = settings.get("api_base_url")
    if not isinstance(url, str) or not url:
        raise ValueError("An explicit api_base_url is required; no endpoint is inferred")
    parsed = urlsplit(url)
    if (url != url.strip() or any(ord(char) < 32 for char in url)
            or parsed.scheme not in {"http", "https"} or not parsed.netloc
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("api_base_url must be an HTTP(S) URL without credentials, query or fragment")
    config = OmegaConf.load(config_path)
    config = OmegaConf.merge(config, {key: settings[key] for key in ("agent", "client") if key in settings})
    if config.agent.type != "naive":
        raise ValueError("This parity runner currently validates the upstream naive agent only")
    if config.agent.max_image_history != 0:
        raise ValueError("The HTTP BabyAI task supports text-only parity")
    if "model_id" not in settings.get("client", {}) or not str(config.client.model_id).strip():
        raise ValueError("An explicit model_id is required")
    if re.search(r"REPLACE[_-]|YOUR[_-]|CHANGEME|TODO|<|>", str(config.client.model_id), re.IGNORECASE):
        raise ValueError("Replace the template model_id before running parity")
    if config.client.client_name not in {"openai", "vllm", "nvidia", "xai"}:
        raise ValueError("This parity entry point currently supports OpenAI-compatible upstream clients")
    config.client.base_url = url
    # Upstream OpenAIWrapper deliberately does not pass config.client.base_url.
    # OpenAI() reads this SDK environment variable. Never infer the endpoint from
    # upstream's localhost default and never write an API key into config/logs.
    os.environ["OPENAI_BASE_URL"] = url
    return config


class HTTPEnvironment:
    """Public game protocol only; this class has no result token or scoring API."""

    def __init__(self, url):
        self.url = url.rstrip("/")

    def _request(self, endpoint, payload=None):
        body = None if payload is None else encoded(payload).encode("utf-8")
        request = Request(self.url + endpoint, data=body, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            observation = json.load(response)
        fields = {"task_id", "text", "mission", "instruction", "step", "max_steps", "done", "terminated", "truncated"}
        if not isinstance(observation, dict) or set(observation) != fields:
            raise RuntimeError("Unexpected game observation schema")
        if not isinstance(observation["text"], dict) or not isinstance(observation["instruction"], str):
            raise RuntimeError("Invalid game observation")
        if not isinstance(observation["task_id"], str) or not observation["task_id"]:
            raise RuntimeError("Missing authoritative task identity")
        for field in ("step", "max_steps"):
            if type(observation[field]) is not int:
                raise RuntimeError("Invalid game step budget")
        for field in ("done", "terminated", "truncated"):
            if type(observation[field]) is not bool:
                raise RuntimeError("Invalid game termination")
        return observation

    def observation(self):
        return self._request("/observation")

    def action(self, raw_action, expected_step):
        return self._request("/action", {"action": raw_action, "expected_step": expected_step})

    def close(self):
        pass


class RecordingClient:
    """Record the exact prompt and raw response around the original API client."""

    def __init__(self, client, output_dir, limit=None):
        self.client = client
        self.output_dir = output_dir
        self.limit = limit
        self.calls = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def generate(self, messages):
        if self.limit is not None and len(self.calls) >= self.limit:
            raise RuntimeError("Configured model-call budget exhausted")
        prompt = []
        for message in messages:
            if message.attachment is not None:
                raise RuntimeError("Unexpected image in text-only parity")
            prompt.append({"role": message.role, "content": message.content})
        record = {"call": len(self.calls), "timestamp": now(), "messages": prompt,
                  "prompt_sha256": digest(prompt)}
        if hasattr(self.client, "convert_messages"):
            record["request_messages"] = self.client.convert_messages(messages)
            record["request_prompt_sha256"] = digest(record["request_messages"])
        self.calls.append(record)
        started = time.monotonic()
        try:
            response = self.client.generate(messages)
            record.update({"raw_completion": response.completion,
                           "stop_reason": str(response.stop_reason), "reasoning": response.reasoning,
                           "input_tokens": response.input_tokens, "output_tokens": response.output_tokens})
            for field in ("input_tokens", "output_tokens"):
                if type(record[field]) is not int or record[field] < 0:
                    raise RuntimeError("Provider returned invalid token accounting")
            self.total_input_tokens += response.input_tokens
            self.total_output_tokens += response.output_tokens
            if response.stop_reason == "error_max_retries":
                raise RuntimeError("Upstream provider exhausted its retries")
            if not isinstance(response.completion, str):
                raise RuntimeError("Provider returned a nontext completion")
            return response
        except Exception as exc:
            # Provider exception text may contain sensitive request information.
            record["error_type"] = type(exc).__name__
            raise
        finally:
            record["elapsed_seconds"] = time.monotonic() - started
            write_json(self.output_dir / "model_calls.json", self.calls)


def run_episode(agent, environment, output_dir, config_metadata, *, mode, max_model_calls=None, session_id=None, task_id=None):
    if mode != "http":
        raise ValueError("Native runs must use run_original_episode")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    session_id = session_id or str(uuid.uuid4())
    recorder = RecordingClient(agent.client, output_dir, max_model_calls)
    agent.client = recorder
    started = time.monotonic()
    summary = {"status": "running", "mode": mode, "session_id": session_id,
               "upstream_revision": UPSTREAM_REVISION, "settings": config_metadata,
               "settings_sha256": digest(config_metadata),
               "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "source_commits": source_commits(task_id),
               "runtime_versions": runtime_versions(), "task_id": task_id,
               "steps": 0, "model_calls": 0, "input_tokens": 0, "output_tokens": 0}
    trajectory = {"schema_version": "ATIF-v1.7", "session_id": session_id,
                  "agent": {"name": "balrog-" + config_metadata["agent"]["type"],
                            "version": UPSTREAM_REVISION,
                            "model_name": config_metadata["client"]["model_id"]},
                  "steps": [], "notes": "Upstream BALROG prompts and agent. Actions are environment dispatches, not model tool calls."}

    def checkpoint():
        summary.update(model_calls=len(recorder.calls), input_tokens=recorder.total_input_tokens,
                       output_tokens=recorder.total_output_tokens,
                       elapsed_seconds=time.monotonic() - started)
        trajectory["final_metrics"] = {"total_prompt_tokens": recorder.total_input_tokens,
                                       "total_completion_tokens": recorder.total_output_tokens,
                                       "total_steps": len(trajectory["steps"])}
        trajectory["extra"] = {"status": summary["status"], "mode": mode,
                               "elapsed_seconds": summary["elapsed_seconds"]}
        write_json(output_dir / "episode_result.json", summary)
        if trajectory["steps"]:
            write_json(output_dir / "trajectory.json", trajectory)

    try:
        obs = environment.observation()
        if task_id is not None and task_id != obs["task_id"]:
            raise ValueError("Requested task identity differs from the game service")
        task_id = obs["task_id"]
        summary.update(task_id=task_id, source_commits=source_commits(task_id))
        if obs["step"] != 0 or obs["done"]:
            raise RuntimeError("Parity must start from an unused, live episode")
        summary["initial_observation_sha256"] = observed_hash(obs)
        agent.reset()
        agent.prompt_builder.update_instruction_prompt(obs["instruction"])
        trajectory["steps"].append({"step_id": 1, "timestamp": now(), "source": "user",
                                    "message": obs["instruction"],
                                    "extra": {"initial_observation": obs, "observation_sha256": observed_hash(obs)}})
        prev_action = None
        while not obs["done"]:
            if obs["step"] >= obs["max_steps"]:
                raise RuntimeError("Environment did not stop at its native step budget")
            # The upstream agent only receives native text/image observations.
            # Image history is zero, so omitting the image is prompt-equivalent.
            response = agent.act({"text": obs["text"], "mission": obs["mission"]}, prev_action=prev_action)
            if not isinstance(response.completion, str):
                raise RuntimeError("Upstream agent returned a nontext action")
            record = recorder.calls[-1]
            record["parsed_action"] = response.completion
            record["observation_sha256"] = observed_hash(obs)
            previous_step = obs["step"]
            action_step = {"step_id": len(trajectory["steps"]) + 1, "timestamp": record["timestamp"],
                           "source": "agent", "message": record["raw_completion"], "llm_call_count": 1,
                           "metrics": {"prompt_tokens": response.input_tokens, "completion_tokens": response.output_tokens},
                           "extra": {"parsed_action": response.completion, "prompt_sha256": record["prompt_sha256"],
                                     "elapsed_seconds": record["elapsed_seconds"]}}
            if record["reasoning"] is not None:
                action_step["reasoning_content"] = str(record["reasoning"])
            trajectory["steps"].append(action_step)
            # Retain the native agent's output as prev_action even if invalid;
            # native Evaluator.run_episode does NOT remember the fallback action.
            prev_action = response.completion
            obs = environment.action(response.completion, previous_step)
            if obs["step"] != previous_step + 1:
                raise RuntimeError("Environment action did not advance exactly one step")
            action_step["observation"] = {"results": [{"content": encoded(obs)}]}
            summary["steps"] = obs["step"]
            record["next_observation_sha256"] = observed_hash(obs)
            write_json(output_dir / "model_calls.json", recorder.calls)
            checkpoint()
        summary.update(status="completed", terminated=obs["terminated"], truncated=obs["truncated"],
                       max_steps=obs["max_steps"])
        return summary
    except Exception as exc:
        summary.update(status="error", error_type=type(exc).__name__)
        raise
    finally:
        checkpoint()
        environment.close()


def run_original_episode(agent, config, manifest, output_dir, config_metadata, *, max_model_calls=None, session_id=None):
    """Call the unmodified upstream Evaluator.run_episode; wrappers only record.

    The module's environment factory is scoped to a transparent recorder so the
    original evaluator remains solely responsible for reset/seed, action
    validation, stepping, invalid-action feedback, stopping and native scoring.
    Run one episode per process; this scoped factory instrumentation is not
    intended for concurrent threads.
    """
    import balrog.evaluator as evaluator_module

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = copy.deepcopy(config)
    if type(manifest["seed"]) is not int or not 0 <= manifest["seed"] < 2**32:
        raise ValueError("Frozen episode seed must be uint32")
    config.envs.env_kwargs.seed = manifest["seed"]
    env_name = manifest.get("env_name", "babyai")
    if env_name not in {"babyai", "babaisai", "textworld", "crafter", "nle", "minihack"}:
        raise ValueError("Unknown BALROG environment")
    if manifest["task"] not in config.tasks[f"{env_name}_tasks"]:
        raise ValueError("Unknown task in pinned BALROG configuration")
    kwargs_key = f"{env_name}_kwargs"
    if kwargs_key in manifest:
        config.envs[kwargs_key] = manifest[kwargs_key]
    if config.eval.max_steps_per_episode is not None:
        raise ValueError("Parity uses the native environment step budget")
    session_id = session_id or str(uuid.uuid4())
    recorder = RecordingClient(agent.client, output_dir, max_model_calls)
    agent.client = recorder
    started = time.monotonic()
    summary = {"status": "running", "mode": "native", "session_id": session_id,
               "upstream_revision": UPSTREAM_REVISION, "settings": config_metadata,
               "settings_sha256": digest(config_metadata),
               "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "source_commits": source_commits(manifest["task_id"]),
               "runtime_versions": runtime_versions(),
               **{key: manifest[key] for key in ("task_id", "task", "seed")},
               "steps": 0, "model_calls": 0, "input_tokens": 0, "output_tokens": 0}
    trajectory = {"schema_version": "ATIF-v1.7", "session_id": session_id,
                  "agent": {"name": "balrog-" + config_metadata["agent"]["type"],
                            "version": UPSTREAM_REVISION,
                            "model_name": config_metadata["client"]["model_id"]},
                  "steps": [], "notes": "Unmodified upstream Evaluator.run_episode; transparent recorders only."}
    environment = None

    def checkpoint():
        summary.update(model_calls=len(recorder.calls), input_tokens=recorder.total_input_tokens,
                       output_tokens=recorder.total_output_tokens,
                       elapsed_seconds=time.monotonic() - started)
        trajectory["final_metrics"] = {"total_prompt_tokens": recorder.total_input_tokens,
                                       "total_completion_tokens": recorder.total_output_tokens,
                                       "total_steps": len(trajectory["steps"])}
        trajectory["extra"] = {"status": summary["status"], "mode": "native",
                               "elapsed_seconds": summary["elapsed_seconds"]}
        write_json(output_dir / "episode_result.json", summary)
        write_json(output_dir / "model_calls.json", recorder.calls)
        if trajectory["steps"]:
            write_json(output_dir / "trajectory.json", trajectory)

    class EnvironmentRecorder:
        def __init__(self, original):
            self.original = original
            self.obs = None
            self.steps = 0
            self.terminated = self.truncated = False
            self.instruction = None

        def __getattr__(self, name):
            return getattr(self.original, name)

        def reset(self, **kwargs):
            self.obs, info = self.original.reset(**kwargs)
            actual = {"expected_mission": self.obs.get("mission"),
                      "expected_initial_observation_sha256": observed_hash(self.obs),
                      "expected_max_steps": int(self.original.max_steps)}
            for key, value in actual.items():
                if key in manifest and manifest[key] != value:
                    raise ValueError("Original environment differs from manifest: " + key)
            summary["initial_observation_sha256"] = observed_hash(self.obs)
            return self.obs, info

        def view(self):
            # Record the same public fields as HTTP, without feeding this view
            # back to the native evaluator or agent.
            truncated = self.truncated or (self.steps >= self.max_steps and not self.terminated)
            return {"task_id": manifest["task_id"], "text": copy.deepcopy(self.obs["text"]), "mission": self.obs.get("mission"),
                    "instruction": self.instruction, "step": self.steps, "max_steps": int(self.max_steps),
                    "done": self.terminated or truncated, "terminated": self.terminated, "truncated": truncated}

        def get_instruction_prompt(self, **kwargs):
            self.instruction = self.original.get_instruction_prompt(**kwargs)
            trajectory["steps"].append({"step_id": 1, "timestamp": now(), "source": "user",
                                        "message": self.instruction,
                                        "extra": {"initial_observation": self.view(),
                                                  "observation_sha256": observed_hash(self.obs)}})
            return self.instruction

        def step(self, action):
            result = self.original.step(action)
            self.obs, _, terminated, truncated, _ = result
            self.steps += 1
            self.terminated, self.truncated = bool(terminated), bool(truncated)
            summary["steps"] = self.steps
            return result

    def finish_previous_observation():
        if environment is not None and environment.steps and trajectory["steps"][-1]["source"] == "agent":
            recorder.calls[-1]["next_observation_sha256"] = observed_hash(environment.obs)
            trajectory["steps"][-1]["observation"] = {"results": [{"content": encoded(environment.view())}]}

    class AgentRecorder:
        def __getattr__(self, name):
            return getattr(agent, name)

        def act(self, obs, prev_action=None):
            # Feedback has now been added by the original evaluator to the
            # previous step's observation, so capture it without reproducing it.
            finish_previous_observation()
            response = agent.act(obs, prev_action=prev_action)
            record = recorder.calls[-1]
            record.update(parsed_action=response.completion, observation_sha256=observed_hash(obs))
            action_step = {"step_id": len(trajectory["steps"]) + 1, "timestamp": record["timestamp"],
                           "source": "agent", "message": record["raw_completion"], "llm_call_count": 1,
                           "metrics": {"prompt_tokens": response.input_tokens, "completion_tokens": response.output_tokens},
                           "extra": {"parsed_action": response.completion, "prompt_sha256": record["prompt_sha256"],
                                     "elapsed_seconds": record["elapsed_seconds"]}}
            if record["reasoning"] is not None:
                action_step["reasoning_content"] = str(record["reasoning"])
            trajectory["steps"].append(action_step)
            checkpoint()
            return response

    original_factory = evaluator_module.make_env

    def recording_factory(*args, **kwargs):
        nonlocal environment
        if environment is not None:
            raise RuntimeError("Original evaluator unexpectedly created multiple environments")
        environment = EnvironmentRecorder(original_factory(*args, **kwargs))
        return environment

    evaluator_module.make_env = recording_factory
    try:
        evaluator = evaluator_module.Evaluator(env_name, config, output_dir=str(output_dir / "original"))
        original_result = evaluator.run_episode(manifest["task"], AgentRecorder(), episode_idx=0)
        finish_previous_observation()
        score = float(original_result["progression"])
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise RuntimeError("Invalid original progression")
        if original_result["num_steps"] != environment.steps:
            raise RuntimeError("Original evaluator step accounting differs")
        observation = environment.view()
        summary.update(status="completed", native_progression=score,
                       terminated=observation["terminated"], truncated=observation["truncated"],
                       max_steps=observation["max_steps"])
        write_json(output_dir / "original_episode_result.json", original_result)
        return summary
    except Exception as exc:
        summary.update(status="error", error_type=type(exc).__name__)
        raise
    finally:
        evaluator_module.make_env = original_factory
        checkpoint()
        if environment is not None:
            environment.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("native", "http"), required=True)
    parser.add_argument("--config", type=Path, default=Path("/opt/balrog/balrog/config/config.yaml"))
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--episode", type=Path)
    parser.add_argument("--server", default="http://game:8080")
    parser.add_argument("--session-id")
    parser.add_argument("--task-id")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Keep SDK errors out of stderr; our error records contain exception classes.
    logging.getLogger("balrog.client").disabled = True
    try:
        settings = json.loads(args.settings.read_text(encoding="utf-8"))
        config = load_config(args.config, settings)
        from balrog.agents import AgentFactory
        from omegaconf import OmegaConf

        agent = AgentFactory(config).create_agent()
        metadata = {"agent": OmegaConf.to_container(config.agent, resolve=True),
                    "client": OmegaConf.to_container(config.client, resolve=True),
                    "api_base_url": settings["api_base_url"], "limits": settings.get("limits", {})}
        if args.mode == "native":
            if args.episode is None:
                raise ValueError("Native mode requires an explicit frozen episode manifest")
            result = run_original_episode(agent, config, json.loads(args.episode.read_text(encoding="utf-8")),
                                          args.output_dir, metadata,
                                          max_model_calls=settings.get("limits", {}).get("max_model_calls"),
                                          session_id=args.session_id)
        else:
            if args.episode is not None:
                raise ValueError("HTTP mode must not receive a private episode manifest")
            result = run_episode(agent, HTTPEnvironment(args.server), args.output_dir, metadata, mode="http",
                                 max_model_calls=settings.get("limits", {}).get("max_model_calls"),
                                 session_id=args.session_id, task_id=args.task_id)
        print(encoded({key: result[key] for key in ("status", "steps", "model_calls", "input_tokens", "output_tokens")}))
        return 0
    except Exception as exc:
        write_json(args.output_dir / "error.json", {"status": "error", "error_type": type(exc).__name__,
                                                   "message": "Parity runner failed; no score is certified.", "timestamp": now()})
        print("Parity runner failed: " + type(exc).__name__, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
