"""Unit tests for Sprint 10 – i18n (internationalization).

Tests cover:
- detect_system_locale() env-var and OS fallback
- install() + _ passthrough and translation lookup
- available_languages() discovery
- current_lang() tracking
- Fallback chain: unknown lang → en → NullTranslations
- Language selector in SettingsWindow
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_cache() -> None:
    """Reset module-level caches between tests."""
    import gesture_controller.core.i18n as i18n_mod

    i18n_mod._translators.clear()
    i18n_mod._current_lang = "en"
    i18n_mod._ = i18n_mod._noop


# ---------------------------------------------------------------------------
# detect_system_locale
# ---------------------------------------------------------------------------


class TestDetectSystemLocale:
    def test_reads_language_env_var(self) -> None:
        from gesture_controller.core.i18n import detect_system_locale

        with patch.dict(os.environ, {"LANGUAGE": "fr_FR.UTF-8"}, clear=False):
            assert detect_system_locale() == "fr"

    def test_reads_lang_env_var(self) -> None:
        from gesture_controller.core.i18n import detect_system_locale

        env = {"LANGUAGE": "", "LANG": "de_DE.UTF-8", "LC_ALL": ""}
        with patch.dict(os.environ, env, clear=False):
            assert detect_system_locale() == "de"

    def test_reads_lc_all_env_var(self) -> None:
        from gesture_controller.core.i18n import detect_system_locale

        env = {"LANGUAGE": "", "LANG": "", "LC_ALL": "es_MX.UTF-8"}
        with patch.dict(os.environ, env, clear=False):
            assert detect_system_locale() == "es"

    def test_falls_back_to_en_on_empty_env(self) -> None:
        from gesture_controller.core.i18n import detect_system_locale

        env = {"LANGUAGE": "", "LANG": "", "LC_ALL": "", "LC_MESSAGES": ""}
        with patch.dict(os.environ, env, clear=False):
            with patch("locale.getlocale", return_value=(None, None)):
                result = detect_system_locale()
        assert result == "en"

    def test_returns_two_letter_code(self) -> None:
        from gesture_controller.core.i18n import detect_system_locale

        with patch.dict(os.environ, {"LANGUAGE": "pt_BR"}, clear=False):
            code = detect_system_locale()
        assert len(code) == 2
        assert code == "pt"


# ---------------------------------------------------------------------------
# install() + _ translation
# ---------------------------------------------------------------------------


class TestInstall:
    def setup_method(self):
        _clear_cache()

    def teardown_method(self):
        _clear_cache()

    def test_install_en_returns_passthrough(self) -> None:
        from gesture_controller.core.i18n import install, _

        lang = install("en")
        assert lang == "en"
        # English passthrough – msgstr == msgid
        from gesture_controller.core import i18n as i18n_mod

        assert i18n_mod._("Settings") == "Settings"

    def test_install_unknown_lang_falls_back_to_en(self) -> None:
        from gesture_controller.core.i18n import install, current_lang

        install("zz")  # Non-existent language
        # Should not raise; falls back gracefully
        assert current_lang() == "zz"  # lang code is stored as-is
        from gesture_controller.core import i18n as i18n_mod

        assert i18n_mod._("Hello") == "Hello"  # passthrough via NullTranslations

    def test_install_sets_current_lang(self) -> None:
        from gesture_controller.core.i18n import install, current_lang

        install("es")
        assert current_lang() == "es"

    def test_install_none_auto_detects(self) -> None:
        from gesture_controller.core.i18n import install, current_lang

        with patch.dict(os.environ, {"LANGUAGE": "fr_FR"}, clear=False):
            install(None)
        assert current_lang() == "fr"

    def test_install_caches_translator(self) -> None:
        import gesture_controller.core.i18n as i18n_mod

        install = i18n_mod.install
        install("en")
        install("en")  # Second call should use cached
        assert len(i18n_mod._translators) == 1

    def test_gettext_callable_returns_function(self) -> None:
        from gesture_controller.core.i18n import install, gettext_callable

        install("en")
        fn = gettext_callable()
        assert callable(fn)
        assert fn("OK") == "OK"


# ---------------------------------------------------------------------------
# available_languages()
# ---------------------------------------------------------------------------


class TestAvailableLanguages:
    def test_returns_list_with_at_least_en(self) -> None:
        from gesture_controller.core.i18n import available_languages

        langs = available_languages()
        assert isinstance(langs, list)
        assert len(langs) > 0

    def test_contains_expected_languages(self) -> None:
        from gesture_controller.core.i18n import available_languages

        langs = available_languages()
        # We shipped en, es, fr, de, ja, ar, hi
        for expected in ("en", "es", "fr", "de", "ja", "ar", "hi"):
            assert expected in langs, f"{expected} missing from available_languages()"

    def test_sorted_output(self) -> None:
        from gesture_controller.core.i18n import available_languages

        langs = available_languages()
        assert langs == sorted(langs)

    def test_returns_en_when_locales_dir_missing(self) -> None:
        from gesture_controller.core.i18n import available_languages

        with patch("gesture_controller.core.i18n._LOCALE_DIR", Path("/nonexistent/path")):
            langs = available_languages()
        assert langs == ["en"]


# ---------------------------------------------------------------------------
# Fallback chain
# ---------------------------------------------------------------------------


class TestFallbackChain:
    def setup_method(self):
        _clear_cache()

    def teardown_method(self):
        _clear_cache()

    def test_missing_mo_file_does_not_crash(self) -> None:
        """If no .mo is present, should fall back to NullTranslations."""
        import gesture_controller.core.i18n as i18n_mod

        # Patch locale dir to a temp path where no .mo exists
        with patch("gesture_controller.core.i18n._LOCALE_DIR", Path("/tmp/nonexistent_locales")):
            t = i18n_mod._load_translator("xx")
        # Should have returned a NullTranslations without raising
        import gettext

        assert isinstance(t, gettext.NullTranslations)

    def test_corrupt_mo_file_falls_back_gracefully(self, tmp_path) -> None:
        import gesture_controller.core.i18n as i18n_mod

        lang_dir = tmp_path / "xx" / "LC_MESSAGES"
        lang_dir.mkdir(parents=True)
        mo_path = lang_dir / "maestro.mo"
        mo_path.write_bytes(b"CORRUPTED DATA")  # Not a valid .mo

        with patch("gesture_controller.core.i18n._LOCALE_DIR", tmp_path):
            t = i18n_mod._load_translator("xx")

        import gettext

        assert isinstance(t, gettext.NullTranslations)


# ---------------------------------------------------------------------------
# Language selector in SettingsWindow
# ---------------------------------------------------------------------------


class TestLanguageSelectorUI:
    def test_language_combo_populated(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.core.config_manager import ConfigManager

        window = SettingsWindow(ConfigManager())
        assert window._lang_combo.count() >= 7  # at least 7 languages

        # All items should have valid 2-letter data codes
        for i in range(window._lang_combo.count()):
            code = window._lang_combo.itemData(i)
            assert isinstance(code, str) and len(code) == 2

        window.deleteLater()
        qapp.processEvents()

    def test_language_change_calls_install(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.core.config_manager import ConfigManager
        from gesture_controller.core import i18n as i18n_mod

        window = SettingsWindow(ConfigManager())

        with patch.object(i18n_mod, "install", return_value="es") as mock_install:
            # Set to Spanish (find its index)
            es_idx = -1
            for i in range(window._lang_combo.count()):
                if window._lang_combo.itemData(i) == "es":
                    es_idx = i
                    break
            assert es_idx >= 0
            window._lang_combo.setCurrentIndex(es_idx)
            mock_install.assert_called_with("es")

        window.deleteLater()
        qapp.processEvents()

    def test_language_saved_to_config_on_change(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.core.config_manager import ConfigManager

        config = ConfigManager()
        window = SettingsWindow(config)

        # Find German index
        de_idx = next(
            (
                i
                for i in range(window._lang_combo.count())
                if window._lang_combo.itemData(i) == "de"
            ),
            -1,
        )
        assert de_idx >= 0

        with patch("gesture_controller.core.i18n.install"):
            window._lang_combo.setCurrentIndex(de_idx)

        assert config.get("ui.language") == "de"

        window.deleteLater()
        qapp.processEvents()

    def test_initial_lang_combo_selection_matches_current_lang(self, qapp) -> None:
        from gesture_controller.gui.settings_window import SettingsWindow
        from gesture_controller.core.config_manager import ConfigManager
        from gesture_controller.core import i18n as i18n_mod

        # Force current language to French
        with patch.object(i18n_mod, "current_lang", return_value="fr"):
            window = SettingsWindow(ConfigManager())

        # The combo should have FR selected
        selected_code = window._lang_combo.currentData()
        assert selected_code == "fr"

        window.deleteLater()
        qapp.processEvents()
