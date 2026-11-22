import json
import os
import signal
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from clinic import Clinic, ClinicLLMError, ClinicStateError
from fastmcp import FastMCP
from llm import ChatClient
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

DEFAULT_MODEL = "gpt-4o-mini"

ASK_PATIENT = "Say one line of dialogue to the patient (a question, or an examination you perform) and get the patient's reply. Uses one of your turns."
REQUEST_TEST = "Order a medical test or measurement by name, for example Chest_X-Ray, and get the result from the measurement reader. Uses one of your turns."
SUBMIT_DIAGNOSIS = (
    "Give your final diagnosis. This ends the consultation and uses one of your turns. Only the first diagnosis counts."
)
GET_STATUS = "Report how many turns you have used and how many remain, whether a turn is still being answered, and the last reply. Does not use a turn."


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".state-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


class LazyChat:
    def __init__(self):
        self._client: ChatClient | None = None

    @property
    def last_model(self) -> str | None:
        return getattr(self._client, "last_model", None)

    def __call__(self, model: str, system: str, user: str) -> str:
        if self._client is None:
            self._client = ChatClient.from_env()
        return self._client(model, system, user)


def status_of(clinic: Clinic) -> dict:
    state = clinic.snapshot()
    return {
        "turns_used": state["turns"],
        "max_turns": state["max_turns"],
        "turns_remaining": max(state["max_turns"] - state["turns"], 0),
        "consultation_over": state["diagnosis"] is not None or state["turns"] >= state["max_turns"],
        "call_in_progress": state["pending"] is not None,
        "last_reply": state["last_reply"],
    }


def build_server(clinic: Clinic) -> FastMCP:
    mcp = FastMCP("clinic")

    @mcp.tool(description=ASK_PATIENT)
    def ask_patient(question: str) -> str:
        return clinic.ask_patient(question)

    @mcp.tool(description=REQUEST_TEST)
    def request_test(test: str) -> str:
        return clinic.request_test(test)

    @mcp.tool(description=SUBMIT_DIAGNOSIS)
    def submit_diagnosis(diagnosis: str) -> str:
        return clinic.submit_diagnosis(diagnosis)

    @mcp.tool(description=GET_STATUS)
    def get_status() -> str:
        return json.dumps(status_of(clinic))

    actions = {
        "ask_patient": clinic.ask_patient_with_status,
        "request_test": clinic.request_test_with_status,
        "submit_diagnosis": clinic.submit_diagnosis_with_status,
    }

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    @mcp.custom_route("/api/{action}", methods=["POST"])
    async def api(request: Request) -> JSONResponse:
        action = actions.get(request.path_params["action"])
        if action is None:
            return JSONResponse({"error": "unknown action"}, status_code=404)
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("text"), str):
            return JSONResponse({"error": "expected a JSON body with a string field 'text'"}, status_code=400)
        try:
            status, reply = await run_in_threadpool(action, body["text"])
        except ClinicLLMError as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)
        except ClinicStateError as exc:
            return JSONResponse({"error": str(exc)}, status_code=503)
        return JSONResponse({"reply": reply, "status": status})

    return mcp


def state_path_from_env() -> Path:
    return Path(os.environ.get("AGENTCLINIC_STATE_PATH", "/root/logs/consultation_state.json"))


def install_seal_handler(clinic: Clinic, state_path: Path) -> None:
    def seal_in_background(signum, frame):
        threading.Thread(target=lambda: write_state(state_path, clinic.seal()), daemon=True).start()

    signal.signal(signal.SIGUSR1, seal_in_background)


def build_from_env(llm: Callable[[str, str, str], str] | None = None) -> tuple[FastMCP, Clinic]:
    case = json.loads(Path(os.environ.get("AGENTCLINIC_CASE_PATH", "/app/case.json")).read_text(encoding="utf-8"))
    state_path = state_path_from_env()
    saved = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    clinic = Clinic(
        case=case,
        llm=llm or LazyChat(),
        patient_model=os.environ.get("AGENTCLINIC_PATIENT_MODEL") or DEFAULT_MODEL,
        measurement_model=os.environ.get("AGENTCLINIC_MEASUREMENT_MODEL") or DEFAULT_MODEL,
        on_change=lambda state: write_state(state_path, state),
        initial_state=saved,
    )
    write_state(state_path, clinic.snapshot())
    return build_server(clinic), clinic


if __name__ == "__main__":
    server, clinic = build_from_env()
    install_seal_handler(clinic, state_path_from_env())
    server.run(transport="streamable-http", host="0.0.0.0", port=8000)
