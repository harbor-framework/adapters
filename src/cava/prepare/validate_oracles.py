"""Score every oracle answer with the ported CAVA scorer (no audio/ASR needed).

Usage:
  python validate_oracles.py /path/to/CAVA          # oracles rebuilt from CAVA's record files
  python validate_oracles.py --manifests DIR        # oracles shipped in <subtask>.jsonl manifests
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src" / "cava" / "scoring"))
sys.path.insert(0, str(HERE))
from cava_score import score_record  # noqa: E402
from prepare_manifests import EXPECTED_COUNTS, PIPE, oracle_for  # noqa: E402


def records(cava: Path, subtask: str):
    files = {
        "deception_detection": "data/Werewolf/werewolf.jsonl",
        "jeopardy": "data/jeopardy/audio_inputs.jsonl",
        "multimodal_instruction_following": "data/MultimodalInstructionFollowing/audio_inputs.jsonl",
        "function_calling": f"data/function_calling_test/audio_inputs.jsonl_{PIPE}_function_calling",
        "jailbreak": "data/jailbreaking/jailbreak_persuasive/audio_inputs.jsonl",
    }
    lines = (cava / files[subtask]).read_text().splitlines()
    if subtask == "multimodal_instruction_following":
        lines = lines[:1000]
    return [json.loads(l) for l in lines]



SUBTASKS = ["deception_detection", "jeopardy", "multimodal_instruction_following",
            "function_calling", "jailbreak"]


def pairs(subtask: str):
    """(record, oracle) pairs from a manifest dir or rebuilt from a CAVA checkout."""
    if sys.argv[1] == "--manifests":
        path = Path(sys.argv[2]) / f"{subtask}.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        return [(r["record"], r["oracle"]) for r in rows]
    return [(rec, oracle_for(subtask, rec)) for rec in records(Path(sys.argv[1]), subtask)]


if __name__ == "__main__":
    ok_all = True
    for subtask in SUBTASKS:
        recs = pairs(subtask)
        fails = []
        for i, (rec, o) in enumerate(recs):
            c, t = score_record(subtask, rec, o["answer"], o.get("function_calls"))
            if c != t:
                fails.append((i, rec.get("instruction_id") or rec.get("filename"), o["answer"][:80]))
        if len(recs) != EXPECTED_COUNTS[subtask]:
            fails.append((None, f"{len(recs)} records, expected {EXPECTED_COUNTS[subtask]}", ""))
        ok_all &= not fails
        print(f"{subtask:34s} {len(recs) - len(fails)}/{len(recs)} oracle pass")
        for f in fails[:8]:
            print("   FAIL", f)
    sys.exit(0 if ok_all else 1)
