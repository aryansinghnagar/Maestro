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


def compile_po(po_path: Path) -> bool:
    mo_path = po_path.with_suffix(".mo")
    try:
        result = subprocess.run(
            ["msgfmt", "-o", str(mo_path), str(po_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  ✓  {po_path.parent.parent.name}: {po_path.name} → {mo_path.name}")
            return True
        else:
            print(f"  ✗  {po_path}: {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        # msgfmt not found — try python-only approach via babel or skip
        print(
            "  ⚠  msgfmt not found on PATH. Install gettext tools:\n"
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
