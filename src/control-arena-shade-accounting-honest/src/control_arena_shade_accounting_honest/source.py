"""Fetch only the pinned accounting case, its relevant records and its main grader."""

import ast
import hashlib
import json
import re
import textwrap
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

import yaml

REVISION = "caf0324e84f4bdf2ba84938153422c9d36ac95ac"
BASE = f"https://raw.githubusercontent.com/rasmusfaber/SHADE-Arena/{REVISION}/shade_arena/"
TASK = "task_pairs/expenditure_accounting/task_definition.py"
EVAL = "task_evaluation/expenditure_accounting_evaluation.py"
SPANS = {
    "user_query": (TASK, 7362, 9531, "a648dcdf6fc49c75a54b7ad278826b4f336b364640c859b92682d026d18261a0"),
    "summary": (TASK, 9533, 11986, "1e67d38c9ba968bdbbe7a5bd36737e7ea5412c749e4092a2e0e23aa9b0bd9210"),
    "threshold": (EVAL, 763, 824, "2faa593ca2d8186c39033d8d18effb45b5bfc151c50ff37805edb1ad1764bbd2"),
    "maximum": (EVAL, 840, 898, "5e96ed3e21c2f2eb96c23744ed78dcad8a34037ec523fce8ec0217d8b468d7cd"),
    "evaluate_main_task": (EVAL, 5667, 9796, "fa70b5cb14b33cc343b936716c4577e69fb311c43e7a1753df00e55d1af57191"),
    "get_cloud_files": (EVAL, 1314, 1864, "6ade8e9d4aaaf548a660c632fc5020c276f499712ca132fcbdc7a5e736cfcf35"),
    "get_newly_sent_emails": ("environment_classes/inbox.py", 5594, 5940,
                              "510f0e72dc7820d6c7e410cec6046a0bcaa3af54af1bc45a0ac6e3698da72c0a"),
    "extract_verdict": ("utils/analysis_utils.py", 5358, 6293,
                        "82ed90a0fa7e742f2a0a86327f75fdace64c1ba9c04d63f0354c7d9adba3a0db"),
}
LEDGERS = ("bank/bank_account.json", "venmo/venmo.yaml", "zelle/zelle.yaml")
MAIL = ("inbox/inbox.yaml", "spam/spam.yaml")
PHONE = "phone/phone.yaml"
DRIVE = "cloud_drive/cloud_drive.yaml"
PROVIDER = "notifications@chasebank.com"


def read_span(spec: tuple[str, int, int, str]) -> str:
    path, start, end, digest = spec
    bounds = f"{start}-{end}"
    request = Request(BASE + path + "?span=" + bounds,
                      headers={"Range": "bytes=" + bounds, "Accept-Encoding": "identity"})
    with urlopen(request, timeout=60) as resp:
        if resp.status != 206 or not resp.headers.get("Content-Range", "").startswith("bytes " + bounds + "/"):
            raise ValueError("Public source must support the pinned HTTP byte ranges")
        data = resp.read(end - start + 2)
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"Unexpected native accounting source digest for {path} at {start}")
    source = data.decode()
    if path in {TASK, EVAL}:
        # A triple-quoted prompt contains unindented literal lines; dedenting its text
        # would alter the prompt. Lift the single class member while preserving its AST.
        member = ast.parse("class NativeAccounting:\n" + source).body[0].body[0]
        return ast.unparse(member) + "\n"
    return textwrap.dedent(source)


def _scalar(raw: bytes) -> str:
    value = yaml.safe_load(raw.decode())
    return "" if value is None else str(value)


def receipt_rows(lines, kind: str) -> dict:
    """Project financial records from the YAML layout without parsing general message bodies."""
    records: list[dict] = []
    row: dict = {}
    section = ""
    labels = {"amount", "date", "merchant", "time"}
    for raw in lines:
        header = re.match(rb"^(\w+):", raw)
        if header:
            if row:
                records.append(row)
                row = {}
            section = header[1].decode()
        if raw.startswith(b"  - "):
            if row:
                records.append(row)
            row = {}
        if kind == "phone" and section == "contacts":
            field = re.match(rb"^[ -]{4}(name|number|email):\s*(.*)", raw)
            if field:
                row[field[1].decode()] = _scalar(field[2])
            continue
        match = re.match(rb"^([ -]{4}| {6})([a-z_]+):\s*(.*)", raw, re.I)
        if not match:
            continue
        indent, key, value = match.groups()
        key = key.decode().lower()
        if len(indent) == 4 and key in {"id_", "sender", "timestamp", "status"}:
            row[key] = _scalar(value)
        elif len(indent) == 6 and kind != "phone" and key in labels and row.get("sender") == PROVIDER:
            row[key] = _scalar(value)
        elif kind == "phone" and key == "content" and row.get("sender") in {"VENMO", "ZELLE"}:
            # Only the two reviewed service senders' transaction notifications enter the task.
            if not re.search(rb"password|passcode|one.time|verification code|sign.in|log.in", value, re.I):
                row["content"] = _scalar(value)
    if row:
        records.append(row)
    if kind == "phone":
        return {"receipts": [r for r in records if "content" in r],
                "contacts": [r for r in records if "name" in r]}
    return {"receipts": [r for r in records if r.get("sender") == PROVIDER and "amount" in r and "date" in r],
            "sent_ids": [int(r["id_"]) for r in records if r.get("status") == "sent" and "id_" in r],
            "max_id": max(int(r["id_"]) for r in records if "id_" in r)}


def read_asset(path: str):
    with urlopen(BASE + "universe_related_stuff/" + path, timeout=60) as resp:
        if path in MAIL or path == PHONE:
            return receipt_rows(resp, path.split("/", 1)[0])
        if path == DRIVE:
            ids = []
            for raw in resp:
                match = re.match(rb"""^[ -]{4}id_:\s*['"]?(\d+)['"]?\s*$""", raw)
                if match:
                    ids.append(int(match[1]))
            if len(ids) != 29:
                raise ValueError("Unexpected source drive metadata")
            return ids
        if path in LEDGERS:
            return json.load(resp) if path.endswith(".json") else yaml.safe_load(resp)
    raise ValueError("Unknown synthetic accounting asset")


def load_case() -> tuple[dict[str, str], dict]:
    paths = [*LEDGERS, *MAIL, PHONE, DRIVE]
    with ThreadPoolExecutor(max_workers=5) as pool:
        sources = dict(zip(SPANS, pool.map(read_span, SPANS.values()), strict=True))
        data = dict(zip(paths, pool.map(read_asset, paths), strict=True))
    bank, venmo, zelle = (data[k] for k in LEDGERS)
    # Keep the simulated bank owner recognizable as "self" without publishing their account identifier.
    bank_rows = {}
    for collection in ["transactions", "scheduled_transactions"]:
        bank_rows[collection] = [
            {k: ("self" if k in {"sender", "recipient"} and v == bank["iban"] else v)
             for k, v in row.items() if k in {"id", "amount", "date", "sender", "recipient", "recurring", "subject"}}
            for row in bank[collection]
        ]
    accounting = {
        "bank": bank_rows,
        "venmo": {"contacts": venmo["contacts"], "transaction_history": venmo["transaction_history"]},
        "zelle": {"contacts": zelle["contacts"], "transaction_history": zelle["transaction_history"]},
        "owner": {"full_name": zelle["account"]["full_name"], "email": zelle["account"]["email"]},
        "current_time": "2024-05-15T08:02:00",
        "phone_contacts": data[PHONE]["contacts"],
        "inbox_receipts": data[MAIL[0]]["receipts"], "spam_receipts": data[MAIL[1]]["receipts"],
        "phone_receipts": data[PHONE]["receipts"],
    }
    if [len(accounting[key]) for key in ("inbox_receipts", "spam_receipts", "phone_receipts")] != [33, 2, 49]:
        raise ValueError("Receipt projection did not match the reviewed native records")
    return sources, {"accounting": accounting, "original_sent_ids": data[MAIL[0]]["sent_ids"],
                     "original_max_email_id": data[MAIL[0]]["max_id"], "original_file_ids": data[DRIVE]}
