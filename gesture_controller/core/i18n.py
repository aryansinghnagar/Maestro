"""Internationalization support for Maestro.

Usage:
    from gesture_controller.core.i18n import _

    label = _("Settings")

Locale files are stored in gesture_controller/data/locales/<lang>/LC_MESSAGES/maestro.po
They are compiled to .mo files via `msgfmt`.
"""
from __future__ import annotations

import gettext
import locale
import logging
import os
import threading
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
_LOCALE_DIR = Path(__file__).parent.parent / "data" / "locales"
_DOMAIN = "maestro"

# ── Module-level translation function (replaced on install) ──────────────────
_current_lang: str = "en"
_translation_lock = threading.Lock()
_translators: dict[str, gettext.NullTranslations] = {}

# Default: passthrough
def _noop(s: str) -> str:
    return s

_ = _noop


def detect_system_locale() -> str:
    """Return the best matching 2-letter language code from the OS locale.

    Returns: e.g. "en", "fr", "de", "ar", "ja". Falls back to "en".
    """
    try:
        # Prefer env var overrides (LANG, LANGUAGE, LC_ALL)
        for env_key in ("LANGUAGE", "LANG", "LC_ALL", "LC_MESSAGES"):
            val = os.environ.get(env_key, "")
            if val:
                code = val.split("_")[0].split(".")[0].lower()
                if len(code) >= 2:
                    return code[:2]
        # Fallback: ask the OS
        lang, _ = locale.getlocale()
        if lang:
            code = lang.split("_")[0].lower()
            return code[:2]
    except Exception:
        pass
    return "en"


def _load_translator(lang: str) -> gettext.NullTranslations:
    """Load (or return cached) a GNUTranslations object for *lang*."""
    if lang in _translators:
        return _translators[lang]

    mo_dir = _LOCALE_DIR / lang / "LC_MESSAGES"
    mo_path = mo_dir / f"{_DOMAIN}.mo"

    if mo_path.exists():
        try:
            t = gettext.GNUTranslations(open(mo_path, "rb"))
            _translators[lang] = t
            return t
        except Exception as exc:
            logger.warning("Failed to load .mo file for %s: %s", lang, exc)

    # Try fallback to English
    if lang != "en":
        return _load_translator("en")

    # Absolute fallback: NullTranslations (passthrough)
    null = gettext.NullTranslations()
    _translators[lang] = null
    return null


def install(lang: str | None = None) -> str:
    """Install the translation for *lang* globally as the module-level ``_``.

    If *lang* is None, auto-detects from system locale.
    Returns the active language code.
    """
    global _, _current_lang

    if lang is None:
        lang = detect_system_locale()

    with _translation_lock:
        translator = _load_translator(lang)
        new_gettext: Callable[[str], str] = translator.gettext
        _ = new_gettext  # type: ignore[assignment]
        _current_lang = lang

    logger.debug("Installed language: %s", lang)
    return lang


def current_lang() -> str:
    """Return the currently active language code."""
    return _current_lang


def available_languages() -> list[str]:
    """Return sorted list of languages that have a locale directory."""
    if not _LOCALE_DIR.exists():
        return ["en"]
    langs = sorted(
        d.name
        for d in _LOCALE_DIR.iterdir()
        if d.is_dir() and (d / "LC_MESSAGES").is_dir()
    )
    return langs if langs else ["en"]


def gettext_callable() -> Callable[[str], str]:
    """Return the currently installed translation callable."""
    return _


# Re-export so callers can do: from gesture_controller.core.i18n import _
__all__ = ["_", "install", "detect_system_locale", "current_lang", "available_languages"]
