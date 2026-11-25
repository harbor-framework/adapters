"""Harbor custom agent wrapper for AndroidWorld's T3A (Text-only Autonomous Agent)."""

from __future__ import annotations

import asyncio
import json
import shlex
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from harbor.agents.agent_auth_resolution import ModelConnectionSpec, ProviderAccess
from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.agents.options import AgentOptions
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.model_api_format import ModelApiFormat

from androidworld.agents.llm import ERROR_CALLING_LLM, LlmPrediction, T3ALlmClient
from androidworld.agents.t3a_core import (
    DEFAULT_MAX_RETRY,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    JSONAction,
    TRIGGER_SAFETY_CLASSIFIER,
    action_selection_prompt,
    allocate_step_budget,
    extract_json,
    parse_reason_action_output,
    summarize_prompt,
)
from androidworld.agents.trajectory import T3AActionObservation, T3ATrajectoryRecorder

CONTAINER_BRIDGE_ROOT = "/tmp/harbor-t3a-agent"
CONTAINER_BRIDGE_PATH = f"{CONTAINER_BRIDGE_ROOT}/env_bridge.py"
CONTAINER_IMAGES_DIR = "/logs/agent/images"
DEFAULT_BRIDGE_PORT = 5001


class T3AAgentOptions(AgentOptions):
    """User-facing kwargs accepted by ``T3AAgent``."""

    temperature: float = Field(
        default=DEFAULT_TEMPERATURE,
        description="LLM sampling temperature (upstream T3A default: 0.0).",
    )
    max_tokens: int = Field(
        default=DEFAULT_MAX_TOKENS,
        description="Max completion tokens per LLM call (upstream default: 1000).",
    )
    max_steps: int | None = Field(
        default=None,
        description=(
            "Override turn limit; when omitted, uses upstream "
            "int(10 * task.complexity)."
        ),
    )
    transition_pause: float | None = Field(
        default=None,
        description=(
            "Seconds to wait before grabbing post-action state, or None to "
            "wait_to_stabilize (upstream run.py default for android_world)."
        ),
    )
    api_format: Literal["auto", "openai", "anthropic"] = Field(
        default="auto",
        description="Endpoint protocol (auto, openai, or anthropic).",
    )
    max_retry: int = Field(
        default=DEFAULT_MAX_RETRY,
        description="Max retries per LLM HTTP call (upstream default: 3).",
    )
    bridge_port: int = Field(
        default=DEFAULT_BRIDGE_PORT,
        description="Localhost port inside the container for the env bridge.",
    )
    go_home_on_reset: bool = Field(
        default=True,
        description="Press Home before starting the episode (matches TaskEval.start_on_home_screen).",
    )


class T3AAgent(BaseAgent):
    """Harbor custom agent executing upstream AndroidWorld T3A."""

    MODEL_CONNECTION = ModelConnectionSpec(
        base_url_destination_names={"default": None},
        agent_provider_access=ProviderAccess(
            api_key_candidate_names=["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
            base_url_candidate_names=[
                "OPENAI_BASE_URL",
                "OPENAI_API_BASE",
                "ANTHROPIC_BASE_URL",
                "ANTHROPIC_API_BASE",
            ],
        ),
        supported_api_formats=[
            ModelApiFormat.OPENAI_CHAT_COMPLETIONS,
            ModelApiFormat.ANTHROPIC_MESSAGES,
        ],
    )
    capabilities = AgentCapabilities(
        base_url=True,
        atif=True,
    )
    options_model = T3AAgentOptions
    options: T3AAgentOptions

    def __init__(
        self,
        *args: Any,
        additional_guidelines: list[str] | None = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.additional_guidelines = additional_guidelines
        self.history: list[dict[str, Any]] = []

    @staticmethod
    def name() -> str:
        return "t3a-agent"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        await self._exec_checked(
            environment,
            f"rm -rf {shlex.quote(CONTAINER_BRIDGE_ROOT)} && "
            f"mkdir -p {shlex.quote(CONTAINER_BRIDGE_ROOT)} "
            f"{shlex.quote(CONTAINER_IMAGES_DIR)}",
        )
        bridge_src = Path(__file__).with_name("env_bridge.py")
        await environment.upload_file(
            source_path=bridge_src,
            target_path=CONTAINER_BRIDGE_PATH,
        )
        await self._exec_checked(
            environment,
            "/opt/aw/boot.sh || true; python3 /opt/aw/client.py wait",
            timeout_sec=1500,
        )
        port = int(self.options.bridge_port)
        start_cmd = (
            f"if ! python3 {shlex.quote(CONTAINER_BRIDGE_PATH)} call "
            f"--port {port} --method GET --endpoint /health >/dev/null 2>&1; then "
            f"mkdir -p /logs/aw && "
            f"nohup python3 {shlex.quote(CONTAINER_BRIDGE_PATH)} serve --port {port} "
            "> /logs/aw/t3a_bridge.log 2>&1 & "
            "for i in $(seq 1 30); do "
            f"python3 {shlex.quote(CONTAINER_BRIDGE_PATH)} call "
            f"--port {port} --method GET --endpoint /health >/dev/null 2>&1 && break; "
            "sleep 1; "
            "done; "
            "fi; "
            f"python3 {shlex.quote(CONTAINER_BRIDGE_PATH)} call "
            f"--port {port} --method GET --endpoint /health"
        )
        await self._exec_checked(environment, start_cmd, timeout_sec=120)

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        self.history = []
        llm = self._create_llm_client()
        reset_resp = await self._bridge_call(
            environment,
            "/reset",
            {"go_home": self.options.go_home_on_reset},
            timeout_sec=120,
        )
        task_spec = reset_resp.get("task_spec") or {}
        goal = str(task_spec.get("goal") or instruction)
        max_steps = self._resolve_max_steps(task_spec)

        recorder = T3ATrajectoryRecorder(
            logs_dir=self.logs_dir,
            agent_name=self.name(),
            agent_version=self.version() or "0.1.0",
            model_name=self.model_name,
            instruction=goal,
            extra={
                "task_name": task_spec.get("name"),
                "seed": task_spec.get("seed"),
                "max_steps": max_steps,
                "temperature": self.options.temperature,
                "max_tokens": self.options.max_tokens,
            },
        )

        for step_idx in range(max_steps):
            step_num = step_idx + 1
            state_resp = await self._bridge_call(
                environment,
                "/state",
                {
                    "transition_pause": self.options.transition_pause,
                    "save_screenshot_path": f"{CONTAINER_IMAGES_DIR}/step_{step_num:03d}_before.png",
                },
                timeout_sec=120,
            )
            before_element_list = str(state_resp.get("ui_elements_description") or "")
            num_ui_elements = int(state_resp.get("num_ui_elements") or 0)

            history_lines = [
                f"Step {i + 1}: {item['summary']}"
                for i, item in enumerate(self.history)
            ]
            action_prompt = action_selection_prompt(
                goal,
                history_lines,
                before_element_list,
                self.additional_guidelines,
            )
            pred = await asyncio.to_thread(llm.predict_with_usage, action_prompt)
            action_output = pred.text
            is_safe = pred.is_safe
            raw_response = pred.raw_response

            if is_safe is False:
                action_output = (
                    f"Reason: {TRIGGER_SAFETY_CLASSIFIER}\n"
                    'Action: {"action_type": "status", "goal_status": "infeasible"}'
                )

            if not raw_response:
                recorder.write(context)
                raise RuntimeError("Error calling LLM in action selection phase.")

            step_data: dict[str, Any] = {
                "action_prompt": action_prompt,
                "action_output": action_output,
                "action_raw_response": raw_response,
                "summary_prompt": None,
                "summary": None,
                "summary_raw_response": None,
            }

            reason, action = parse_reason_action_output(action_output)
            if (not reason) or (not action):
                step_data["summary"] = (
                    "Output for action selection is not in the correct format, "
                    "so no action is performed."
                )
                self.history.append(step_data)
                recorder.record_turn(
                    response=action_output,
                    action_obs=None,
                    prompt_tokens=pred.prompt_tokens,
                    completion_tokens=pred.completion_tokens,
                    cost_usd=pred.cost_usd,
                    llm_call_count=1,
                    summary=step_data["summary"],
                )
                recorder.populate_context(context)
                continue

            try:
                extracted = extract_json(action)
                if extracted is None:
                    raise ValueError("No JSON object found in action output")
                converted_action = JSONAction(**extracted)
            except Exception as exc:  # noqa: BLE001
                step_data["summary"] = (
                    "Can not parse the output to a valid action. Please make sure "
                    "to pick the action from the list with the correct json format!"
                )
                self.history.append(step_data)
                recorder.record_turn(
                    response=action_output,
                    action_obs=None,
                    prompt_tokens=pred.prompt_tokens,
                    completion_tokens=pred.completion_tokens,
                    cost_usd=pred.cost_usd,
                    llm_call_count=1,
                    summary=f"{step_data['summary']} ({exc})",
                )
                recorder.populate_context(context)
                continue

            # Preserve exact upstream t3a.py index check.
            if converted_action.action_type in ["click", "long-press", "input-text"]:
                if (
                    converted_action.index is not None
                    and converted_action.index >= num_ui_elements
                ):
                    step_data["summary"] = (
                        "The parameter index is out of range. Remember the index "
                        "must be in the UI element list!"
                    )
                    self.history.append(step_data)
                    recorder.record_turn(
                        response=action_output,
                        action_obs=None,
                        prompt_tokens=pred.prompt_tokens,
                        completion_tokens=pred.completion_tokens,
                        cost_usd=pred.cost_usd,
                        llm_call_count=1,
                        summary=step_data["summary"],
                    )
                    recorder.populate_context(context)
                    continue

            action_dict = converted_action.as_dict(skip_none=True)
            if converted_action.action_type == "status":
                step_data["summary"] = "Agent thinks the request has been completed."
                self.history.append(step_data)
                recorder.record_turn(
                    response=action_output,
                    action_obs=T3AActionObservation(
                        action=action_dict,
                        info={"goal_status": converted_action.goal_status},
                    ),
                    prompt_tokens=pred.prompt_tokens,
                    completion_tokens=pred.completion_tokens,
                    cost_usd=pred.cost_usd,
                    llm_call_count=1,
                    summary=step_data["summary"],
                )
                recorder.write(context)
                return

            try:
                exec_resp = await self._bridge_call(
                    environment,
                    "/execute",
                    {
                        "action": action_dict,
                        "transition_pause": self.options.transition_pause,
                        "save_screenshot_path": (
                            f"{CONTAINER_IMAGES_DIR}/step_{step_num:03d}_after.png"
                        ),
                    },
                    timeout_sec=120,
                )
            except Exception as exc:  # noqa: BLE001
                step_data["summary"] = (
                    "Some error happened executing the action "
                    + str(converted_action.action_type)
                )
                self.history.append(step_data)
                recorder.record_turn(
                    response=action_output,
                    action_obs=T3AActionObservation(
                        action=action_dict,
                        info={"error": str(exc)},
                    ),
                    prompt_tokens=pred.prompt_tokens,
                    completion_tokens=pred.completion_tokens,
                    cost_usd=pred.cost_usd,
                    llm_call_count=1,
                    summary=step_data["summary"],
                )
                recorder.populate_context(context)
                continue

            after_element_list = str(exec_resp.get("after_element_list") or "")
            sum_prompt = summarize_prompt(
                goal,
                action,
                reason,
                before_element_list,
                after_element_list,
            )
            sum_pred = await asyncio.to_thread(llm.predict_with_usage, sum_prompt)
            summary_text = sum_pred.text
            if sum_pred.is_safe is False:
                summary_text = "Summary triggered LLM safety classifier."

            step_data["summary_prompt"] = sum_prompt
            step_data["summary"] = (
                f"Action selected: {action}. {summary_text}"
                if sum_pred.raw_response
                else "Error calling LLM in summerization phase."
            )
            step_data["summary_raw_response"] = sum_pred.raw_response
            self.history.append(step_data)

            after_rel = f"images/step_{step_num:03d}_after.png"
            image_path = after_rel if (self.logs_dir / after_rel).exists() else None
            recorder.record_turn(
                response=action_output,
                action_obs=T3AActionObservation(
                    action=action_dict,
                    image_path=image_path,
                    info={"summary": step_data["summary"]},
                ),
                prompt_tokens=pred.prompt_tokens + sum_pred.prompt_tokens,
                completion_tokens=pred.completion_tokens + sum_pred.completion_tokens,
                cost_usd=pred.cost_usd + sum_pred.cost_usd,
                llm_call_count=2,
                summary=step_data["summary"],
            )
            recorder.populate_context(context)

        recorder.write(context)

    def populate_context_post_run(self, context: AgentContext) -> None:
        result_path = self.logs_dir / "t3a_result.json"
        if not result_path.exists():
            return
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to read T3A result sidecar: %s", exc)
            return
        ctx_payload = payload.get("context") or {}
        context.n_input_tokens = ctx_payload.get("n_input_tokens")
        context.n_output_tokens = ctx_payload.get("n_output_tokens")
        context.cost_usd = ctx_payload.get("cost_usd")
        context.metadata = ctx_payload.get("metadata")

    def _resolve_max_steps(self, task_spec: dict[str, Any]) -> int:
        if self.options.max_steps is not None:
            return int(self.options.max_steps)
        if task_spec.get("complexity") is not None:
            return max(1, allocate_step_budget(float(task_spec["complexity"])))
        return 30

    def _create_llm_client(self) -> T3ALlmClient:
        model_name = self.model_name
        if not model_name:
            raise ValueError("T3AAgent requires model_name to be set")
        api_format = (
            self._model_api_format.value
            if self._model_api_format is not None
            else self.options.api_format
        )
        return T3ALlmClient(
            model_name=model_name,
            api_format=api_format,
            base_url=self._execution_base_url,
            api_key_name=self._model_api_key_name,
            temperature=self.options.temperature,
            max_tokens=self.options.max_tokens,
            max_retry=self.options.max_retry,
            env=self.extra_env,
        )

    async def _exec_checked(
        self,
        environment: BaseEnvironment,
        command: str,
        *,
        timeout_sec: int | None = None,
    ) -> str:
        result = await environment.exec(
            command=command,
            env=self.extra_env or None,
            timeout_sec=timeout_sec,
        )
        if result.return_code != 0:
            raise RuntimeError(
                f"Container command failed (rc={result.return_code}): {command}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        return result.stdout or ""

    async def _bridge_call(
        self,
        environment: BaseEnvironment,
        endpoint: str,
        payload: dict[str, Any],
        *,
        method: str = "POST",
        timeout_sec: int = 120,
    ) -> dict[str, Any]:
        port = int(self.options.bridge_port)
        cmd = (
            f"python3 {shlex.quote(CONTAINER_BRIDGE_PATH)} call "
            f"--port {port} --method {shlex.quote(method)} "
            f"--endpoint {shlex.quote(endpoint)} "
            f"--payload {shlex.quote(json.dumps(payload))} "
            f"--timeout {int(timeout_sec)}"
        )
        stdout = await self._exec_checked(environment, cmd, timeout_sec=timeout_sec + 15)
        return json.loads(stdout) if stdout.strip() else {}
