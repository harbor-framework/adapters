"""Adapter: BigLaw Bench (6 BLB-Core + 10 BLB-Workflows/SPA = 16 public tasks) -> Harbor tasks.

Source: https://github.com/harveyai/biglaw-bench (pinned commit). CSVs are fetched at
generation time, while PDFs and schema.json are fetched during Docker image build;
nothing from the upstream dataset is committed to adapters or harbor-datasets.
"""

import csv
import io
import json
import re
import shlex
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

UPSTREAM = "harveyai/biglaw-bench"
COMMIT = "138fd481b459a00bbd98eeb710f69ada1052bd47"
RAW_BASE = f"https://raw.githubusercontent.com/{UPSTREAM}/{COMMIT}"
RAW_CORE = f"{RAW_BASE}/blb-core"
RAW_SPA = f"{RAW_BASE}/blb-workflows/spa"
TEMPLATE_DIR = Path(__file__).parent / "task-template"
SOLUTIONS_DIR = Path(__file__).parent / "solutions"

SPLIT_CHOICES = ("full", "core", "spa")

_VERBS = {
    "state", "mention", "provide", "identify", "explain", "recommend", "note", "discuss",
    "include", "address", "acknowledge", "propose", "analyze", "highlight", "describe",
    "establish", "reference", "suggest", "conclude", "cite", "recognize", "outline", "say",
}

_ENTITY_TYPE_RE = re.compile(
    r"^(.*?)\b(limited liability company|unlimited liability company|aktiengesellschaft|"
    r"corporation|corp\.?|llc|ulc|l\.?l\.?c\.?|l\.?p\.?|llp|partnership|company|"
    r"individual|trust)\s*$",
    re.I,
)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _fetch(base: str, path: str) -> bytes:
    url = f"{base}/{urllib.parse.quote(path)}"
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def criterion_to_statement(q: str) -> str:
    """Turn a rubric question ('Does the response state that X?') into a declarative statement."""
    q = re.sub(r"\s*\((\d+(?:\.\d+)?)\s*points?\)\s*$", "", q.strip()).rstrip("?").strip()
    m = re.match(r"^Does (the [\w'\- ]+?) (\w+)\b(.*)$", q)
    if m and m.group(2).lower() in _VERBS:
        verb = m.group(2)
        verb = verb + ("es" if verb.endswith(("s", "sh", "ch")) else "s")
        return f"{m.group(1).capitalize()} {verb}{m.group(3)}."
    m = re.match(r"^Do (the [\w'\- ]+?) (\w+)\b(.*)$", q)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}{m.group(3)}."
    m = re.match(r"^(Is|Are) (the [\w'\- ]+?) ((?:in|written|a|an|formatted|structured|organized)\b.*)$", q)
    if m:
        return f"{m.group(2).capitalize()} {m.group(1).lower()} {m.group(3)}."
    return f"The response satisfies the following requirement: {q}."


def reference_answer(rubric: str, prompt: str) -> str:
    """Rubric-derived reference answer: every affirmative criterion restated as a satisfied statement."""
    out = [f"# Reference response\n\nTask: {prompt}\n"]
    section = ""
    for line in rubric.splitlines():
        s = line.strip()
        if re.match(r"^negative points", s, re.I):
            break
        m = re.search(r"\((\d+(?:\.\d+)?)\s*points?\)\s*$", s)
        if m:
            body = re.sub(r"^[a-zA-Z0-9]+\.?\s+(?=[A-Z])", "", s)
            out.append(f"- {criterion_to_statement(body)}")
        elif s and not s.lower().startswith("affirmative"):
            label = re.sub(r"^\d+\.\s*", "", s).rstrip(":")
            if label != section and not re.match(r"^[a-z]\.\s", s):
                out.append(f"\n## {label}\n")
                section = label
    return "\n".join(out) + "\n"


def _parse_single_party(line: str) -> dict[str, str]:
    line = re.sub(r'\s*-\s*the\s+"[^"]+"\s*$', "", line.strip()).rstrip(";,").strip()
    m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", line)
    if m:
        name = m.group(1).strip().rstrip(",")
        inside = re.sub(r"^a\s+", "", m.group(2).strip(), flags=re.I)
        em = _ENTITY_TYPE_RE.match(inside)
        if em:
            jur = em.group(1).strip().rstrip(",")
            etype = em.group(2).strip()
            return {
                "name": name,
                "entity_type": etype or "N/A",
                "jurisdiction": jur or "N/A",
            }
    return {"name": line or "N/A", "entity_type": "N/A", "jurisdiction": "N/A"}


def parse_party(raw: str) -> dict[str, str]:
    """Parse an upstream CSV party string into {name, entity_type, jurisdiction}."""
    raw = raw.strip()
    if not raw or raw.upper() == "N/A":
        return {"name": "N/A", "entity_type": "N/A", "jurisdiction": "N/A"}

    lines = [
        ln.strip()
        for ln in raw.splitlines()
        if ln.strip() and not re.match(r'^"?(buyer|seller)"?:?$', ln.strip(), re.I)
    ]
    if len(lines) == 1:
        return _parse_single_party(lines[0])

    # Multi-line party descriptions (e.g. multiple sellers or TreeHouse US/CA entities)
    parsed = [_parse_single_party(ln) for ln in lines]
    names = "; ".join(lines)
    etypes = "; ".join(dict.fromkeys(p["entity_type"] for p in parsed if p["entity_type"] != "N/A"))
    jurs = "; ".join(dict.fromkeys(p["jurisdiction"] for p in parsed if p["jurisdiction"] != "N/A"))
    return {
        "name": names,
        "entity_type": etypes or "N/A",
        "jurisdiction": jurs or "N/A",
    }


def parse_list_field(raw: str) -> list[str]:
    """Convert a newline-delimited CSV deal-point string into a clean list of strings."""
    raw = raw.strip()
    if not raw or raw.upper() == "N/A":
        return []
    items = []
    for line in raw.splitlines():
        s = re.sub(r"^\s*[-*\u2022]\s*", "", line.strip())
        if s:
            items.append(s)
    return items


def parse_conditions(raw: str) -> tuple[list[str], list[str]]:
    """Split 'Conditions Precedent to Closing Transaction' into (to_sellers, to_buyers)."""
    raw = raw.strip()
    if not raw or raw.upper() == "N/A":
        return [], []

    mutual: list[str] = []
    buyer: list[str] = []
    seller: list[str] = []
    bucket: list[str] | None = None

    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        hdr = s.rstrip(":").strip().lower()
        if hdr == "mutual":
            bucket = mutual
            continue
        if hdr in ("buyer", "purchaser", "conditions to obligations of buyer", "conditions to buyer's obligations"):
            bucket = buyer
            continue
        if hdr in ("seller", "conditions to obligations of seller", "conditions to seller's obligations"):
            bucket = seller
            continue
        item = re.sub(r"^\s*[-*\u2022]\s*", "", s)
        if bucket is None:
            mutual.append(item)
        else:
            bucket.append(item)

    return mutual + seller, mutual + buyer


def spa_row_to_json(row: dict[str, str]) -> dict:
    """Map one row of blb-workflows/spa/spa-samples.csv into schema.json structure."""
    to_sellers, to_buyers = parse_conditions(row["Conditions Precedent to Closing Transaction"])
    return {
        "effective_date": row["Effective Date"].strip(),
        "purchaser": parse_party(row["Purchaser (Name + entity type)"]),
        "seller": parse_party(row["Seller (name + entity)"]),
        "company": parse_party(row["Company (Name, jurisdiction and entity type)"]),
        "price": {
            "base_purchase_price": row["Base Purchase Price"].strip(),
            "price_per_share": row["Price Per Share"].strip(),
            "number_of_shares": row["Number of Shares"].strip(),
        },
        "closing_deliverables": parse_list_field(row["Closing Deliverables List"]),
        "purchase_price_adjustments": row["Post-Closing Payments Adjustments"].strip(),
        "capitalization": {
            "shares_outstanding": row["Shares Outstanding"].strip(),
            "pro_forma_percentage": row["Pro Forma Ownership Percentage"].strip(),
        },
        "transaction_agreements": parse_list_field(row["List of Other Transaction Agreements"]),
        "indemnification": {
            "by_buyer": {
                "survival": row["Indemnification by Buyer Survival Period"].strip(),
                "liability_cap": row["Indemnification by Buyer Liability Cap"].strip(),
                "basket": row["Indemnification by Buyer Basket"].strip(),
            },
            "by_seller": {
                "survival": row["Indemnification by Seller or Company Survival Period"].strip(),
                "liability_cap": row["Indemnification by Seller or Company  Liability Cap"].strip(),
                "basket": row["Indemnification by Seller or Company  Basket"].strip(),
            },
        },
        "conditions_to_sellers_obligations": to_sellers,
        "conditions_to_buyers_obligations": to_buyers,
        "governing_law": row["Governing Law"].strip(),
        "dispute_resolution_jurisdiction": row["Dispute Resolution Jurisdiction"].strip(),
        "termination_rights": {
            "by_buyer": row["Termination Rights by Buyer"].strip(),
            "by_seller": row["Termination Rights by Seller"].strip(),
        },
        "effect_of_termination": parse_list_field(row["Effect of Termination"]),
        "transfer_taxes": row["Transfer Taxes"].strip(),
        "fees_and_expenses": row["Fees and Expenses"].strip(),
        "notices": {
            "to_buyer": row["Notices to Buyer"].strip(),
            "to_seller_or_company": row["Notices to Seller/Company"].strip(),
        },
    }


class BigLawBenchAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "full",
        **kwargs,
    ):
        if split not in SPLIT_CHOICES:
            raise ValueError(f"Unsupported split {split!r}; expected one of {SPLIT_CHOICES}")
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.split = split

    def load_core_records(self) -> list[dict]:
        text = _fetch(RAW_CORE, "core-samples.csv").decode("utf-8-sig")
        records = []
        for rec in csv.DictReader(io.StringIO(text)):
            rec = dict(rec)
            rec["_kind"] = "core"
            rec["_id"] = f"blb-core-{int(rec['Number']):03d}"
            records.append(rec)
        return records

    def load_spa_records(self) -> tuple[list[dict], bytes]:
        text = _fetch(RAW_SPA, "spa-samples.csv").decode("utf-8-sig")
        schema_bytes = _fetch(RAW_SPA, "schema.json")
        records = []
        for idx, rec in enumerate(csv.DictReader(io.StringIO(text)), 1):
            rec = dict(rec)
            rec["_kind"] = "spa"
            rec["_index"] = idx
            rec["_id"] = f"blb-spa-{idx:03d}"
            records.append(rec)
        return records, schema_bytes

    @staticmethod
    def task_id(rec: dict) -> str:
        if "_id" in rec:
            return rec["_id"]
        return f"blb-core-{int(rec['Number']):03d}"

    def _matches_filter(self, rec: dict, wanted: set[str]) -> bool:
        tid = self.task_id(rec).lower()
        if tid in wanted:
            return True
        if rec.get("_kind") == "core":
            return str(int(rec["Number"])) in wanted
        idx = rec.get("_index")
        return idx is not None and f"spa-{idx}" in wanted or f"spa-{idx:03d}" in wanted

    def run(self) -> None:
        records: list[dict] = []
        schema_bytes: bytes | None = None

        if self.split in ("full", "core"):
            records.extend(self.load_core_records())
        if self.split in ("full", "spa"):
            spa_records, schema_bytes = self.load_spa_records()
            records.extend(spa_records)

        if self.task_ids:
            wanted = {t.lower() for t in self.task_ids}
            records = [r for r in records if self._matches_filter(r, wanted)]
        if self.limit is not None:
            records = records[: self.limit]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        for rec in records:
            if rec.get("_kind") == "spa":
                assert schema_bytes is not None
                self._generate_spa(rec, schema_bytes)
            else:
                self._generate_core(rec)

    def _prepare_task_dir(self, tid: str) -> Path | None:
        dest = self.output_dir / tid
        if dest.exists():
            if not self.overwrite:
                print(f"skip {tid} (exists; use --overwrite)")
                return None
            shutil.rmtree(dest)
        shutil.copytree(TEMPLATE_DIR, dest)
        return dest

    @staticmethod
    def _append_dockerfile_downloads(dest: Path, downloads: list[tuple[str, str]]) -> None:
        if not downloads:
            return
        cmds = [
            f"curl -fsSL --retry 3 {shlex.quote(url)} -o {shlex.quote(target)}"
            for url, target in downloads
        ]
        dockerfile_path = dest / "environment" / "Dockerfile"
        dockerfile = dockerfile_path.read_text()
        dockerfile = dockerfile.rstrip() + "\nRUN " + " \\\n    && ".join(cmds) + "\n"
        dockerfile_path.write_text(dockerfile)

    def _render_toml(self, dest: Path, subs: dict[str, str]) -> None:
        toml = (dest / "task.toml").read_text()
        for k, v in subs.items():
            toml = toml.replace(k, v)
        (dest / "task.toml").write_text(toml)

    def _generate_core(self, rec: dict) -> None:
        tid = self.task_id(rec)
        dest = self._prepare_task_dir(tid)
        if dest is None:
            return

        docs = [d.strip() for d in rec["Document(s)"].splitlines() if d.strip() and d.strip().upper() != "N/A"]
        self._append_dockerfile_downloads(
            dest,
            [(f"{RAW_CORE}/{urllib.parse.quote(f'documents/{d}')}", f"/app/documents/{d}") for d in docs],
        )

        prompt = rec["Prompt"].strip()
        rubric = rec["Rubric"].strip() + "\n"
        num = str(int(rec["Number"]))
        summary = rec["Task"].strip().replace('"', "'")
        self._render_toml(
            dest,
            {
                "{task_id}": tid,
                "{artifact_path}": "/app/answer.md",
                "{description}": f"BigLaw Bench Core task {num}: {summary}",
                "{tag1}": "rubric",
                "{tag2}": "llm-judge",
                "{category_kw}": _slug(rec["Category"]),
                "{task_type_kw}": _slug(rec["Task Type"]),
                "{category}": rec["Category"].strip(),
                "{task_type}": rec["Task Type"].strip(),
            },
        )

        instr = (dest / "instruction.md").read_text()
        if docs:
            doc_block = (
                "The attached documents are available in `/app/documents/` (PDF files; `pdftotext` is installed):\n\n"
                + "\n".join(f"- `/app/documents/{d}`" for d in docs)
                + "\n\n"
            )
        else:
            doc_block = "No documents are attached; everything needed is in the request above.\n\n"
        instr = instr.replace("{prompt}", prompt).replace("{doc_block}", doc_block)
        (dest / "instruction.md").write_text(instr)
        (dest / "tests" / "rubric.md").write_text(rubric)

        authored = SOLUTIONS_DIR / f"{tid}.md"
        answer_text = authored.read_text(encoding="utf-8") if authored.is_file() else reference_answer(rubric, prompt)
        (dest / "solution" / "answer.md").write_text(answer_text)
        (dest / "solution" / "solve.sh").chmod(0o755)
        (dest / "tests" / "test.sh").chmod(0o755)
        print(f"generated {tid} ({len(docs)} docs)")

    def _generate_spa(self, rec: dict, schema_bytes: bytes) -> None:
        tid = self.task_id(rec)
        dest = self._prepare_task_dir(tid)
        if dest is None:
            return

        doc_name = rec["Documents"].strip()
        idx = int(rec["_index"])
        self._append_dockerfile_downloads(
            dest,
            [
                (f"{RAW_SPA}/{urllib.parse.quote(f'documents/{doc_name}')}", f"/app/documents/{doc_name}"),
                (f"{RAW_SPA}/schema.json", "/app/schema.json"),
            ],
        )

        self._render_toml(
            dest,
            {
                "{task_id}": tid,
                "{artifact_path}": "/app/answer.json",
                "{description}": f"BigLaw Bench Workflows SPA task {idx}: Extract 29 deal-point fields from {doc_name}",
                "{tag1}": "spa",
                "{tag2}": "extraction",
                "{category_kw}": "transactional",
                "{task_type_kw}": "spa-deal-points",
                "{category}": "Transactional",
                "{task_type}": "Workflows - SPA Deal Points",
            },
        )

        instruction = (
            "Extract all 29 deal-point fields from the Share Purchase Agreement (SPA) PDF into a single JSON file "
            "conforming to the schema at `/app/schema.json`.\n\n"
            "Available files (`pdftotext` is installed):\n"
            f"- SPA document: `/app/documents/{doc_name}`\n"
            "- Output JSON schema: `/app/schema.json`\n\n"
            "Requirements:\n"
            "- Populate every field in `/app/schema.json`, covering all 29 deal points (effective date, purchaser, "
            "seller, company, base purchase price, price per share, number of shares, closing deliverables, "
            "purchase price adjustments, shares outstanding, pro forma ownership percentage, other transaction "
            "agreements, buyer and seller indemnification survival/liability cap/basket, conditions to seller's "
            "and buyer's closing obligations, governing law, dispute resolution jurisdiction, buyer and seller "
            "termination rights, effect of termination, transfer taxes, fees and expenses, and buyer and "
            "seller/company notices).\n"
            '- Use `"N/A"` for string fields (or `[]` for array fields) when a term is not present or not applicable in the agreement.\n'
            "- Write valid JSON matching `/app/schema.json` to `/app/answer.json`.\n"
        )
        (dest / "instruction.md").write_text(instruction)

        gt = spa_row_to_json(rec)
        gt_json = json.dumps(gt, indent=2, ensure_ascii=False) + "\n"
        (dest / "solution" / "answer.json").write_text(gt_json)
        (dest / "solution" / "solve.sh").write_text(
            "#!/bin/bash\n"
            "# Oracle: copy the ground-truth SPA deal-point JSON into place.\n"
            "set -e\n"
            "mkdir -p /app\n"
            "cp /solution/answer.json /app/answer.json\n"
        )
        (dest / "solution" / "solve.sh").chmod(0o755)

        (dest / "tests" / "ground_truth.json").write_text(gt_json)
        (dest / "tests" / "test.sh").write_text(
            "#!/bin/bash\n"
            "mkdir -p /logs/verifier\n"
            "ANSWER=\"/app/answer.json\"\n"
            "if [ ! -f \"$ANSWER\" ] && [ -f \"/logs/artifacts/app/answer.json\" ]; then\n"
            "  ANSWER=\"/logs/artifacts/app/answer.json\"\n"
            "fi\n"
            "python3 /tests/judge.py --mode spa --ground-truth /tests/ground_truth.json --answer \"$ANSWER\" --out /logs/verifier/reward.txt\n"
            "status=$?\n"
            "if [ ! -f /logs/verifier/reward.txt ]; then\n"
            "  echo 0 > /logs/verifier/reward.txt\n"
            "fi\n"
            "exit $status\n"
        )
        (dest / "tests" / "test.sh").chmod(0o755)
        print(f"generated {tid} ({doc_name})")
