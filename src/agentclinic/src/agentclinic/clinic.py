import copy
import threading
import time
from collections.abc import Callable

try:
    from . import prompts
except ImportError:
    import prompts

SUBMITTED = "Diagnosis recorded. The consultation is over."
ENDED = "The consultation has already ended because a diagnosis was already submitted."
CLOSED = "The consultation is closed."
BUSY = "Busy: your previous turn is still being answered. No turn was used. Call get_status to see whether it finished and to read its reply."
RESUMED_FIELDS = (
    "turns",
    "transcript",
    "diagnosis",
    "submitted_at_turn",
    "errors",
    "patient_history",
    "measurement_history",
    "last_reply",
    "served_models",
    "simulator_unrecovered",
    "state_unrecovered",
    "persist_failures",
)


class ClinicLLMError(RuntimeError):
    pass


class ClinicStateError(RuntimeError):
    pass


class Clinic:
    def __init__(
        self,
        case: dict,
        llm: Callable[[str, str, str], str],
        patient_model: str,
        measurement_model: str,
        max_turns: int = prompts.MAX_INFERENCES,
        on_change: Callable[[dict], None] | None = None,
        initial_state: dict | None = None,
    ):
        self._patient_info = case["patient_actor"]
        exams = copy.deepcopy(case["physical_exam"])
        exams["tests"] = case["test_results"]
        self._exam_info = exams
        self._llm = llm
        self._models = {"patient": patient_model, "measurement": measurement_model}
        self._max_turns = max_turns
        self._on_change = on_change
        self._turn_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._state = {
            "task_id": case["task_id"],
            "turns": 0,
            "max_turns": max_turns,
            "transcript": [],
            "diagnosis": None,
            "submitted_at_turn": None,
            "errors": [],
            "pending": None,
            "restarts": 0,
            "patient_history": "",
            "measurement_history": "",
            "last_reply": None,
            "models": {"patient": patient_model, "measurement": measurement_model},
            "served_models": {"patient": None, "measurement": None},
            "sealed": False,
            "simulator_unrecovered": False,
            "state_unrecovered": False,
            "persist_failures": 0,
        }
        if initial_state is not None:
            if initial_state.get("task_id") != case["task_id"]:
                raise ValueError(f"saved state belongs to {initial_state.get('task_id')!r}, not {case['task_id']!r}")
            for key in RESUMED_FIELDS:
                self._state[key] = copy.deepcopy(initial_state.get(key, self._state[key]))
            self._state["restarts"] = int(initial_state.get("restarts", 0)) + 1
            if initial_state.get("pending") is not None:
                self._state["simulator_unrecovered"] = True

    def ask_patient(self, question: str) -> str:
        return self.ask_patient_with_status(question)[1]

    def request_test(self, request: str) -> str:
        return self.request_test_with_status(request)[1]

    def submit_diagnosis(self, diagnosis: str) -> str:
        return self.submit_diagnosis_with_status(diagnosis)[1]

    def ask_patient_with_status(self, question: str) -> tuple[str, str]:
        return self.say_with_status(question)

    def request_test_with_status(self, request: str) -> tuple[str, str]:
        request = prompts.normalize_response(request)
        if prompts.REQUEST_TEST not in request:
            request = f"{prompts.REQUEST_TEST}: {request}"
        return self.say_with_status(request)

    def submit_diagnosis_with_status(self, diagnosis: str) -> tuple[str, str]:
        diagnosis = prompts.normalize_response(diagnosis)
        if prompts.DIAGNOSIS_READY not in diagnosis:
            diagnosis = f"{prompts.DIAGNOSIS_READY}: {diagnosis}"
        return self.say_with_status(diagnosis)

    def snapshot(self) -> dict:
        with self._state_lock:
            return copy.deepcopy(self._state)

    def seal(self) -> dict:
        with self._state_lock:
            self._state["sealed"] = True
            return copy.deepcopy(self._state)

    def say(self, utterance: str) -> str:
        return self.say_with_status(utterance)[1]

    def say_with_status(self, utterance: str) -> tuple[str, str]:
        utterance = prompts.normalize_response(utterance)
        if len(utterance) > prompts.MAX_UTTERANCE_CHARS:
            return "rejected", (
                f"Rejected: this message is too long ({len(utterance)} characters; the limit is "
                f"{prompts.MAX_UTTERANCE_CHARS}). No turn was used."
            )
        if not self._turn_lock.acquire(blocking=False):
            return "busy", BUSY
        try:
            return self._take_turn(utterance)
        finally:
            self._turn_lock.release()

    def _take_turn(self, utterance: str) -> tuple[str, str]:
        current = self.snapshot()
        if current["sealed"]:
            return "closed", CLOSED
        if current["diagnosis"] is not None:
            return "ended", ENDED
        if current["turns"] >= self._max_turns:
            return "max_reached", prompts.MAX_REACHED
        new = copy.deepcopy(current)
        new["pending"] = None
        new["state_unrecovered"] = False
        new["turns"] += 1
        new["transcript"].append({"role": "doctor", "text": utterance})
        if prompts.DIAGNOSIS_READY in utterance:
            new["diagnosis"] = utterance
            new["submitted_at_turn"] = new["turns"]
            new["last_reply"] = SUBMITTED
            self._commit(new)
            return "submitted", SUBMITTED
        if prompts.REQUEST_TEST in utterance:
            role = "measurement"
            reply = self._call(
                role,
                prompts.measurement_system_prompt(self._exam_info),
                prompts.measurement_user_prompt(current["measurement_history"], utterance),
            )
            new["measurement_history"] += utterance + "\n\n" + reply + "\n\n"
            new["patient_history"] += reply + "\n\n"
        else:
            role = "patient"
            reply = self._call(
                role,
                prompts.patient_system_prompt(self._patient_info),
                prompts.patient_user_prompt(current["patient_history"], utterance),
            )
            new["patient_history"] += utterance + "\n\n" + reply + "\n\n"
            new["measurement_history"] += reply + "\n\n"
        new["simulator_unrecovered"] = False
        new["served_models"][role] = getattr(self._llm, "last_model", None)
        new["transcript"].append({"role": role, "text": reply})
        if new["turns"] == self._max_turns - 1:
            reply = reply + prompts.FINAL_NOTICE
        new["last_reply"] = reply
        self._commit(new)
        return "ok", reply

    def _commit(self, new: dict) -> None:
        with self._state_lock:
            sealed = self._state["sealed"]
        if sealed:
            raise ClinicStateError("The consultation was closed before this turn could be recorded.")
        if self._on_change is not None:
            try:
                self._on_change(copy.deepcopy(new))
            except Exception as exc:
                with self._state_lock:
                    self._state["pending"] = None
                    self._state["state_unrecovered"] = True
                    self._state["persist_failures"] += 1
                raise ClinicStateError(
                    "The clinic could not record this turn (infrastructure error). Nothing was recorded; the turn can be retried."
                ) from exc
        with self._state_lock:
            new["persist_failures"] = self._state["persist_failures"]
            self._state = new

    def _persist_best_effort(self) -> None:
        if self._on_change is None:
            return
        try:
            self._on_change(self.snapshot())
        except Exception:
            pass

    def _call(self, role: str, system: str, user: str) -> str:
        label = "patient" if role == "patient" else "measurement reader"
        with self._state_lock:
            self._state["pending"] = {"role": role, "started_at": time.time()}
        self._persist_best_effort()
        try:
            return self._llm(self._models[role], system, user)
        except Exception as exc:
            with self._state_lock:
                self._state["pending"] = None
                self._state["simulator_unrecovered"] = True
                self._state["errors"].append(f"{label}: {type(exc).__name__}: {exc}")
            self._persist_best_effort()
            raise ClinicLLMError(
                f"The simulated {label} is unavailable ({type(exc).__name__}). This is an infrastructure error, not a reply."
            ) from exc
