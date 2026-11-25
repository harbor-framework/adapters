"""Harbor adapter for AndroidWorld (google-research/android_world).

Task list comes from `tasks.json`, produced by `scripts/export_tasks.py` from the upstream
registry with a fixed seed scheme (see that script). One Harbor task per (task class, seed).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "task-template"
TASKS_JSON = Path(__file__).parent / "tasks.json"

# Oracle kinds (handlers + method in task-template/environment/aw/oracles.py KINDS).
def _k(kind: str, *names: str) -> dict[str, str]:
    return {n: kind for n in names}


ORACLE_KINDS: dict[str, str] = {
    **_k("system_toggle", "SystemWifiTurnOn", "SystemWifiTurnOff", "SystemWifiTurnOnVerify",
         "SystemWifiTurnOffVerify", "SystemBluetoothTurnOn", "SystemBluetoothTurnOff",
         "SystemBluetoothTurnOnVerify", "SystemBluetoothTurnOffVerify", "SystemBrightnessMax",
         "SystemBrightnessMin", "SystemBrightnessMaxVerify", "SystemBrightnessMinVerify",
         "TurnOffWifiAndTurnOnBluetooth"),
    **_k("system_clipboard", "SystemCopyToClipboard"),
    **_k("system_open_app", "OpenAppTaskEval", "TurnOnWifiAndOpenApp"),
    **_k("files_delete", "FilesDeleteFile", "MarkorDeleteNote"),
    **_k("files_move", "FilesMoveFile", "MarkorMoveNote"),
    **_k("markor_create_folder", "MarkorCreateFolder"),
    **_k("markor_delete_all", "MarkorDeleteAllNotes"),
    **_k("markor_delete_newest", "MarkorDeleteNewestNote"),
    **_k("markor_create_note", "MarkorCreateNote"),
    **_k("markor_create_file", "MarkorCreateNoteFromClipboard", "MarkorTranscribeReceipt",
         "MarkorTranscribeVideo"),
    **_k("markor_edit_note", "MarkorEditNote"),
    **_k("markor_change_content", "MarkorChangeNoteContent"),
    **_k("markor_add_header", "MarkorAddNoteHeader"),
    **_k("markor_merge", "MarkorMergeNotes"),
    **_k("markor_note_and_sms", "MarkorCreateNoteAndSms"),
    **_k("sql_add", "ExpenseAddSingle", "ExpenseAddMultiple", "ExpenseAddMultipleFromMarkor",
         "ExpenseAddMultipleFromGallery", "RecipeAddSingleRecipe", "RecipeAddMultipleRecipes",
         "RecipeAddMultipleRecipesFromMarkor", "RecipeAddMultipleRecipesFromMarkor2",
         "RecipeAddMultipleRecipesFromImage", "SimpleCalendarAddOneEvent",
         "SimpleCalendarAddOneEventInTwoWeeks", "SimpleCalendarAddOneEventRelativeDay",
         "SimpleCalendarAddOneEventTomorrow", "SimpleCalendarAddRepeatingEvent"),
    **_k("sql_delete", "ExpenseDeleteSingle", "ExpenseDeleteMultiple", "ExpenseDeleteMultiple2",
         "RecipeDeleteSingleRecipe", "RecipeDeleteSingleWithRecipeWithNoise",
         "RecipeDeleteMultipleRecipes", "RecipeDeleteMultipleRecipesWithNoise",
         "RecipeDeleteMultipleRecipesWithConstraint", "SimpleCalendarDeleteEvents",
         "SimpleCalendarDeleteOneEvent", "SimpleCalendarDeleteEventsOnRelativeDay"),
    **_k("sql_delete_duplicate", "ExpenseDeleteDuplicates", "ExpenseDeleteDuplicates2",
         "RecipeDeleteDuplicateRecipes", "RecipeDeleteDuplicateRecipes2",
         "RecipeDeleteDuplicateRecipes3"),
    **_k("sms_send", "SimpleSmsSend", "SimpleSmsReply", "SimpleSmsReplyMostRecent",
         "SimpleSmsResend", "SimpleSmsSendClipboardContent", "SimpleSmsSendReceivedAddress"),
    **_k("contacts_add", "ContactsAddContact"),
    **_k("contacts_draft", "ContactsNewContactDraft"),
    **_k("clock_stopwatch_running", "ClockStopWatchRunning"),
    **_k("clock_stopwatch_paused", "ClockStopWatchPausedVerify"),
    **_k("clock_timer_entry", "ClockTimerEntry"),
    **_k("browser_maze", "BrowserMaze"),
    **_k("browser_multiply", "BrowserMultiply"),
    **_k("browser_draw", "BrowserDraw"),
    **_k("retro_playlist", "RetroCreatePlaylist", "RetroSavePlaylist", "RetroPlaylistDuration"),
    **_k("retro_queue", "RetroPlayingQueue"),
    **_k("vlc_playlists", "VlcCreatePlaylist", "VlcCreateTwoPlaylists"),
    **_k("osmand_favorite", "OsmAndFavorite"),
    **_k("osmand_marker", "OsmAndMarker"),
    **_k("osmand_track", "OsmAndTrack"),
    **_k("camera_photo", "CameraTakePhoto"),
    **_k("camera_video", "CameraTakeVideo"),
    **_k("audio_record", "AudioRecorderRecordAudio", "AudioRecorderRecordAudioWithFileName"),
    **_k("gallery_copy", "SaveCopyOfReceiptTaskEval"),
    **_k("draw_create", "SimpleDrawProCreateDrawing"),
}
ANSWER_FAMILY = "abc"  # information-retrieval tasks (module `abc`): answer is checked, not state


def oracle_kind(t: dict) -> str:
    if t["family"] == ANSWER_FAMILY:
        return "answer"
    return ORACLE_KINDS.get(t["name"], "none")


def _oracle_methods() -> dict[str, str]:
    """kind -> method (computed / injection / ui-script), read from the oracle module."""
    import importlib.util

    p = TEMPLATE_DIR / "environment" / "aw" / "oracles.py"
    spec = importlib.util.spec_from_file_location("aw_oracles", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {k: m for k, (_h, m) in mod.KINDS.items()}


def task_id(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", name)
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def difficulty(c: float) -> str:
    return "easy" if c <= 1.5 else "medium" if c <= 3.5 else "hard"


def parity_subset(tasks: list[dict], per_family: int = 2) -> list[dict]:
    """Deterministic stratified subset: up to `per_family` tasks per app family, ordered by
    sha256(name). Proposal only; confirm with the Harbor-Index team before running parity."""
    by_fam: dict[str, list[dict]] = {}
    for t in tasks:
        by_fam.setdefault(t["family"], []).append(t)
    out = []
    for fam in sorted(by_fam):
        ts = sorted(by_fam[fam], key=lambda t: hashlib.sha256(t["name"].encode()).hexdigest())
        out += ts[:per_family]
    return sorted(out, key=lambda t: t["name"])


class AndroidWorldAdapter:
    def __init__(
        self,
        output_dir: Path,
        limit: int | None = None,
        overwrite: bool = False,
        task_ids: list[str] | None = None,
        split: str = "full",
        **kwargs,
    ):
        self.output_dir = Path(output_dir)
        self.limit = limit
        self.overwrite = overwrite
        self.task_ids = task_ids
        self.split = split

    def _select(self) -> list[dict]:
        tasks = json.loads(TASKS_JSON.read_text())
        methods = _oracle_methods()
        for t in tasks:
            t["oracle"] = oracle_kind(t)
            if t["oracle"] not in methods:
                raise ValueError(f"no oracle implemented for {t['name']}")
            t["oracle_method"] = methods[t["oracle"]]
            t["id"] = task_id(t["name"])
        if self.split == "parity":
            tasks = parity_subset(tasks)
        elif self.split != "full":
            raise ValueError(f"unknown split {self.split!r}")
        if self.task_ids:
            wanted = {x.lower() for x in self.task_ids}
            tasks = [t for t in tasks if t["id"] in wanted or t["name"].lower() in wanted]
        if self.limit is not None:
            tasks = tasks[: self.limit]
        return tasks

    def _render(self, text: str, mapping: dict[str, str]) -> str:
        for k, v in mapping.items():
            text = text.replace("{" + k + "}", v)
        return text

    def _generate(self, t: dict) -> None:
        dest = self.output_dir / t["id"]
        if dest.exists():
            if not self.overwrite:
                print(f"skip existing {dest}")
                return
            shutil.rmtree(dest)
        shutil.copytree(TEMPLATE_DIR, dest)
        answer_task = t["family"] == ANSWER_FAMILY
        answer_note = (
            "- This task asks a question. Write ONLY your final answer, exactly in the format "
            "requested, to `/workspace/answer.txt` (multiple answers separated by commas).\n"
            if answer_task
            else ""
        )
        m = {
            "task_id": t["id"],
            "class_name": t["name"],
            "seed": str(t["seed"]),
            "family": t["family"],
            "difficulty": difficulty(t["complexity"]),
            "oracle_kind": t["oracle"],
            "oracle_method": t["oracle_method"],
            "goal": t["goal"],
            "answer_note": answer_note,
        }
        for rel in ("task.toml", "instruction.md"):
            p = dest / rel
            p.write_text(self._render(p.read_text(), m))
        spec = {
            k: t[k]
            for k in ("name", "module", "family", "seed", "goal", "complexity", "params_pickle_b64", "params_repr")
        }
        spec.update(oracle=t["oracle"], oracle_method=t["oracle_method"], answer_task=answer_task)
        (dest / "environment" / "task_spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n")

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        tasks = self._select()
        for t in tasks:
            self._generate(t)
        print(f"Generated {len(tasks)} tasks (split={self.split}) in {self.output_dir}")
