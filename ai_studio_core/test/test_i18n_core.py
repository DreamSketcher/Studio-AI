# -*- coding: utf-8 -*-
"""Тесты ядра локализации ai_studio_core.i18n.

Регрессия по отчёту: переключение языка на русский приводило к падению.
Класс ошибок закрыт здесь: t() не бросает исключений, set_language()
безопасно отклоняет неизвестные коды, gpt_client.refresh_i18n_labels()
работает на реальных словарях.
"""
from __future__ import annotations

import pytest

from ai_studio_core import i18n
from ai_studio_core.i18n import (
    DEFAULT_LANGUAGE, LANGUAGES, TRANSLATIONS,
    available_languages, get_language, set_language, t,
)


@pytest.fixture(autouse=True)
def _restore_language():
    prev = get_language()
    yield
    set_language(prev)


class TestDictionaries:
    def test_parity_en_ru_keysets_identical(self):
        """EN и RU словари содержат одинаковые наборы ключей — перевод не «просеян»."""
        en_keys = set(TRANSLATIONS["en"].keys())
        ru_keys = set(TRANSLATIONS["ru"].keys())
        assert en_keys == ru_keys, (
            f"Различия ключей: только en={sorted(en_keys - ru_keys)}, "
            f"только ru={sorted(ru_keys - en_keys)}"
        )

    def test_all_values_non_empty_strings(self):
        for lang, mapping in TRANSLATIONS.items():
            for key, value in mapping.items():
                assert isinstance(value, str) and value.strip(), f"{lang}:{key} пуст"

    def test_every_key_translates_in_every_language(self):
        for key in TRANSLATIONS[DEFAULT_LANGUAGE]:
            for lang in LANGUAGES:
                out = t(key, lang=lang)
                assert out == TRANSLATIONS[lang][key]

    def test_russian_present(self):
        """Ключевой кейс: русский перевод существует и это не сам ключ."""
        assert t("menu_file", lang="ru") != "menu_file"
        assert t("menu_file", lang="ru") == "&Файл"


class TestTranslationFallback:
    def test_missing_key_returns_key_itself(self):
        assert t("definitely.missing.key") == "definitely.missing.key"

    def test_t_never_raises(self):
        for bad in (None, "", 123, "menu_file"):
            try:
                out = t(bad)  # type: ignore[arg-type]
            except Exception as e:  # noqa: BLE001
                pytest.fail(f"t({bad!r}) бросил {type(e).__name__}: {e}")
            else:
                assert isinstance(out, str)

    def test_unknown_lang_falls_back_to_current(self):
        assert t("menu_file", lang="klingon") == TRANSLATIONS[DEFAULT_LANGUAGE]["menu_file"]


class TestSetLanguage:
    def test_valid_switch(self):
        assert set_language("ru") is True
        assert get_language() == "ru"
        assert t("menu_file") == "&Файл"
        assert set_language("en") is True
        assert get_language() == "en"
        assert t("menu_file") == "&File"

    def test_invalid_codes_rejected_safely(self):
        """Краш-регрессия: неизвестный код языка не должен ничего ломать."""
        set_language("en")
        for bad in ("de", "日本語", "", None, 42, ["ru"]):
            assert set_language(bad) is False  # type: ignore[arg-type]
            assert get_language() == "en", f"set_language({bad!r}) сместил язык"
            assert t("menu_file") == "&File"

    def test_ping_pong_switching_stable(self):
        for _ in range(10):
            set_language("ru")
            set_language("en")
        assert get_language() == "en"

    def test_available_languages(self):
        langs = available_languages()
        assert langs == LANGUAGES
        assert langs is not LANGUAGES  # копия, не мутируем оригинал


class TestGptClientIntegration:
    def test_provider_labels_follow_language(self):
        """refresh_i18n_labels подтягивает переводы провайдеров."""
        from ai_studio_core import gpt_client

        set_language("ru")
        gpt_client.refresh_i18n_labels()
        assert gpt_client.PROVIDERS["groq"]["label"] == TRANSLATIONS["ru"]["prov_groq"]
        assert gpt_client.PROVIDERS["openrouter"]["label"] == TRANSLATIONS["ru"]["prov_openrouter"]

        set_language("en")
        gpt_client.refresh_i18n_labels()
        assert gpt_client.PROVIDERS["groq"]["label"] == TRANSLATIONS["en"]["prov_groq"]

    def test_gpt_t_returns_translated_keys(self):
        set_language("ru")
        from ai_studio_core.gpt_client import _t
        assert _t("prov_groq") == TRANSLATIONS["ru"]["prov_groq"]

    def test_refresh_labels_robustly_silent_on_junk(self):
        """Даже если что-то пошло не так в каталоге — функция не роняет приложение."""
        from ai_studio_core import gpt_client
        gpt_client.refresh_i18n_labels()  # просто не должно кидать
