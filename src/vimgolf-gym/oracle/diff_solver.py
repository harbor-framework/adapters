"""Deterministic line/char-diff edit script generator for VimGolf oracles.

Edits the buffer bottom-up (so line numbers stay valid) with normal-mode commands and
finishes with ZZ. Output still has to be replay-verified by build_oracles.py.
"""

import difflib

from vimgolf.vimgolf import format_


def esc_text(t: str) -> str:
    # literal text typed in insert mode; '<' must be written as <lt> for the tokenizer
    return t.replace("<", "<lt>")


def goto(n: int) -> str:
    return f"{n}G" if n > 1 else "gg"


def edit_line(n: int, old: str, new: str) -> str:
    p = 0
    while p < min(len(old), len(new)) and old[p] == new[p]:
        p += 1
    s = 0
    while s < min(len(old), len(new)) - p and old[-1 - s] == new[-1 - s]:
        s += 1
    mid_old = len(old) - p - s
    mid_new = new[p:len(new) - s]
    keys = goto(n) + "0" + (f"{p}l" if p else "")
    if mid_old == 0:
        if p >= len(old):
            keys = goto(n) + "A"
        else:
            keys += "i"
        return keys + esc_text(mid_new) + "<Esc>"
    if not mid_new:
        return keys + f"{mid_old}x"
    return keys + f"{mid_old}s" + esc_text(mid_new) + "<Esc>"


def open_lines(after: int, lines: list[str]) -> str:
    # insert new lines after line `after` (0 = before first line); 0<C-D> kills autoindent
    if after == 0:
        keys = "ggO"
    else:
        keys = goto(after) + "o"
    parts = []
    for i, ln in enumerate(lines):
        parts.append(("0<C-D>" if i == 0 or True else "") + esc_text(ln))
    return keys + "<CR>".join(parts) + "<Esc>"


def solve(inp: str, out: str) -> str:
    a = format_(inp).split("\n")[:-1]
    b = format_(out).split("\n")[:-1]
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    keys = []
    for tag, i1, i2, j1, j2 in reversed(ops):
        if tag == "equal":
            continue
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            for k in reversed(range(i2 - i1)):
                keys.append(edit_line(i1 + k + 1, a[i1 + k], b[j1 + k]))
            continue
        if tag in ("replace", "insert") and j2 > j1:
            # pair the common prefix of the block line-by-line, add/delete the rest
            m = min(i2 - i1, j2 - j1)
            if i2 - i1 > m:
                keys.append(goto(i1 + m + 1) + f"{i2 - i1 - m}dd")
            if j2 - j1 > m:
                keys.append(open_lines(i1 + m, b[j1 + m:j2]))
            for k in reversed(range(m)):
                keys.append(edit_line(i1 + k + 1, a[i1 + k], b[j1 + k]))
            continue
        if tag == "delete":
            keys.append(goto(i1 + 1) + f"{i2 - i1}dd")
    return "".join(keys) + "ZZ"


