"""
Grades a single CAIBench task.

Reads the answer from /tests/expected.json (written per-task by the adapter) and the
agent's output from /logs/agent/, then writes a float reward to /logs/verifier/reward.txt.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXPECTED_PATH = Path("/tests/expected.json")
AGENT_LOGS_DIR = Path("/logs/agent")
REWARD_PATH = Path("/logs/verifier/reward.txt")

# ===================================================================
#  ported from CAI's benchmarks/cyberPII-bench/annotation_metrics.py
# ===================================================================

VALID_ENTITIES = {
    "PERSON",
    "PHONE_NUMBER",
    "LOCATION",
    "CREDIT_CARD",
    "CRYPTO",
    "IBAN_CODE",
    "IP_ADDRESS",
    "EMAIL_ADDRESS",
    "URL",
    "DATE_TIME",
    "NIF",
    "MEDICAL_LICENSE",
    "US_SSN",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_ITIN",
    "US_PASSPORT",
    "ORGANIZATION",
    "ADDRESS",
    "NRP",
    "DNI",
    "NIE",
    "IBAN",
    "EUROPEAN_BANK_ACCOUNT",
}


def find_entities_with_positions(text, skip_entities=set()):
    """
    Find entities marked with brackets and their positions in the text.
    Returns: List of (entity_type, start_pos, end_pos, full_tag)
    """
    if not isinstance(text, str):
        return []

    entities = []
    valid_entities = VALID_ENTITIES - set(skip_entities)
    pattern = r"\[({})\]".format("|".join(valid_entities))

    for match in re.finditer(pattern, text):
        entity_type = match.group(1)
        if entity_type not in skip_entities:
            start = match.start()
            end = match.end()
            full_tag = match.group(0)
            entities.append((entity_type, start, end, full_tag))

    return sorted(entities, key=lambda x: x[1])


# ======================================
#  ported from CAI's benchmarks/eval.py
# ======================================

def parse_result_seceval(result):
    # Expecting format: 'ANSWER: X', 'ANSWER: XY', or 'ANSWER: XYZ' (1, 2, or 3 letters A-D)
    if result is None:
        return None
    match = re.search(r"ANSWER:?\s*([A-D]{1,3})", result, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def parse_result_cybermetric(result):
    # Expecting format: 'ANSWER: X'
    if result is None:
        return None
    match = re.search(r"ANSWER:?\s*([A-D])", result, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def parse_result_cti_bench(result, dataset_file):
    # Accepts answers like 'ANSWER: X', 'ANSWER: XY', or 'ANSWER: XYZ' (A-D), and also 'ANSWER: Txxxx' (MITRE ATT&CK IDs)
    if result is None:
        return None
    # Try to match CWE IDs (e.g., CWE-416, CWE-79, etc.)
    if "cti-rcm" in dataset_file:
        cwe_match = re.search(r"(CWE-\d+)", result, re.IGNORECASE)
        if cwe_match:
            return cwe_match.group(1).upper()
    # Try to match A-D answers (1-3 letters)
    if "cti-mcq" in dataset_file:
        match = re.search(r"ANSWER:?\s*([A-D])", result, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    # Find all MITRE ATT&CK technique IDs (e.g., T1071, T1059, etc.) anywhere in the result
    if "cti-ate" in dataset_file:
        ids = re.findall(r"T\d{4}", result, re.IGNORECASE)
        if ids:
            # Return all found IDs as uppercase, comma-separated
            return ", ".join([x.upper() for x in ids])
    if "cti-vsp" in dataset_file:
        # Try to match CVSS vector strings (e.g., CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H)
        cvss_match = re.search(
            r"(CVSS:3\.1/AV:[NALP]/AC:[LH]/PR:[NLH]/UI:[NR]/S:[UC]/C:[NLH]/I:[NLH]/A:[NLH])",
            result,
            re.IGNORECASE,
        )
        if cvss_match:
            return cvss_match.group(1).upper()
        # Also accept vector without prefix
        vector_match = re.search(
            r"(AV:[NALP]/AC:[LH]/PR:[NLH]/UI:[NR]/S:[UC]/C:[NLH]/I:[NLH]/A:[NLH])",
            result,
            re.IGNORECASE,
        )
        if vector_match:
            return "CVSS:3.1/" + vector_match.group(1).upper()
        return result.upper()
    return None


def extract_cvss_score(vector):
    """
    Extracts a score from a CVSS vector string using the CVSS library.
    """
    try:
        from cvss import CVSS3

        c = CVSS3(vector)
        return c.scores()[0]
    except Exception as e:
        print(f"Error calculating CVSS score: {e}")
        return None


def compute_vsp_mad(results):
    """
    Compute Mean Absolute Deviation for CVSS scores, following the original implementation.
    """
    try:
        from cvss import CVSS3
    except ImportError:
        print("CVSS library not found. Please install it with 'pip install cvss'")
        return None

    cvss_prefix = "CVSS:3.1/"  # Use 3.1 to match current data
    error_sum = 0
    total = 0

    for item in results:
        gt = item.get("Solution")
        pred = item.get("ModelAnswer")

        try:
            # Parse prediction
            pred_vector = parse_result_cti_bench(pred, "cti-vsp")

            # Ensure vectors have prefix
            if pred_vector and not pred_vector.startswith("CVSS:"):
                pred_vector = cvss_prefix + pred_vector

            # Calculate scores
            if gt and pred_vector:
                c_gt = CVSS3(gt)
                c_pred = CVSS3(pred_vector)

                gt_score = c_gt.scores()[0]
                pred_score = c_pred.scores()[0]

                error = abs(pred_score - gt_score)
                error_sum += error
                total += 1
        except Exception as e:
            print(f"Error processing CVSS vector: {e}")
            continue

    return error_sum / total if total > 0 else None


def compute_ate_metrics(results):
    """
    Compute F1-macro score and accuracy for CTI-ATE task.

    For F1-macro, we calculate F1 separately for each sample and then average them.

    Args:
        results (list of dict): Each dict should have the ground truth answer and model answer.

    Returns:
        tuple: (f1_macro, accuracy, precision_macro, recall_macro)
    """
    # For storing per-sample metrics
    f1_scores = []
    precision_scores = []
    recall_scores = []

    correct_predictions = 0
    total_predictions = 0

    for item in results:
        gt = item.get("Solution", "")
        pred = item.get("ModelAnswer", "")

        # Extract technique IDs
        gt_ids = [tid.strip().upper() for tid in gt.split(",") if tid.strip()]
        pred_vector = parse_result_cti_bench(pred, "cti-ate")
        pred_ids = [tid.strip().upper() for tid in (pred_vector or "").split(",") if tid.strip()]

        # Calculate true positives, false positives, and false negatives for this sample
        sample_tp = len(set(gt_ids) & set(pred_ids))
        sample_fp = len(set(pred_ids) - set(gt_ids))
        sample_fn = len(set(gt_ids) - set(pred_ids))

        # Calculate precision and recall for this sample
        if sample_tp + sample_fp > 0:
            sample_precision = sample_tp / (sample_tp + sample_fp)
        else:
            sample_precision = 0

        if sample_tp + sample_fn > 0:
            sample_recall = sample_tp / (sample_tp + sample_fn)
        else:
            sample_recall = 0

        # Calculate F1 for this sample
        if sample_precision + sample_recall > 0:
            sample_f1 = 2 * (sample_precision * sample_recall) / (sample_precision + sample_recall)
        else:
            sample_f1 = 0

        # Add to list of scores
        precision_scores.append(sample_precision)
        recall_scores.append(sample_recall)
        f1_scores.append(sample_f1)

        # Calculate exact match for accuracy
        if set(gt_ids) == set(pred_ids):
            correct_predictions += 1
        total_predictions += 1

    # Calculate macro metrics (average of per-sample metrics)
    precision_macro = sum(precision_scores) / len(precision_scores) if precision_scores else 0
    recall_macro = sum(recall_scores) / len(recall_scores) if recall_scores else 0
    f1_macro = sum(f1_scores) / len(f1_scores) if f1_scores else 0
    accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0

    return f1_macro, accuracy, precision_macro, recall_macro

# ========================
#  end of ported CAI code
# ========================


def read_agent_output() -> str:
    for name in ("oracle.txt", "claude-code.txt", "gemini-cli.txt", "codex.txt", "output.txt"):
        path = AGENT_LOGS_DIR / name
        if path.is_file():
            return path.read_text(errors="replace")

    if AGENT_LOGS_DIR.is_dir():
        return "\n".join(p.read_text(errors="replace") for p in sorted(AGENT_LOGS_DIR.glob("*.txt")))

    return ""


def grade_cybermetric(output: str, solution: str) -> float:
    return 1.0 if parse_result_cybermetric(output) == solution.upper() else 0.0


def grade_seceval(output: str, solution: str) -> float:
    return 1.0 if parse_result_seceval(output) == solution.upper() else 0.0


def grade_cti_bench_mcq(output: str, solution: str) -> float:
    return 1.0 if parse_result_cti_bench(output, "cti-mcq.tsv") == solution.upper() else 0.0


def grade_cti_bench_ate(output: str, solution: str) -> float:
    return compute_ate_metrics([{"Solution": solution, "ModelAnswer": output}])[0]  # F1-macro score


def grade_cti_bench_rcm(output: str, solution: str) -> float:
    return 1.0 if parse_result_cti_bench(output, "cti-rcm.tsv") == solution.upper() else 0.0


def grade_cti_bench_vsp(output: str, solution: str) -> float:
    mad = compute_vsp_mad([{"Solution": solution, "ModelAnswer": output}])
    return max(0.0, 1.0 - mad / 10.0) if mad is not None else 0.0


def grade_cyberpii_bench(output: str, solution: str) -> float:
    gt_entities = {(t, s, e) for t, s, e, _ in find_entities_with_positions(solution)}
    pred_entities = {(t, s, e) for t, s, e, _ in find_entities_with_positions(output)}

    tp = len(gt_entities & pred_entities)

    precision = tp / len(pred_entities) if pred_entities else 0
    recall = tp / len(gt_entities) if gt_entities else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    f2 = 5 * (precision * recall) / (4 * precision + recall) if (precision + recall) > 0 else 0

    print(f"precision={precision:.4f}  recall={recall:.4f}  f1_score={f1:.4f}  f2_score={f2:.4f}")

    return f1


GRADERS = {
    "cybermetric": grade_cybermetric,
    "seceval": grade_seceval,
    "cti_bench_mcq": grade_cti_bench_mcq,
    "cti_bench_ate": grade_cti_bench_ate,
    "cti_bench_rcm": grade_cti_bench_rcm,
    "cti_bench_vsp": grade_cti_bench_vsp,
    "cyberpii_bench": grade_cyberpii_bench,
}


def main() -> int:
    expected = json.loads(EXPECTED_PATH.read_text())
    eval_type = expected["eval_type"]
    solution = expected["solution"]

    grader = GRADERS.get(eval_type)
    if grader is None:
        raise ValueError(f"Unknown eval_type: {eval_type}")

    output = read_agent_output()
    reward = grader(output, solution)

    REWARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REWARD_PATH.write_text(str(reward))
    print(f"eval_type={eval_type}  reward={reward}")

    return 0 if reward == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
