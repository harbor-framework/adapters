import hashlib
import os
import sys
import types
import urllib.request
import warnings
from pathlib import Path

from agentclinic.cases import UPSTREAM_COMMIT, UPSTREAM_REPO

SOURCE_SHA256 = "ee9cfb3020c7addf717ba8eb3510ba81b2b4b53071cba67d0663ad6c7c6ddbd3"
SOURCE_URL = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_COMMIT}/agentclinic.py"


def upstream_source() -> str:
    local = os.environ.get("AGENTCLINIC_UPSTREAM_SOURCE")
    if local:
        data = Path(local).read_bytes()
    else:
        root = os.environ.get("AGENTCLINIC_CACHE_DIR")
        base = Path(root) if root else Path.home() / ".cache" / "harbor-agentclinic"
        cached = base / UPSTREAM_COMMIT / "agentclinic.py"
        if cached.exists():
            data = cached.read_bytes()
        else:
            with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
                data = response.read()
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE_SHA256:
        raise RuntimeError(f"upstream agentclinic.py sha256 {digest} != pinned {SOURCE_SHA256}")
    return data.decode("utf-8")


class Recorder:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, model_str, prompt, system_prompt, **kwargs):
        self.calls.append({"model": model_str, "prompt": prompt, "system": system_prompt})
        return self.replies.pop(0)


def load_upstream(recorder: Recorder) -> dict:
    stubs = {name: types.ModuleType(name) for name in ("anthropic", "openai", "replicate", "transformers")}
    stubs["transformers"].pipeline = lambda *a, **k: None
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        namespace = {"__name__": "agentclinic_upstream"}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            code = compile(upstream_source(), "agentclinic.py", "exec")
        exec(code, namespace)
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    namespace["query_model"] = recorder
    namespace["time"] = types.SimpleNamespace(sleep=lambda *_: None)
    return namespace


def role_of(system_prompt: str) -> str:
    for prefix, role in (
        ("You are a doctor", "doctor"),
        ("You are a patient", "patient"),
        ("You are an measurement reader", "measurement"),
        ("You are responsible for determining", "moderator"),
    ):
        if system_prompt.startswith(prefix):
            return role
    raise AssertionError(f"unknown role for system prompt {system_prompt[:40]!r}")


def simulated_reply(role: str, n: int, messy: bool) -> str:
    if messy:
        return (
            f"Patient reply {n}.\n\nI  feel\ttired. "
            if role == "patient"
            else f"RESULTS:\n  finding {n}\n\n- normal  otherwise"
        )
    return f"Patient reply {n}." if role == "patient" else f"RESULTS: finding {n}"


class ScriptedWorld:
    def __init__(self, moderator_reply="Yes", messy=False):
        self.counts = {"patient": 0, "measurement": 0}
        self.calls = []
        self.moderator_reply = moderator_reply
        self.messy = messy

    def reply(self, system_prompt: str, prompt: str) -> str:
        role = role_of(system_prompt)
        self.calls.append({"role": role, "system": system_prompt, "prompt": prompt})
        if role == "moderator":
            return self.moderator_reply
        self.counts[role] += 1
        return simulated_reply(role, self.counts[role], self.messy)


class Transport:
    def __init__(self, doctor_script, moderator_reply="Yes", messy=False):
        self.doctor_script = list(doctor_script)
        self.moderator_reply = moderator_reply
        self.messy = messy
        self.counts = {"patient": 0, "measurement": 0}
        self.calls = []

    def create(self, model, messages, temperature=None, max_tokens=None, **kwargs):
        system, user = messages[0]["content"], messages[1]["content"]
        role = role_of(system)
        if role == "doctor":
            content = self.doctor_script.pop(0)
        elif role == "moderator":
            content = self.moderator_reply
        else:
            self.counts[role] += 1
            content = simulated_reply(role, self.counts[role], self.messy)
        self.calls.append(
            {
                "role": role,
                "system": system,
                "prompt": user,
                "reply": content,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return {"choices": [{"message": {"content": content}}]}


def load_upstream_with_transport(transport: Transport) -> dict:
    stubs = {name: types.ModuleType(name) for name in ("anthropic", "openai", "replicate", "transformers")}
    stubs["transformers"].pipeline = lambda *a, **k: None
    stubs["openai"].ChatCompletion = types.SimpleNamespace(create=transport.create)
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        namespace = {"__name__": "agentclinic_upstream"}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            code = compile(upstream_source(), "agentclinic.py", "exec")
        exec(code, namespace)
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    namespace["time"] = types.SimpleNamespace(sleep=lambda *_: None)
    return namespace


def run_upstream_consultation(
    fixture_path: Path, doctor_script: list[str], tmp_path: Path, moderator_reply: str = "Yes", messy: bool = False
):
    transport = Transport(doctor_script, moderator_reply, messy)
    ns = load_upstream_with_transport(transport)
    (tmp_path / "agentclinic_medqa_extended.jsonl").write_text(fixture_path.read_text().splitlines()[0] + "\n")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        ns["main"](
            "k",
            None,
            "llm",
            "None",
            "None",
            "gpt-4o-mini",
            "gpt-4o-mini",
            "gpt-4o-mini",
            "gpt-4o-mini",
            1,
            "MedQA_Ext",
            False,
            20,
        )
    finally:
        os.chdir(cwd)
    return transport
