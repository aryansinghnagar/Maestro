#!/usr/bin/env python
"""Compile all .po files in the locales directory to .mo binary format.

Run this script after adding or modifying any .po translation files:
    python scripts/compile_locales.py
"""

import subprocess
import sys
from pathlib import Path

LOCALES_DIR = Path(__file__).parent.parent / "gesture_controller" / "data" / "locales"
DOMAIN = "maestro"


def _compile_with_stdlib_msgfmt(po_path: Path, mo_path: Path) -> bool:
    """Pure-python fallback using CPython's Tools/i18n/msgfmt.py (no gettext needed)."""
    try:
        import sys as _sys

        tools_candidates = [
            Path(_sys.base_prefix) / "Tools" / "i18n" / "msgfmt.py",
            Path(_sys.exec_prefix) / "Tools" / "i18n" / "msgfmt.py",
        ]
        msgfmt_py = next((p for p in tools_candidates if p.exists()), None)
        if msgfmt_py is None:
            return False
        result = subprocess.run(
            [_sys.executable, str(msgfmt_py), "-o", str(mo_path), str(po_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def _parse_po_messages(po_path: Path) -> dict[bytes, bytes]:
    """Minimal .po parser returning {msgid_bytes: msgstr_bytes}.

    Handles singular msgid/msgstr pairs with multi-line string
    concatenation and standard escapes. Skips the header entry
    (empty msgid), fuzzy entries, and plural forms (keeps msgstr[0]).
    """
    messages: dict[bytes, bytes] = {}
    msgid: list[str] | None = None
    msgstr: list[str] | None = None
    msgstr_plural: dict[int, list[str]] | None = None
    fuzzy = False
    section: str | None = None  # "id" | "str" | ("plural", idx)

    def flush() -> None:
        if msgid is None:
            return
        key = "".join(msgid)
        if fuzzy:
            return
        if not key:
            # Header entry (empty msgid): REQUIRED so gettext knows the
            # charset (UTF-8). Without it, non-ASCII catalogs fail to parse.
            val = "".join(msgstr or [])
            if val:
                messages[b""] = val.encode("utf-8")
            return
        if msgstr_plural:
            # Plural: gettext looks up "msgid\\x00msgid_plural".
            # We only have the singular key here; store msgstr[0].
            val = "".join(msgstr_plural.get(0, msgstr or []))
        else:
            val = "".join(msgstr or [])
        if val:
            messages[key.encode("utf-8")] = val.encode("utf-8")

    def unquote(s: str) -> str:
        s = s.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            s = s[1:-1]
        # Standard .po escapes (order matters: backslash last).
        s = s.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
        s = s.replace("\\\\", "\\")
        return s

    with open(po_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("#"):
                if ", fuzzy" in line or line.startswith("#,") and "fuzzy" in line:
                    fuzzy = True
                continue
            if not line:
                flush()
                msgid, msgstr, msgstr_plural, fuzzy, section = None, None, None, False, None
                continue
            if line.startswith("msgid_plural"):
                section = "plural_id"
                continue
            if line.startswith("msgid"):
                flush()
                msgid, msgstr, msgstr_plural, fuzzy = [], [], None, False
                section = "id"
                rest = line[5:].strip()
                if rest:
                    msgid.append(unquote(rest))
                continue
            if line.startswith("msgstr["):
                idx = int(line[7 : line.index("]")])
                if msgstr_plural is None:
                    msgstr_plural = {}
                msgstr_plural[idx] = []
                section = ("plural", idx)
                rest = line[line.index("]") + 1 :].strip()
                if rest:
                    msgstr_plural[idx].append(unquote(rest))
                continue
            if line.startswith("msgstr"):
                msgstr = []
                section = "str"
                rest = line[6:].strip()
                if rest:
                    msgstr.append(unquote(rest))
                continue
            if line.startswith('"'):
                text = unquote(line)
                if section == "id" and msgid is not None:
                    msgid.append(text)
                elif section == "str" and msgstr is not None:
                    msgstr.append(text)
                elif isinstance(section, tuple) and msgstr_plural is not None:
                    msgstr_plural[section[1]].append(text)
                continue
    flush()
    return messages


def _compile_with_pure_python(po_path: Path, mo_path: Path) -> bool:
    """Self-contained .po -> .mo compiler (no gettext needed).

    Writes GNU .mo binary format: magic, version, N, key/value offset
    tables, then string data. Keys sorted by msgid as msgfmt does.
    """
    import struct as _struct

    try:
        messages = _parse_po_messages(po_path)
    except Exception as e:
        print(f"  [FAIL] {po_path}: po parse failed: {e}")
        return False
    keys = sorted(messages.keys())
    offsets: list[tuple[int, int, int, int]] = []
    key_blob = b""
    val_blob = b""
    for k in keys:
        v = messages[k]
        offsets.append((len(k), len(key_blob), len(v), len(val_blob)))
        key_blob += k + b"\x00"
        val_blob += v + b"\x00"
    n = len(keys)
    keystart = 28 + n * 16
    valstart = keystart + len(key_blob)
    out = bytearray()
    out += _struct.pack("Iiiiiii", 0x950412DE, 0, n, 28, 28 + n * 8, 0, 0)
    for klen, koff, vlen, voff in offsets:
        out += _struct.pack("ii", klen, koff + keystart)
    for klen, koff, vlen, voff in offsets:
        out += _struct.pack("ii", vlen, voff + valstart)
    out += key_blob + val_blob
    try:
        mo_path.write_bytes(bytes(out))
    except OSError as e:
        print(f"  [FAIL] {po_path}: cannot write .mo: {e}")
        return False
    print(
        f"  [OK] {po_path.parent.parent.name}: {po_path.name} -> "
        f"{mo_path.name} ({n} strings, pure-python)"
    )
    return True


def compile_po(po_path: Path) -> bool:
    mo_path = po_path.with_suffix(".mo")
    try:
        result = subprocess.run(
            ["msgfmt", "-o", str(mo_path), str(po_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"  [OK] {po_path.parent.parent.name}: {po_path.name} -> {mo_path.name}")
            return True
        print(f"  [FAIL] {po_path}: {result.stderr.strip()}")
    except FileNotFoundError:
        print("  [..] msgfmt not on PATH; trying pure-python fallback...")
    except subprocess.TimeoutExpired:
        print(f"  [FAIL] {po_path}: msgfmt timed out after 30s")
        return False
    # Fallback 1: stdlib msgfmt.py so fresh clones still get .mo files.
    if _compile_with_stdlib_msgfmt(po_path, mo_path):
        print(f"  [OK] {po_path.parent.parent.name}: {po_path.name} -> {mo_path.name} (stdlib)")
        return True
    # Fallback 2: self-contained compiler (works everywhere, no gettext).
    if _compile_with_pure_python(po_path, mo_path):
        return True
    print(
        "  [WARN] msgfmt not found on PATH. Install gettext tools:\n"
        "      Windows: https://mlocati.github.io/articles/gettext-iconv-windows.html\n"
        "      macOS:   brew install gettext\n"
        "      Linux:   sudo apt-get install gettext"
    )
    return False


def main() -> int:
    if not LOCALES_DIR.exists():
        print(f"Locales directory not found: {LOCALES_DIR}")
        return 1

    po_files = list(LOCALES_DIR.rglob(f"{DOMAIN}.po"))
    if not po_files:
        print("No .po files found.")
        return 1

    print(f"Compiling {len(po_files)} .po file(s) in {LOCALES_DIR}:")
    failures = 0
    for po_path in sorted(po_files):
        if not compile_po(po_path):
            failures += 1

    if failures:
        print(f"\n{failures} file(s) failed to compile.")
        return 1
    print(f"\nAll {len(po_files)} locale(s) compiled successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
