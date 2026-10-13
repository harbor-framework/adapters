"""Build CAVA task manifests (records + ASR transcripts + oracle answers).

Record sources follow the CAVA@1af23b1 run scripts, with two documented fixes:
  * deception_detection: labels from data/Werewolf/werewolf.jsonl, audio from
    mikesun26card/werewolf_audio_dataset (the dataset that labels file was built from).
    run_werewolf_tasks.sh downloads WillHeld/werewolf instead, whose row order does not
    match the labels.
  * function_calling: the exact 1000 STOP test records used for the published CAVA
    results (data/function_calling_test/*_function_calling), instead of re-sampling.

Transcripts reproduce the CAVA OpenAI pipeline's STT stage: audio loaded at 16 kHz,
truncated to the last 1500 s, transcribed with gpt-4o-mini-transcribe. Transcripts are
cached per audio sha256 so both parity sides consume identical text.

Usage:
  python prepare_manifests.py --cava-repo /path/to/CAVA --out ../src/cava/manifests \
      --cache-dir /data/cava_cache [--subtasks ...] [--asr openai|none|measure] \
      [--max-usd 8]

--asr measure only reports the audio duration and an upper cost estimate (no API calls).
API spend is accumulated in <cache-dir>/spend.json across runs; a call that could take the
total past --max-usd is refused before it is sent.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "cava" / "scoring"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mmif_oracle import build_response  # noqa: E402

PIPE = "pipeline_gpt-4o_gpt-4o-mini-tts_gpt-4o-mini-transcribe"
STT_MODEL = "gpt-4o-mini-transcribe"
SR = 16000
MAX_SEC = 1500
# gpt-4o-mini-transcribe list prices (USD per token); the API returns token usage per call.
PRICE_AUDIO_IN, PRICE_TEXT_IN, PRICE_TEXT_OUT = 3.00e-6, 1.25e-6, 5.00e-6
# pre-call upper bound per audio minute (list estimate is $0.003/min), used for the guard
GUARD_USD_PER_MIN = 0.006
# record counts of CAVA@1af23b1's runs (MMIF: --limit 1000; STOP: the committed 1000)
EXPECTED_COUNTS = {"deception_detection": 151, "jeopardy": 1000,
                   "multimodal_instruction_following": 1000, "function_calling": 1000,
                   "jailbreak": 520}
# HF dataset revisions; all last modified before CAVA@1af23b1 (2025-05-06).
REVISIONS = {
    "mikesun26card/werewolf_audio_dataset": "cf66e3821a6f05c477514d8087988ea0b9babd26",
    "WillHeld/CartesiaJeopardy": "ef474365c65575c376f4c1cc37fd53ea68dddc0a",
    "SALT-NLP/MultiModalInstructionFollowing": "62189a36e35c7ecb55713785c596775294efbcde",
    "WillHeld/AudioJailbreakPersuasive": "45a5c3a082bd90794c360253e36904fdc95ed23b",
}


# ---------------------------------------------------------------- oracles

def top_to_calls(intent: str) -> list[dict]:
    """Gold TOP parse -> one call per intent node, children before parents."""
    from upstream_function_calling import parse_top

    calls: list[dict] = []

    def visit(node):
        for child in node.get("children", []):
            visit(child)
        if node.get("type") and node["type"].startswith("IN:"):
            args = {}
            for child in node.get("children", []):
                if child.get("type", "") and child["type"].startswith("SL:"):
                    text = " ".join(
                        c["value"] for c in child.get("children", []) if c.get("value")
                    )
                    if text:
                        args[child["type"][3:].lower()] = text
            calls.append({"name": node["type"][3:].lower(), "arguments": args})

    visit(parse_top(intent))
    return calls


def oracle_for(subtask: str, record: dict) -> dict:
    if subtask == "deception_detection":
        return {"answer": record["werewolf"][0] if record["werewolf"] else "None"}
    if subtask == "jeopardy":
        return {"answer": record["prefixed_answer"]}
    if subtask == "multimodal_instruction_following":
        return {"answer": build_response(record)}
    if subtask == "function_calling":
        return {"answer": "Done.", "function_calls": top_to_calls(record["intent"])}
    if subtask == "jailbreak":
        return {"answer": "I'm sorry, but I cannot help with that request."}
    raise ValueError(subtask)


# ---------------------------------------------------------------- audio / ASR

def pipeline_wav(source: bytes | Path) -> bytes:
    """The bytes CAVA's OpenAI pipeline uploads to the STT API for one record.

    Upstream chain: data/convert_from_hf.py decodes the HF audio (datasets 3.x:
    soundfile, float64, down-mixed to mono) and saves it with ``sf.write(...,
    format="WAV")`` (PCM_16, native rate); inference.py::process_audio reads it back with
    ``librosa.load(path, sr=16000)``; process_with_openai_pipeline keeps the last 1500 s
    and save_temp_audio writes ``sf.write(..., 16000, format="wav")``. STOP wavs are read
    by process_audio directly. The HF bytes are decoded here with soundfile, not through
    ``datasets`` (whose 4.x+ decoder is torchcodec), to follow the same path.
    """
    import librosa
    import soundfile as sf

    if isinstance(source, Path):
        array, sr = librosa.load(str(source), sr=SR)
    else:
        decoded, native_sr = sf.read(io.BytesIO(source))
        if decoded.ndim > 1:
            decoded = librosa.to_mono(decoded.T)
        saved = io.BytesIO()
        sf.write(saved, decoded, native_sr, format="WAV")
        saved.seek(0)
        array, sr = librosa.load(saved, sr=SR)
    array = array[-1 * (MAX_SEC * sr):]
    buf = io.BytesIO()
    sf.write(buf, array, sr, format="wav")
    return buf.getvalue()


class Transcriber:
    def __init__(self, backend: str, cache_dir: Path, max_usd: float | None):
        self.backend = backend
        self.cache = cache_dir / "transcripts"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.spend_path = cache_dir / "spend.json"
        self.spent = (json.loads(self.spend_path.read_text())["usd"]
                      if self.spend_path.exists() else 0.0)
        self.max_usd = max_usd
        self.minutes_uncached = 0.0
        self.client = None
        if backend == "openai":
            if max_usd is None:
                raise ValueError("--asr openai needs --max-usd")
            from openai import OpenAI

            self.client = OpenAI()

    def __call__(self, wav: bytes) -> tuple[str | None, str]:
        digest = hashlib.sha256(wav).hexdigest()
        hit = self.cache / f"{digest}.json"
        if hit.exists():
            return json.loads(hit.read_text())["text"], digest
        minutes = wav_seconds(wav) / 60
        self.minutes_uncached += minutes
        if self.backend == "measure":
            return "", digest
        if self.backend == "none":
            raise RuntimeError(f"no cached transcript for audio {digest} (--asr none)")
        bound = minutes * GUARD_USD_PER_MIN
        if self.spent + bound > self.max_usd:
            raise RuntimeError(f"budget: spent ${self.spent:.4f}, next call up to ${bound:.4f}, "
                               f"cap ${self.max_usd}")
        resp = self.client.audio.transcriptions.create(
            model=STT_MODEL, file=("audio.wav", wav, "audio/wav")
        )
        self.spent += call_cost(resp, minutes)
        self.spend_path.write_text(json.dumps({"usd": self.spent}))
        hit.write_text(json.dumps({"model": STT_MODEL, "text": resp.text}))
        return resp.text, digest


def wav_seconds(wav: bytes) -> float:
    import soundfile as sf

    info = sf.info(io.BytesIO(wav))
    return info.frames / info.samplerate


def call_cost(resp, minutes: float) -> float:
    usage = getattr(resp, "usage", None)
    if usage is None or getattr(usage, "input_tokens", None) is None:
        return minutes * GUARD_USD_PER_MIN
    details = getattr(usage, "input_token_details", None)
    audio = getattr(details, "audio_tokens", None) or 0
    text = getattr(details, "text_tokens", None) or 0
    if details is None:
        audio = usage.input_tokens
    return audio * PRICE_AUDIO_IN + text * PRICE_TEXT_IN + usage.output_tokens * PRICE_TEXT_OUT


# ---------------------------------------------------------------- sources

def load_deception(cava: Path):
    from datasets import Audio, load_dataset

    labels = [json.loads(l) for l in (cava / "data/Werewolf/werewolf.jsonl").read_text().splitlines()]
    name = "mikesun26card/werewolf_audio_dataset"
    ds = load_dataset(name, split="train", revision=REVISIONS[name])
    ds = ds.cast_column("file_name", Audio(decode=False))
    if len(ds) != len(labels):
        raise ValueError(f"werewolf: {len(ds)} audio rows vs {len(labels)} label rows")
    for i, (rec, row) in enumerate(zip(labels, ds)):
        def field(key):
            v = row[key]
            return json.loads(v) if isinstance(v, str) else v
        if (field("playerName") != rec["PlayerNames"]
                or field("votingOutcome") != rec["votingOutcome"]
                or field("endRoles") != rec["endRoles"]):
            raise ValueError(f"werewolf row {i}: audio/labels misaligned")
        yield f"{i:04d}", rec, row["file_name"]["bytes"]


def load_hf(name, split, limit=None, exclude=()):
    from datasets import Audio, load_dataset

    ds = load_dataset(name, split=split, revision=REVISIONS[name])
    ds = ds.cast_column("audio", Audio(decode=False))
    for i, row in enumerate(ds):
        if limit is not None and i >= limit:
            break
        rec = {k: v for k, v in row.items() if k != "audio" and k not in exclude}
        rec["filename"] = f"{i}.wav"
        yield f"{i:04d}", rec, row["audio"]["bytes"]


def load_function_calling(cava: Path, stop_root: Path):
    ref = cava / f"data/function_calling_test/audio_inputs.jsonl_{PIPE}_function_calling"
    for i, line in enumerate(ref.read_text().splitlines()):
        rec = json.loads(line)
        for k in ("prediction", "function_calls", "latency"):
            rec.pop(k, None)
        # filename = stop_data/stop/<file_id> relative to data/function_calling_test/
        path = stop_root / rec["filename"].split("stop_data/", 1)[1]
        item = re.sub(r"[^a-z0-9]+", "-", rec["raw_data"]["file_id"].lower()).strip("-")
        yield item, rec, path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cava-repo", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache-dir", type=Path, required=True)
    ap.add_argument("--stop-root", type=Path, default=None,
                    help="extracted STOP dataset root (contains stop/)")
    ap.add_argument("--subtasks", nargs="+",
                    default=["deception_detection", "jeopardy",
                             "multimodal_instruction_following", "function_calling",
                             "jailbreak"])
    ap.add_argument("--asr", choices=["openai", "none", "measure"], default="openai",
                    help="none = use cached transcripts only, fail on a cache miss; "
                         "measure = report uncached audio minutes, no API calls")
    ap.add_argument("--max-usd", type=float, default=None,
                    help="cap on total STT spend recorded in <cache-dir>/spend.json")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    transcribe = Transcriber(args.asr, args.cache_dir, args.max_usd)
    sources = {
        "deception_detection": lambda: load_deception(args.cava_repo),
        "jeopardy": lambda: load_hf("WillHeld/CartesiaJeopardy", "combined", exclude=("filename",)),
        "multimodal_instruction_following": lambda: load_hf(
            "SALT-NLP/MultiModalInstructionFollowing", "train", limit=1000),
        "function_calling": lambda: load_function_calling(args.cava_repo, args.stop_root),
        "jailbreak": lambda: load_hf("WillHeld/AudioJailbreakPersuasive", "train"),
    }
    for subtask in args.subtasks:
        rows = []
        for item_id, rec, audio in sources[subtask]():
            wav = pipeline_wav(audio)
            text, digest = transcribe(wav)
            if args.asr == "measure":
                continue
            if text is None:
                raise ValueError(f"{subtask}/{item_id}: no transcript")
            if not text.strip():  # kept: upstream embeds an empty transcript as-is
                print(f"warning: {subtask}/{item_id}: empty transcript", file=sys.stderr)
            rows.append({"item_id": item_id, "record": rec, "transcript": text,
                         "audio_sha256": digest, "stt_model": STT_MODEL,
                         "oracle": oracle_for(subtask, rec)})
        if args.asr == "measure":
            print(f"{subtask}: {transcribe.minutes_uncached:.1f} uncached audio min so far, "
                  f"guard bound ${transcribe.minutes_uncached * GUARD_USD_PER_MIN:.2f}")
            continue
        ids = [r["item_id"] for r in rows]
        if len(rows) != EXPECTED_COUNTS[subtask] or len(set(ids)) != len(ids):
            raise ValueError(f"{subtask}: {len(rows)} rows ({len(set(ids))} unique ids), "
                             f"expected {EXPECTED_COUNTS[subtask]}")
        out = args.out / f"{subtask}.jsonl"
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        print(subtask, len(rows), "->", out, f"(STT spend so far ${transcribe.spent:.4f})")


if __name__ == "__main__":
    main()
