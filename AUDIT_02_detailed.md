# Отчёт №2 — Детальный аудит перед рефакторингом (Этап A)
**Дата:** 2026-07-18
**Репозиторий:** `DreamSketcher/XTTS-Studio-AI` @ `a28df4a Fix CI`
**Этап:** Детальный анализ кода/импортов/тестов ПЕРЕД Этапом A (правки в `_source_xtts_studio/`).
**Метод:** AST-разбор всех переносимых файлов + строковый разбор динамических импортов.

---

## 1. Подтверждённые файлы к переносу — и их реальный граф импортов

Всего переносимых `.py`-файлов: **48** (с учётом подпакетов `env_core/`, `tts/`, `rvc_catalog/`).
Группы по размеру и риску:

| Группа | Файлы | LOC (сумм.) | GUI-импорты | TK/CustomTk | i18n |
|---|---|---|---|---|---|
| Фундамент (нулевой слой) | `atomic_write.py`, `paths.py`, `logging_utils.py`, `text_utils.py`, `lazy_loader.py`, `task_models.py`, `error_report.py`, `secret_store.py`, `release_hashing.py`, `settings_store.py`, `validation.py` | ~660 | 0 | 0 | 0 |
| env_core (диагностика/установка) | `env_core/__init__.py`, `cpu_gpu.py`, `diagnostics.py` (1859 LOC!), `llama_setup.py`, `rvc_setup.py`, `torch_setup.py` | **4088** | 3 (нарушения #1–#3) | 0* | 0 |
| TTS-движок | `tts/__init__.py` (893), `cache.py`, `device.py`, `export.py`, `qc.py`, `utils.py`, `tts_runner.py` | ~1465 | 0 | 0 | 0 |
| RVC | `rvc_catalog/` (7 файлов, сумм. ~1661), `rvc_pipeline.py` (466) | ~2127 | 0 | 0 | 0 |
| AI-клиенты | `ai_conductor.py`, `gpt_client.py`, `local_llm_client.py` | **2210** | 0 | 0 | **1** (#4) |
| Текст-пайплайн | `normalizer.py`, `chunker.py`, `smart_pauses.py`, `prosody_layer.py`, `de_esser.py`, `reference_processor.py`, `word_replacer.py` | ~1908 | 0 | 0 | 0 |
| Инфраструктура/Сервис | `env_setup.py`, `updater.py`, `update_signing.py`, `history_store.py`, `voice_manager.py`, `task_manager.py`, `output_naming.py` | ~1520 | 0 | 0 | 0 |

**Примечание:** `customtkinter` в `env_core/diagnostics.py` импортируется только внутри `try/except Exception` в диагностической функции (строки ~601–604), в неблокирующем режиме, и только тогда, когда пользователь явно запускает диагностику. Это не headless-блокер. ✅

---

## 2. Внешние (third-party) зависимости переносимого ядра

После AST-сканирования всех 48 файлов (включая ленивые импорты внутри функций):

| pip-пакет | Кто использует | Обязателен? |
|---|---|---|
| `torch` | `tts/qc.py`, `tts/utils.py`, `tts/cache.py`, `tts/device.py` | ✅ обязательный (ядро ML) |
| `numpy` | `tts/__init__.py` (лен.), `de_esser.py` | ✅ обязательный |
| `pydub` | `tts/__init__.py`, `reference_processor.py`, `tts/export.py`, `tts/qc.py` (косвенно) | ✅ обязательный (AudioSegment) |
| `soundfile` | `tts/__init__.py` (лен., строка 638) | ✅ обязательный (чтение WAV) |
| `TTS` (Coqui XTTS) | `tts/__init__.py` (лен., строка 227) | ✅ обязательный (сам TTS) |
| `cryptography` | `update_signing.py` | ✅ обязательный (Ed25519-подпись) |
| `certifi` | `updater.py`, `local_llm_client.py` (SSL) | ✅ обязательный (обновления/сеть) |
| `psutil` | `local_llm_client.py` | ✅ рекомендуется (проверка ресурсов) |
| `num2words` | `normalizer.py` | ✅ обязательный (нормализация чисел) |
| `cpuinfo` (`py-cpuinfo`) | `env_core/cpu_gpu.py` | ✅ рекомендуется (детекция CPU) |
| `llama_cpp` (`llama-cpp-python`) | `local_llm_client.py` (лен.) | ⚠️ опциональный (нужен только для локальных LLM) |
| `rvc_python` | `rvc_pipeline.py` | ⚠️ опциональный (ставится из env_core/rvc_setup.py, не в requirements.txt) |
| `pygame` | `tts/__init__.py` (лен., в блоке try/except, строка 191) | ⚠️ **нужен только для UI-плеера** (импорт завёрнут в try/except, отсутствие не ломает headless) |

**Зависимости, которые НЕ нужны** переносимому ядру и останутся в исходнике (части GUI):
`customtkinter`, `tkinterdnd2`, `pygame` (только fallback, не обязателен), `darkdetect`, `Babel`, `Flask`, `uvicorn`, `FastAPI`, `matplotlib`, `pillow`, `pygame`-плеерный слой.

---

## 3. Внутренние (engine → engine) зависимости — проверка на скрытые GUI-ссылки

### 3.1 Явные (не-Lazy) импорты `engine.gui.*`
Только три, ровно как в ТЗ:
1. `engine/env_core/rvc_setup.py:274` → `engine.gui.env_settings._can_clear_diagnostics_cache`
2. `engine/env_core/torch_setup.py:257` → `engine.gui.env_settings.{_acquire_install_lock,_release_install_lock,_get_current_install_type}`
3. `engine/env_core/torch_setup.py:458` → `engine.gui.env_settings.{_release_install_lock,_set_install_cancelled}`

### 3.2 Динамические импорты (`importlib.import_module`, `__import__`)
Сканирование по 48 файлам: **0** ссылок на `engine.gui`, `tkinter`, `customtkinter`. ✅

### 3.3 Импорты исключённых из переноса файлов
- `engine.batch_window` → 0 ссылок в переносимом коде. ✅
- `engine.gui_cyrillic_checker` → 0 ссылок в переносимом коде. ✅

### 3.4 tkinter/customtkinter вне `try/except`
**0** жёстких импортов `tkinter`/`customtkinter` в переносимом коде. Единственное упоминание `customtkinter` — в диагностике под try/except (см. §1). ✅

### 3.5 i18n-жёсткий импорт
Ровно 1: `engine/gpt_client.py:35 from i18n import t as _t` (нарушение #4). Исправляется по §2.2 ТЗ.
Других импортов `i18n` в переносимом коде нет. ✅

### 3.6 Другие корневые (не-engine) модули проекта
**0** ссылок на `gui.py`, `gui_cyrillic_checker.py` и прочие корневые файлы проекта из переносимых модулей. ✅

---

## 4. Анализ функций install-state, которые нужно перенести

В `engine/gui/env_settings.py` на строках 28–91 ровно пять публичных для env_core элементов (включая приватный модульный стейт):

| Строка | Элемент | Тип | Что делает |
|---|---|---|---|
| 28 | `_INSTALL_LOCK = threading.RLock()` | модульная переменная | реентерабельный лок установки |
| 29 | `_INSTALL_STATE = {"running": False, "type": None, "cancelled": False}` | модульная переменная | текущее состояние install-процесса |
| 32 | `_acquire_install_lock(install_type: str) -> bool` | функция | взять лок, вернуть True если успешно |
| 44 | `_release_install_lock()` | функция | отпустить лок, сбросить state |
| 56 | `_get_current_install_type() -> str` | функция | текстовый тип текущей установки |
| 61 | `_set_install_cancelled()` | функция | флаг отмены текущей установки |
| 91 | `_can_clear_diagnostics_cache() -> bool` | функция | проверка "не запущена ли установка прямо сейчас" перед очисткой кэша диагностики |

Все эти 7 элементов (2 переменные + 5 функций) — чистая логика состояния, без единого упоминания `tkinter`, `customtkinter`, виджетов или любых GUI-объектов. Перенос дословный, без изменений логики. ✅

Внутри `env_settings.py` эти 5 функций используются на строках 687–1381 (блокировки при установке TTS/RVC и recovery-режиме). После рефакторинга env_settings будет импортировать их из `engine.env_core.install_state` — публичные имена не меняются, все вызовы в GUI-коде продолжат работать без правок в остальном `engine/gui/`.

---

## 5. Анализ `.importlinter` (планируемая реконструкция)

Поскольку конфиг отсутствует в репе (см. Отчёт №1, п.5.1), а ТЗ чётко перечисляет 11 слоёв снизу вверх, будет реконструирован следующий конфиг:

- `root_package = engine`
- Слои (снизу вверх, в терминах import-linter `layers`):
  1. `engine.atomic_write`
  2. `engine.paths`
  3. `engine.logging_utils`
  4. `engine.env_core`
  5. `engine.local_llm_client`
  6. `engine.gpt_client`
  7. `engine.ai_conductor`
  8. `engine.rvc_pipeline`
  9. `engine.rvc_catalog`
  10. `engine.tts`
  11. `engine.gui` (верхний)
- Контракты:
  - `env_core_independence`: слои 1–4 не должны импортировать ничего из слоёв 5–11.
  - `ai_modules_independence`: слои 1–7 не должны импортировать из `engine.rvc_pipeline`, `engine.rvc_catalog`, `engine.tts`, `engine.gui`.
  - `gui_is_top`: `engine.gui` может импортировать всё, но никто, кроме `engine.gui`, не может импортировать из `engine.gui`.
- `ignore_imports` = **пустой** после Этапа A (согласно приёмке §2.1 ТЗ).

Для нового проекта (`ai_studio_core`) тот же конфиг будет с `root_package = ai_studio_core`, переименованными слоями и без `ai_studio_core.gui` вообще (в новом проекте GUI-слоя пока нет).

---

## 6. Тесты — что переносить, что нет

Всего в `test/` 66 тестов + 4 вспомогательных скрипта.

### 6.1 Тесты, которые можно и нужно перенести в `ai_studio_core` (39 штук)
Это тесты, которые не импортируют `engine.gui.*`, `tkinter`, `customtkinter`, `gui.py` и не опираются на UI-фикстуры:

| Модуль | Тесты |
|---|---|
| `env_core` | `test_env_core_init.py`, `test_env_setup.py`, `test_cpu_gpu.py`, `test_diagnostics.py`, `test_docs_torch_versions.py`, `test_dependency_baseline.py`, `test_llama_setup.py`, `test_rvc_setup.py`, `test_torch_setup.py` (9) |
| `gpt_client` | `test_gpt_client.py` (1) |
| `local_llm_client` | `test_local_llm_client.py`, `test_local_llm_security.py` (2) |
| `updater` | `test_updater.py`, `test_updater_cancel_and_removed_files.py` (2) |
| `update_signing`/`release_hashing` | `test_update_signing.py`, `test_release_hashing.py`, `test_sha256_verification.py`, `test_reproducible_release.py`, `test_manifest_self_generated.py` (5) |
| `chunker` | `test_chunker.py` (1) |
| `de_esser` | `test_de_esser.py` (1) |
| `normalizer` | `test_normalizer.py` (1) |
| `smart_pauses` | `test_smart_pauses.py` (1) |
| `prosody_layer` | `test_prosody_layer.py` (1) |
| `reference_processor` | `test_reference_processor.py` (1) |
| `word_replacer` | `test_word_replacer.py` (1) |
| `rvc_pipeline` | `test_rvc_pipeline.py` (1) |
| `rvc_catalog` | `test_rvc_catalog.py` (1) |
| `tts` | `test_qc.py`, `test_tts_utils.py` (2) |
| `ai_conductor` | `test_ai_conductor.py` (1) |
| `task_manager` | `test_task_manager.py` (1) |
| `validation` | `test_validation.py` (1) |
| `output_naming`/`paths` | `test_output_naming.py` (1) |
| `history_store` | `test_history_store.py` (1) |
| `voice_manager` | `test_voice_manager.py` (1) |
| загрузочные | `test_local_llm_client_download.py` (1) — помечен ignored в CI |

Из них нужно скорректировать пути импорта в части тех тестов, что ссылаются на корневые helper-модули (например `test_manifest_self_generated.py`, `test_reproducible_release.py` ссылаются на `tools/` — в новом проекте их нужно будет положить рядом с соответствующими скриптами сборки/CI).

### 6.2 Тесты, которые НЕ переносятся (22 GUI-теста)
`test_animation_manager.py`, `test_batch_window.py`, `test_chat_long_messages.py`, `test_chat_progressive_render.py`, `test_configure_coalescer.py`, `test_console_batching.py`, `test_generation.py`, `test_header_panel.py`, `test_motion_profile.py`, `test_presets.py`, `test_presets_patch.py`, `test_progress_throttle.py`, `test_rvc_dropdown_incremental.py`, `test_rvc_progressive_render.py`, `test_settings_ui.py`, `test_sidebar_animation.py`, `test_smoke_startup.py`, `test_styles_menu.py`, `test_theme_manager.py`, `test_ui_coalescing.py`, `test_ui_thread_bridge.py`, `test_voice_panel.py`.

### 6.3 CI/док/security тесты (не про код engine) — остаются в исходнике или создаются заново
`test_docs_security_wording.py`, `test_docs_structure.py`, `test_generate_version_manifest.py`, `test_i18n.py`, `test_p3_security_tooling.py`, `test_pip_audit_gate.py`, `test_ruff_new_files_gate.py`. Для нового проекта будет нужен свой subset этих проверок (в частности `check_architecture.py`, `check_plugin_deps.py`, `pip-audit` gate).

---

## 7. Итоговая матрица приёмки Этапа A (перед правками)

| Критерий из ТЗ | Текущее состояние | План |
|---|---|---|
| `lint-imports` 3 kept, 0 broken | ❌ конфиг отсутствует; ожидается: после фикса 3 нарушений будет 3/0 | Создать `.importlinter` по реконструкции из §5; запустить после фикса |
| `ignore_imports` пустой | ❌ не существует файла; существуют 3 реальных нарушения + 1 (i18n) вне контрактов слоёв | После фиксов ignore_imports = пустой |
| `pytest test/` проходит до правок (baseline) | ⏳ не запускался в этой сессии | Запустить до правок и зафиксировать baseline, затем после правок сверить |
| Перенос `install_state.py` дословный | ⏳ 5 функций + 2 переменных локализованы на строках 28–91 env_settings.py | Чистый copy-paste, без правок логики |
| `try/except ImportError` в rvc_setup/torch_setup удалены | ❌ присутствуют | Удалить после правки импорта |
| Публичные имена в `engine/gui/env_settings.py` сохранены | ⏳ — | Заменить определения на re-export из нового модуля |
| `i18n`-фолбэк в `gpt_client.py` | ❌ жёсткий импорт | Обернуть в try/except с функцией-заглушкой |

---

## 8. Обнаруженные при детальном аудите нюансы (без расширения скоупа — только для отчёта)

1. **`engine/tts/__init__.py` переопределяет функцию `path(*args)` локально** (строка 119) — это собственный helper, не имеющий отношения к `engine.paths.path`. При пакетном переименовании (`engine` → `ai_studio_core`) проблем не создаст.
2. **`engine/tts/__init__.py` пишет в `os.environ` на верхнем уровне** (PYTHONHOME/PYTHONNOUSERSITE/PATH/TTS_SKIP_UPDATE — строки 17–23). Это изоляция для bundled-интерпретатора, в headless-режиме может быть избыточно, но ТЗ §3.2 запрещает менять логику при переносе — оставляем как есть.
3. **`pygame` в `tts/__init__.py` обёрнут в `try/except` в `_remove_with_retry`** (строка 191). Для headless-режима без pygame это безопасно (в except просто пропускается остановка mixer). Блокера нет.
4. **В `engine/tts/` все файлы (`cache.py`, `device.py`, `export.py`, `qc.py`, `utils.py`) содержат один и тот же однотипный блок импортов с `re, os, sys, time, datetime, unicodedata, threading, hashlib, torch, gc`** — это исторический шаблон, см. комментарии в коде ("файл-чанк для того, чтобы..."). Не трогаем.
5. **`engine/env_setup.py` — star-import фасад** (`from engine.env_core.diagnostics import *` и т.п.). При переносе остаётся как есть — он переэкспортирует всё из env_core, нужен как публичный API фасад.
6. **`engine/text_tools.py` существует, но не упомянут в ТЗ §3.1** — там 19 строк, не используется ни одним из переносимых модулей (проверено поиском имён из него по `engine/`). Не переношу, если не будет указания иначе.
7. **`engine/audio_backend.py`** (534 байт) — также не упомянут в ТЗ, сканирование не показало его импорта переносимыми файлами. Не переношу.
8. **В `engine/` есть дублирование каталог/модуль для `rvc_catalog`**: `engine/rvc_catalog.py` (1557 строк, монолит) и `engine/rvc_catalog/` (пакет, 7 файлов). В ТЗ указано переносить и каталог `engine/rvc_catalog/`, и файл `engine/rvc_catalog.py`? В §3.1 указан только `engine/rvc_catalog/` (весь пакет), но топ-уровневый `engine/rvc_catalog.py` в списке явно не упомянут. **Останавливаюсь и уточняю** (см. ниже).

---

## 9. Находка: старый монолит `engine/rvc_catalog.py` — мёртвый код

**Факт:** В корне `engine/` есть файл `engine/rvc_catalog.py` (1557 строк) — исходный монолит до рефакторинга TASK-008. Тот же путь занимает и пакет `engine/rvc_catalog/` (7 файлов). По правилам Python при импорте `engine.rvc_catalog` выигрывает пакет (его `__init__.py`), что я подтвердил загрузкой:
```
>>> import engine.rvc_catalog
>>> engine.rvc_catalog.__file__
'…/engine/rvc_catalog/__init__.py'
```
Полный grep по всему репозиторию:
- Внутри пакета (`engine/rvc_catalog/*.py`) все импорты вида `from engine.rvc_catalog import …` ссылаются на **подмодули пакета** (`._constants`, `.sources`, `.downloader`, …), а не на старый `.py`-файл.
- Вне пакета переносимые модули не делают `from engine.rvc_catalog import X` вообще (только GUI `engine/gui/presets.py`, `engine/gui/rvc_model_dropdown.py` используют `from engine import rvc_catalog` — это резолвится в пакет через `__init__.py`).
- Ни один файл не ссылается на старый монолит напрямую.

**Решение:** старый `engine/rvc_catalog.py` (1557 строк) **не переносить** в `ai_studio_core`. Это соответствует ТЗ §3.1, где явно указан только каталог `engine/rvc_catalog/ (весь пакет)`. GUI-вызовы `from engine import rvc_catalog` работают через пакетный `__init__.py`, и после переименования корня в `ai_studio_core` продолжат работать так же (с поправкой имени пакета).

**Примечание о scope:** из ТЗ §6 («Рефакторинг логики диагностики/апдейтера сверх устранения пунктов 2.1–2.2 — не делать заодно» и «не удалять легаси в исходнике»), я **не буду удалять** старый монолит из `_source_xtts_studio/` (копии исходника) — он просто не копируется в новый проект. Если хотите, могу отдельным маленьким диффом удалить и из исходника — но это уже за рамками ТЗ, и я не делаю это без явного указания.

---

## 10. Заключение детального аудита — готов к Этапу A

| Блокирующих проблем перед рефакторингом | **0** |
|---|---|
| Подтверждённых нарушений для исправления | 4 (#1, #2, #3 — в ТЗ; все три функции install-state найдены и изолированы в `env_settings.py:28-91`; #4 — `gpt_client.py:35`) |
| Обязательных отсутствующих конфигов (по согласованию с пользователем) | 3 (`.importlinter`, `check_architecture.py`, `architecture_gate.yml`) — **реконструирую** по описанию в ТЗ |
| Имя корневого пакета нового проекта | `ai_studio_core` (согласно ответу пользователя) |
| Чистая копия для diff | `_source_xtts_studio_clean/` уже создана и неизменна |

**План действий на Этап A:**
1. Создать `engine/env_core/install_state.py` и перенести туда 2 модульные переменные + 5 функций дословно из `engine/gui/env_settings.py` (строки 28–91).
2. В `engine/gui/env_settings.py` заменить исходные определения на re-export `from engine.env_core.install_state import …` (публичные имена сохраняются).
3. В `engine/env_core/rvc_setup.py` и `engine/env_core/torch_setup.py` заменить ленивый `from engine.gui.env_settings import …` на прямой `from engine.env_core.install_state import …` и удалить `try/except ImportError` обёртки.
4. В `engine/gpt_client.py` обернуть `from i18n import t as _t` в безопасный try/except с фолбэк-функцией.
5. Создать (реконструировать) `.importlinter` в корне `_source_xtts_studio/` по ТЗ §1.
6. Запустить `pip install import-linter packaging`, затем `lint-imports --config .importlinter` — ожидаем `Contracts: 3 kept, 0 broken`.
7. Снять baseline `pytest test/ -v` на чистой копии и прогнать на правленой — сравнить.
8. Сгенерировать `_source_xtts_studio_CHANGES.diff` по правилам §2.5 ТЗ.
9. Только после этого переходить к Этапу B (раскладка в `ai_studio_core/`).
