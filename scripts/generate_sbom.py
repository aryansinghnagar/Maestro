#!/usr/bin/env python
"""Generate packaging/sbom.cdx.json (CycloneDX 1.5) from pyproject.toml + uv.lock.

Single source of truth:
  - Project version / license / description come from ``pyproject.toml``.
  - Component versions are the *resolved* pins from ``uv.lock``
    (never ``>=`` ranges, never hand-edited guesses).

Usage:
    python scripts/generate_sbom.py [--check]

``--check`` exits non-zero when the on-disk SBOM is stale (for CI).
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"
UV_LOCK = ROOT / "uv.lock"
SBOM_PATH = ROOT / "packaging" / "sbom.cdx.json"

# Curated SPDX ids for *direct* dependencies only. Anything uncertain is
# omitted (valid CycloneDX) rather than guessed.
LICENSES: dict[str, str] = {
    "opencv-python": "Apache-2.0",
    "mediapipe": "Apache-2.0",
    "numpy": "BSD-3-Clause",
    "pyqt6": "GPL-3.0-only",
    "pyyaml": "MIT",
    "ruamel-yaml": "MIT",
    "jsonschema": "MIT",
    "structlog": "MIT",
    "numba": "BSD-2-Clause",
    "onnxruntime": "MIT",
    "tuf": "MIT",
    "psutil": "BSD-3-Clause",
    "watchdog": "Apache-2.0",
    "wasmtime": "Apache-2.0",
    "evdev": "BSD-3-Clause",
    "pyobjc-framework-quartz": "MIT",
    "pyobjc-framework-applicationservices": "MIT",
    "pyobjc-framework-cocoa": "MIT",
}


def _project_meta() -> dict[str, str]:
    with open(PYPROJECT, "rb") as f:
        data = tomllib.load(f)
    proj = data["project"]
    return {
        "name": proj["name"],
        "version": proj["version"],
        "description": proj.get("description", ""),
        "license": proj.get("license", "AGPL-3.0-or-later"),
    }


def _locked_versions() -> dict[str, str]:
    """Parse ``[[package]] name/version`` pairs out of uv.lock."""
    text = UV_LOCK.read_text(encoding="utf-8")
    pairs = re.findall(r'\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"', text)
    return {name.lower(): version for name, version in pairs}


def _direct_dep_names() -> list[str]:
    with open(PYPROJECT, "rb") as f:
        data = tomllib.load(f)
    names: list[str] = []
    for req in data["project"]["dependencies"]:
        # Strip env markers and extras: "evdev>=1.6.0; sys_platform == 'linux'".
        base = req.split(";")[0].strip()
        name = re.split(r"[<>=!~\s\[]", base, maxsplit=1)[0].strip().lower()
        if name:
            names.append(name)
    return names


def build_sbom() -> dict:
    meta = _project_meta()
    locked = _locked_versions()
    direct = _direct_dep_names()
    project_key = meta["name"].lower()

    components: list[dict] = []
    for name in sorted(set(locked) - {project_key}):
        version = locked[name]
        comp: dict = {
            "type": "library",
            "bom-ref": f"pkg:pypi/{name}@{version}",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name}@{version}",
        }
        if name in direct:
            comp["scope"] = "required"
            lic = LICENSES.get(name)
            if lic:
                comp["licenses"] = [{"license": {"id": lic}}]
        else:
            comp["scope"] = "required"  # transitive of a locked dep
        components.append(comp)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:96c9c614-2c0c-43df-8120-cf68a8ee4f3c",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": [
                {"vendor": "Maestro", "name": "generate_sbom.py", "version": meta["version"]}
            ],
            "component": {
                "type": "application",
                "bom-ref": f"pkg:pypi/{meta['name']}@{meta['version']}",
                "name": "Maestro",
                "version": meta["version"],
                "description": meta["description"],
                "licenses": [{"license": {"id": meta["license"]}}],
                "purl": f"pkg:pypi/{meta['name']}@{meta['version']}",
            },
        },
        "components": components,
    }


def main() -> int:
    sbom = build_sbom()
    rendered = json.dumps(sbom, indent=2) + "\n"
    if "--check" in sys.argv:
        if not SBOM_PATH.exists():
            print("SBOM missing; run: python scripts/generate_sbom.py")
            return 1
        on_disk = json.loads(SBOM_PATH.read_text(encoding="utf-8"))
        # Compare semantically (ignore timestamp regeneration noise).
        a, b = dict(sbom), dict(on_disk)
        a["metadata"] = {k: v for k, v in a["metadata"].items() if k != "timestamp"}
        b_meta = b.get("metadata", {})
        b["metadata"] = {k: v for k, v in b_meta.items() if k != "timestamp"}
        if a == b:
            print(f"SBOM fresh ({len(sbom['components'])} components).")
            return 0
        print("SBOM stale; run: python scripts/generate_sbom.py")
        return 1
    SBOM_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {SBOM_PATH} ({len(sbom['components'])} components).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
