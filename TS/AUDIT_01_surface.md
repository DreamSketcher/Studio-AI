# Отчёт №1 — Поверхностный (pre-flight) аудит репозитория
**Дата:** 2026-07-18 (Europe/Moscow)
**Репозиторий:** `DreamSketcher/XTTS-Studio-AI`, ветка `main`
**Хеш HEAD:** `a28df4a Fix CI` (shallow clone, depth=1)
**Этап:** ПЕРЕД любыми правками (до Этапа A по ТЗ)

---

## 1. Резюме

Репозиторий клонирован успешно, базовая структура соответствует описанию в ТЗ.
**Все 4 нарушения графа импортов, перечисленные в ТЗ (таблица из §1), подтвердились по факту кода.**
Дополнительно обнаружены 2 несоответствия с ТЗ, о которых нужно знать перед началом работ.

| Категория              | Оценка | Комментарий |
|------------------------|--------|-------------|
| Структура `engine/`    | ✅      | Полностью совпадает с ТЗ (раздел 3.1) |
| Нарушения #1–#3 (gui→env) | ✅ подтверждены | Три ленивых `try/except ImportError` импорта из `engine.gui.env_settings` в `env_core/rvc_setup.py` и `env_core/torch_setup.py` |
| Нарушение #4 (i18n)    | ✅ подтверждено | Жёсткий `from i18n import t as _t` на строке 35 `engine/gpt_client.py`, без try/except |
| Файл `.importlinter`   | ⚠️ **отсутствует** | В корне репозитория нет ни `.importlinter`, ни секции `[tool.importlinter]` в `pyproject.toml`. ТЗ опирается на прогон `lint-imports --config .importlinter`, но этого конфига нет в текущем HEAD. Архитектурный гейт придётся либо создать (по слоям, описанным в ТЗ), либо уточнить у пользователя. |
| `tools/check_architecture.py`, `tools/check_plugin_deps.py` | ⚠️ **отсутствуют** | В каталоге `tools/` есть только 23 скрипта (ruff_new_files_gate, pip_audit_gate, generate_sbom, build_reproducible_release и др.), но ни `check_architecture.py`, ни `check_plugin_deps.py` в репе нет. ТЗ в разделе 3.4 ссылается на них как на уже готовые. |
| CI-workflow `.github/workflows/architecture_gate.yml` | ⚠️ **отсутствует** | В `.github/workflows/` присутствуют только `ci.yml`, `codeql.yml`, `release.yml`. ТЗ просит перенести уже существующий `architecture_gate.yml`, но его нет в репе. |
| Исключённые из переноса файлы | ✅      | `engine/batch_window.py` (tkinter GUI, не импортируется ни одним другим модулем `engine/`), `engine/gui_cyrillic_checker.py` — на месте. |

---

## 2. Общие метрики кода (tree snapshot)

- Коммит: `a28df4a` ("Fix CI")
- Общий размер `engine/` по `.py`-файлам: **~47 066 строк**
- `engine/gui/` пакет: 42 файла (подпакет `chat_window/`)
- `engine/env_core/`: 6 файлов (`__init__.py`, `cpu_gpu.py`, `diagnostics.py`, `llama_setup.py`, `rvc_setup.py`, `torch_setup.py`)
- `engine/tts/`: 5 файлов (`__init__.py`, `cache.py`, `device.py`, `export.py`, `qc.py`, `utils.py`) — 6
- `engine/rvc_catalog/`: 2 файла (пакет) + топ-уровневый `engine/rvc_catalog.py` (1557 строк)
- Тесты: 66 файлов в `test/` (не все релевантны переносимому ядру — есть UI-тесты `test_*ui*`, `test_batch_window`, `test_animation_manager`, `test_generation`, `test_voice_panel` и т.п.)

---

## 3. Детально по четырём нарушениям ТЗ

### 3.1 Нарушение #1 — `engine/env_core/rvc_setup.py` :274
```python
from engine.gui.env_settings import _can_clear_diagnostics_cache
```
Обёрнуто в `try/except ImportError` с заглушкой `return True`.
**Статус:** подтверждено, подлежит исправлению (перенос в `env_core/install_state.py`).

### 3.2 Нарушение #2 — `engine/env_core/torch_setup.py` :257
```python
from engine.gui.env_settings import (
    _acquire_install_lock, _release_install_lock, _get_current_install_type,
)
```
Обёрнуто в `try/except ImportError` с `pass`-заглушкой.
**Статус:** подтверждено.

### 3.3 Нарушение #3 — `engine/env_core/torch_setup.py` :458
```python
from engine.gui.env_settings import _release_install_lock, _set_install_cancelled
```
Обёрнуто в `try/except ImportError` с `pass`-заглушкой.
**Статус:** подтверждено.

### 3.4 Нарушение #4 — `engine/gpt_client.py` :35
```python
from i18n import t as _t
```
Жёсткий импорт, без try/except.
**Статус:** подтверждено.

---

## 4. Подтверждено: ломающих "сюрпризов" нет

4.1 **`engine/batch_window.py`** — tkinter-GUI файл, но на него **никто в `engine/` не ссылается** (проверено grep-ом на `from engine.batch_window` / `import engine.batch_window` — ноль вхождений). Безопасно не переносить, как указано в ТЗ §3.1.

4.2 **`engine/gui_cyrillic_checker.py`** — на него тоже ссылок внутри `engine/` нет. Безопасно не переносить.

4.3 **`engine/env_core/diagnostics.py`** действительно импортирует `customtkinter`, но только внутри `try/except Exception` в диагностической функции (строки ~601–604) — это не ломает headless-import. ✅

4.4 **`engine/gui/colors.py`** импортируется из `engine/batch_window.py` (строка 28). Но т.к. сам `batch_window.py` не переносится, то и этот импорт уходит вместе с ним. В переносимых файлах (`rvc_setup.py`, `torch_setup.py`, `gpt_client.py`) ссылок на `engine.gui.colors` нет. ✅

4.5 **В `engine/` вне `gui/` нет других жёстких импортов `tkinter`/`customtkinter`**, кроме `batch_window.py`, который мы исключаем. ✅

4.6 **В `engine/` вне `gui/` нет других жёстких импортов `i18n`**, кроме `gpt_client.py:35` (нарушение #4). ✅

4.7 **Функции install-state** действительно лежат в `engine/gui/env_settings.py` (строки 28–91):
- `_INSTALL_LOCK = threading.RLock()` (строка 28)
- `_INSTALL_STATE = {"running": False, "type": None, "cancelled": False}` (строка 29)
- `_acquire_install_lock(install_type)` (строка 32)
- `_release_install_lock()` (строка 44)
- `_get_current_install_type()` (строка 56)
- `_set_install_cancelled()` (строка 61)
- `_can_clear_diagnostics_cache()` (строка 91)

Всё это должно переехать в `engine/env_core/install_state.py` без изменения логики — чистый move.

---

## 5. Обнаруженные расхождения с ТЗ (требуют решения)

### 5.1 ❗ Отсутствует `.importlinter`
ТЗ §2.1/2.3/3.3 опирается на конфиг `.importlinter` с 11 слоями (от `engine.atomic_write` до `engine.gui`) и тремя контрактами (`env_core_independence`, `ai_modules_independence`, `?`). В текущем HEAD этого файла нет, и в `pyproject.toml` секции `[tool.importlinter]` тоже нет.
**Варианты:**
- (а) у вас этот файл есть локально (из более раннего чата, на который ссылается ТЗ в §1: *"конфиг `.importlinter` (см. отдельный файл, уже предоставлен ранее в этом чате)"*) — пришлите его, и я использую как источник истины;
- (б) я могу восстановить конфиг по описанию слоёв из ТЗ §1 и по 4 нарушениям из таблицы ignore_imports — но это будет реконструкция, не оригинал;
- (в) работать без import-linter на Этапе A, проверяя нарушения статически grep-ом, и сгенерировать канонический `.importlinter` уже для нового проекта (Этап B, §3.3).

### 5.2 ❗ Отсутствуют `tools/check_architecture.py` и `tools/check_plugin_deps.py`
ТЗ §3.3 и §3.4 ссылается на эти файлы как на уже существующие ("см. ранее переданный инструмент"). В репе их нет. Нужно либо получить их от вас, либо я создам минимальные реализации под формат, который они ожидают.

### 5.3 ❗ Отсутствует `.github/workflows/architecture_gate.yml`
ТЗ §3.4 просит перенести "уже подготовленный" workflow. В репе только `ci.yml`, `codeql.yml`, `release.yml`. В `ci.yml` уже есть шаг `Strict ruff gate for new files`, `pip-audit`, `security docs/SBOM`, и матрица `tests` на `ubuntu-latest`+`windows-latest`. Мне нужно создать `architecture_gate.yml` с нуля, адаптируя под структуру нового проекта.

### 5.4 ⚠️ Верхнеуровневый файл `engine/batch_window.py` ссылается на `engine.gui.colors`
Это не проблема при корректном выполнении §3.1 ТЗ (мы его **не** переносим), но сто́ит убедиться, что в `engine/gui/` не осталось кросс-ссылок, которые через что-то ещё утянут `colors.py` в переносимое ядро. Проверка по grep в §4.1 это уже подтвердила — ссылок нет, кроме самого `batch_window.py`.

### 5.5 ⚠️ Макос (`macos-latest`) отсутствует в CI-матрице
Существующий `ci.yml` в матрице `tests` использует только `[ubuntu-latest, windows-latest]`. ТЗ §3.4 просит добавить отдельный job с матрицей `windows-latest / macos-latest / ubuntu-latest` — т.е. для нового проекта это новая матрица, а не копия существующей.

---

## 6. Зависимости и окружение

- `requirements.txt` содержит **136+** пакетов, включая GUI: `customtkinter==6.0.0`, `pygame==2.6.1`, `tkinterdnd2==0.4.4.1`;
- `requirements.lock` присутствует, есть проверка `tools/check_requirements_lock.py`;
- Для headless-ядра (ai_studio_core) по грубой оценке достаточно подмножества: `torch`, `torchaudio`, `numpy`, `scipy`, `librosa`, `soundfile`, `pydub`, `pyworld`, `praat-parselmouth`, `transformers`, `TTS`, `spacy`, `huggingface_hub`, `safetensors`, `requests`, `cryptography`, `packaging`, `pyyaml`, `psutil`, `loguru` и транзитивные. Точный перечень определю на Этапе B детальным аудитом.

---

## 7. Риски и рекомендации перед стартом

1. **Самый большой техдолг вне ТЗ:** `engine/env_core/diagnostics.py` (85 КБ / 1800+ строк) — на него стоит завести отдельный тикет. В рамках этой задачи не трогаем (§6 ТЗ явно запрещает).
2. **Дублирование имён пакет/модуль:** `engine/rvc_catalog/` (пакет) и `engine/rvc_catalog.py` (модуль 1557 строк) сосуществуют рядом — это потенциальный источник путаницы с импортами; не трогаем по ТЗ §3.2 (*"Перенос = git mv эквивалент + правка путей импорта"*), но отмечаю.
3. **Тесты UI:** около 15–20 тестов в `test/` импортируют `engine.gui.*` или `customtkinter`/`tkinter` (например `test_batch_window.py`, `test_animation_manager.py`, `test_header_panel.py`, `test_presets.py`, `test_settings_ui.py`, `test_styles_menu.py`, `test_theme_manager.py`, `test_voice_panel.py` и т.д.). Их копировать в `ai_studio_core/` нельзя — это проверю детальным аудитом при Этапе B.
4. **`i18n.py` (117 КБ)** лежит в корне проекта, а не в `engine/`. Поскольку в новом проекте он не переносится (в списке §3.1 нет), фолбэк в `gpt_client.py` (§2.2 ТЗ) является обязательным — без него headless-импорт падает.

---

## 8. Заключение

Поверхностный аудит **пройден условно**. К правкам Этапа A можно приступать, но есть **3 блокирующих вопроса** по отсутствующим файлам конфигурации (`.importlinter`, `tools/check_architecture.py`, `tools/check_plugin_deps.py`, `.github/workflows/architecture_gate.yml`). Рекомендую:
- либо прислать недостающие файлы (они упоминаются как "уже предоставленные ранее", но в этом чате их нет);
- либо дать добро на их восстановление по описанию в ТЗ (я так и сделаю в отсутствие другого указания, с явной пометкой "reconstructed from spec" в отчётах).

**План следующего шага:**
1. Получить подтверждение по п. 5.1–5.3 от пользователя (либо идти с реконструкцией).
2. Сделать **чистый снимок** `_source_xtts_studio/` (`cp -a` в `_source_xtts_studio_clean/`) для последующего формирования unified-diff.
3. Провести **детальный аудит** перед рефакторингом: собрать точный граф импортов для каждого переносимого файла, список всех внешних зависимостей (stdlib + third-party + cross-engine), список тестов, которые остаются/уходят, и выложить `AUDIT_02_detailed.md`.
4. Приступить к правкам Этапа A (§2 ТЗ).
