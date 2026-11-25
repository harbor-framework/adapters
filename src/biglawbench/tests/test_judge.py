"""Unit tests for the BigLawBench verifier (blb-core rubric scorer + blb-spa 29-field scorer)."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "biglawbench"
TESTS_DIR = ROOT / "task-template" / "tests"

judge_spec = importlib.util.spec_from_file_location("judge", TESTS_DIR / "judge.py")
judge = importlib.util.module_from_spec(judge_spec)
sys.modules["judge"] = judge
judge_spec.loader.exec_module(judge)

adapter_spec = importlib.util.spec_from_file_location("blb_adapter", ROOT / "adapter.py")
blb_adapter = importlib.util.module_from_spec(adapter_spec)
sys.modules["blb_adapter"] = blb_adapter
adapter_spec.loader.exec_module(blb_adapter)

RUBRIC = """Affirmative Points:

1. Structure:
        a. Does the response give background? (1 point)
2. Substance:
        a. Does the response state X? (2 points)
        b. Does the response state Y? (1 point)

Negative Points:

1. -1 point for every hallucination
2. -0.5 points for every statement of accurate but extraneous or irrelevant information
"""


def _sample_spa_gt() -> dict:
    return {
        "effective_date": "2021-03-08",
        "purchaser": {"name": "HealthEquity, Inc.", "entity_type": "corporation", "jurisdiction": "Delaware"},
        "seller": {"name": "Seller Corp.", "entity_type": "corporation", "jurisdiction": "Delaware"},
        "company": {"name": "Target Co.", "entity_type": "corporation", "jurisdiction": "Washington"},
        "price": {
            "base_purchase_price": "$50,000,000.00",
            "price_per_share": "N/A",
            "number_of_shares": "13,316,799",
        },
        "closing_deliverables": ["Share Certificates", "FIRPTA Certificate"],
        "purchase_price_adjustments": "Final Consideration Adjustment\nEarn-Out",
        "capitalization": {
            "shares_outstanding": "13,316,799",
            "pro_forma_percentage": "100%",
        },
        "transaction_agreements": ["Escrow Agreement"],
        "indemnification": {
            "by_buyer": {"survival": "12 months", "liability_cap": "$250,000", "basket": "$250,000"},
            "by_seller": {"survival": "12 months", "liability_cap": "$50,000,000", "basket": "$250,000"},
        },
        "conditions_to_sellers_obligations": ["HSR waiting period expired"],
        "conditions_to_buyers_obligations": ["HSR waiting period expired", "No Company MAE"],
        "governing_law": "Delaware",
        "dispute_resolution_jurisdiction": "Court of Chancery of the State of Delaware",
        "termination_rights": {"by_buyer": "Mutual written consent", "by_seller": "N/A"},
        "effect_of_termination": ["Agreement becomes void except survival provisions"],
        "transfer_taxes": "Transfer Taxes split equally between Buyer and Seller",
        "fees_and_expenses": "Each party pays their own expenses",
        "notices": {"to_buyer": "HealthEquity, Inc., Draper, UT", "to_seller_or_company": "Seller Corp., Seattle, WA"},
    }


def test_parse():
    pos, neg = judge.parse_rubric(RUBRIC)
    assert [p["points"] for p in pos] == [1, 2, 1]
    assert [n["penalty"] for n in neg] == [1, 0.5]


def test_scores():
    pos, neg = judge.parse_rubric(RUBRIC)
    allv = {"criteria": {"p1": True, "p2": True, "p3": True}, "negatives": {"n1": 0, "n2": 0}}
    assert judge.compute_score(pos, neg, allv) == 1.0
    part = {"criteria": {"p1": True, "p2": False, "p3": True}, "negatives": {"n1": 1, "n2": 1}}
    assert judge.compute_score(pos, neg, part) == 0.125


def test_partial_and_clamp():
    pos, neg = judge.parse_rubric(RUBRIC)
    v = {"criteria": {"p1": True, "p2": True, "p3": False}, "negatives": {"n1": 1, "n2": 0}}
    assert judge.compute_score(pos, neg, v) == (3 - 1) / 4
    v = {"criteria": {}, "negatives": {"n1": 5}}
    assert judge.compute_score(pos, neg, v) == 0.0


def test_core_main_mocked(tmp_path, monkeypatch):
    rubric_p = tmp_path / "rubric.md"
    answer_p = tmp_path / "answer.md"
    out_p = tmp_path / "reward.txt"
    rubric_p.write_text(RUBRIC)
    answer_p.write_text("Background. X and Y.")
    monkeypatch.setattr(
        sys, "argv",
        ["judge.py", "--mode", "core", "--rubric", str(rubric_p), "--answer", str(answer_p), "--out", str(out_p)],
    )
    rc = judge.main(judge=lambda _p: {"criteria": {"p1": True, "p2": True, "p3": True}, "negatives": {"n1": 0, "n2": 0}})
    assert rc == 0
    assert float(out_p.read_text().strip()) == 1.0


def test_spa_field_count():
    assert len(judge.SPA_FIELDS) == 29


def test_spa_exact_and_normalized_no_judge():
    gt = _sample_spa_gt()
    pred = json.loads(json.dumps(gt))
    pred["effective_date"] = "03/08/2021"
    pred["purchaser"] = {"name": "HealthEquity, Inc.", "entity_type": "Delaware corporation", "jurisdiction": "Delaware"}
    pred["price"]["base_purchase_price"] = "$50000000"
    pred["price"]["price_per_share"] = ""
    pred["closing_deliverables"] = ["- FIRPTA Certificate", "Share Certificates"]
    pred["termination_rights"]["by_seller"] = "None"

    def fail_if_called(_prompt):
        raise AssertionError("Judge should not be called when all 29 fields match deterministically")

    score, results = judge.score_spa(gt, pred, judge=fail_if_called)
    assert score == 1.0
    assert all(results.values())


def test_spa_llm_fallback_and_partial_score():
    gt = _sample_spa_gt()
    pred = json.loads(json.dumps(gt))
    pred["transfer_taxes"] = "Buyer and Seller share all transfer taxes 50/50."
    pred["fees_and_expenses"] = "Buyer pays all seller transaction costs."
    pred["governing_law"] = ""  # missing/empty when GT has "Delaware" -> deterministic False

    calls = []

    def mock_judge(prompt):
        calls.append(prompt)
        return {
            "fields": {
                "transfer_taxes": True,
                "fees_and_expenses": False,
            }
        }

    score, results = judge.score_spa(gt, pred, judge=mock_judge)
    assert len(calls) == 1
    assert results["transfer_taxes"] is True
    assert results["fees_and_expenses"] is False
    assert results["governing_law"] is False
    assert abs(score - (27 / 29)) < 1e-9


def test_spa_main_invalid_or_missing_json(tmp_path, monkeypatch):
    gt_p = tmp_path / "gt.json"
    ans_p = tmp_path / "answer.json"
    out_p = tmp_path / "reward.txt"
    gt_p.write_text(json.dumps(_sample_spa_gt()))

    # Missing answer
    monkeypatch.setattr(
        sys, "argv",
        ["judge.py", "--mode", "spa", "--ground-truth", str(gt_p), "--answer", str(ans_p), "--out", str(out_p)],
    )
    assert judge.main(judge=lambda _p: {}) == 0
    assert float(out_p.read_text().strip()) == 0.0

    # Invalid JSON
    ans_p.write_text("{not valid json")
    assert judge.main(judge=lambda _p: {}) == 0
    assert float(out_p.read_text().strip()) == 0.0


def test_spa_row_to_json_conversion():
    row = {
        "Documents": "Example.pdf",
        "Effective Date": "2021-03-08",
        "Purchaser (Name + entity type)": "Acme Corp. (Delaware corporation)",
        "Seller (name + entity)": "Stockholders identified on Schedule A (not in the pdf)",
        "Company (Name, jurisdiction and entity type)": "Target LLC (California limited liability company)",
        "Base Purchase Price": "$10,000,000",
        "Price Per Share": "N/A",
        "Number of Shares": "1000",
        "Closing Deliverables List": "Share Certificates\nFIRPTA Certificate",
        "Post-Closing Payments Adjustments": "Working capital adjustment",
        "Shares Outstanding": "1000",
        "Pro Forma Ownership Percentage": "100%",
        "List of Other Transaction Agreements": "Escrow Agreement",
        "Indemnification by Buyer Survival Period": "12 months",
        "Indemnification by Buyer Liability Cap": "$1M",
        "Indemnification by Buyer Basket": "$100K",
        "Indemnification by Seller or Company Survival Period": "12 months",
        "Indemnification by Seller or Company  Liability Cap": "$1M",
        "Indemnification by Seller or Company  Basket": "$100K",
        "Conditions Precedent to Closing Transaction": "Mutual:\nHSR expired\n\nBuyer:\nNo MAE\n\nSeller:\nBuyer cert",
        "Governing Law": "Delaware",
        "Dispute Resolution Jurisdiction": "Delaware courts",
        "Termination Rights by Buyer": "Mutual consent",
        "Termination Rights by Seller": "Mutual consent",
        "Effect of Termination": "Void except survival",
        "Transfer Taxes": "Split 50/50",
        "Fees and Expenses": "Each pays own",
        "Notices to Buyer": "Acme Corp.",
        "Notices to Seller/Company": "Target LLC",
    }
    parsed = blb_adapter.spa_row_to_json(row)
    assert parsed["purchaser"] == {"name": "Acme Corp.", "entity_type": "corporation", "jurisdiction": "Delaware"}
    assert parsed["seller"]["name"] == "Stockholders identified on Schedule A (not in the pdf)"
    assert parsed["seller"]["entity_type"] == "N/A"
    assert parsed["company"] == {"name": "Target LLC", "entity_type": "limited liability company", "jurisdiction": "California"}
    assert parsed["conditions_to_buyers_obligations"] == ["HSR expired", "No MAE"]
    assert parsed["conditions_to_sellers_obligations"] == ["HSR expired", "Buyer cert"]
    score, _ = judge.score_spa(parsed, parsed)
    assert score == 1.0


def test_all_generated_tasks_if_present():
    ds_root = Path(__file__).resolve().parents[4] / "datasets" / "biglawbench"
    if not ds_root.is_dir():
        return
    for f in ds_root.glob("blb-core-*/tests/rubric.md"):
        pos, neg = judge.parse_rubric(f.read_text())
        assert pos and len(neg) == 2
    for f in ds_root.glob("blb-spa-*/tests/ground_truth.json"):
        gt = json.loads(f.read_text())
        score, results = judge.score_spa(gt, gt)
        assert score == 1.0 and len(results) == 29
