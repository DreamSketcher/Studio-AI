# Отчёт №4 — Этап B выполнен, итоговый (детальный аудит по результату рефакторинга)
**Дата:** 2026-07-18
**Этап:** Логический этап B по ТЗ (раскладка файлов в новый проект `ai_studio_core/`)

---

## 1. Итоговая сводка по критериям приёмки ТЗ §5

| № | Критерий приёмки | Фактический результат |
|---|---|---|
| 1 | `lint-imports` в `_source_xtts_studio/` — 3 kept, 0 broken, `ignore_imports` пуст | ✅ **1 контракт KEPT, 0 broken, ignore_imports пустой.** Вместо 3 контрактов, пересекающихся по смыслу, используется один общий контракт `layered_architecture` (объяснение — п.2.1 отчёта №3). |
| 2 | Существующие pytest-тесты проходят без изменений тестового кода (на исходнике) | ✅ 193 быстрых тестов пройдены до и после правок Этапа A — без регрессий. Тяжёлые тесты, требующие `torch`/`TTS`/`customtkinter`, в sandbox не запускались по причине отсутствия этих пакетов; на регрессию они не влияют, т.к. правки Этапа A не затрагивают их логику (только меняют путь импорта инсталл-лока). |
| 3 | В `ai_studio_core/` `python -c "import ai_studio_core.env_core"` работает без `tkinter`/`customtkinter`/`PySide6` | ✅ **OK.** Headless-импорт проходит, ни один из модулей `tkinter`/`customtkinter`/`PySide`/`PyQt` не подтягивается в `sys.modules` (проверка прямым сканированием `sys.modules`). |
| 4 | `lint-imports` в `ai_studio_core/` — 0 нарушений, без `ignore_imports` | ✅ **`Contracts: 1 kept, 0 broken`**, `ignore_imports` отсутствует в конфиге. Проанализировано **51 файл, 84 зависимости** (против 125/659 в исходнике с GUI). |
| 5 | `_source_xtts_studio_CHANGES.diff` присутствует, читаем, покрывает все файлы из §2.5 ТЗ | ✅ Файл лежит в `/home/user/_source_xtts_studio_CHANGES.diff`, **314 строк**: шапка с датой и результатами прогона, содержимое нового `install_state.py`, новый `.importlinter`, unified-diff по 4 изменённым файлам (`engine/gui/env_settings.py`, `engine/env_core/rvc_setup.py`, `engine/env_core/torch_setup.py`, `engine/gpt_client.py`). |
| 6 | CI-workflow нового проекта готов к прогону (статически валиден) | ✅ YAML в `.github/workflows/architecture_gate.yml` синтаксически валиден (проверено через `yaml.safe_load`), содержит 2 job-а: `architecture` (lint-imports + plugin manifest) и `headless-tests` (матрица `ubuntu-latest / windows-latest / macos-latest`, Python 3.11, без GUI, запуск быстрых тестов). |

---

## 2. Содержимое финального артефакта `ai_studio_core/`

```
ai_studio_core/
├── README.md                                          # Описание пакета и структуры
├── pyproject.toml                                     # PEP-517/pep-621 мета-данные, экстры [ml]/[local-llm]/[rvc]/[dev]
├── requirements-core.txt                              # Минимальные обязательные зависимости
├── .importlinter                                      # Архитектурные слои
├── .github/
│   └── workflows/
│       └── architecture_gate.yml                     # CI: architecture gate + headless tests (3 ОС)
├── models/
│   └── dummy.model.example.json                      # Пример манифеста плагина/модели (валиден для check_plugin_deps)
├── tools/
│   ├── check_architecture.py                         # CLI для запуска import-linter
│   └── check_plugin_deps.py                          # Валидатор JSON-манифестов плагинов
├── ai_studio_core/                                   # Сам пакет (51 .py-файл)
│   ├── __init__.py
│   ├── atomic_write.py · paths.py · logging_utils.py
│   ├── text_utils.py · secret_store.py · settings_store.py
│   ├── lazy_loader.py · error_report.py
│   ├── env_setup.py · env_core/ (7 файлов, включая install_state.py)
│   ├── ai_conductor.py · gpt_client.py · local_llm_client.py
│   ├── normalizer.py · chunker.py · smart_pauses.py
│   ├── prosody_layer.py · de_esser.py · reference_processor.py
│   ├── word_replacer.py · voice_manager.py
│   ├── tts.py · tts_runner.py → в реальности: tts/ пакет (6 файлов) + tts_runner.py
│   ├── rvc_pipeline.py · rvc_catalog/ (7 файлов)
│   ├── updater.py · update_signing.py · release_hashing.py
│   ├── validation.py · history_store.py
│   ├── task_manager.py · task_models.py · output_naming.py
│   └── tts/ (cache.py, device.py, export.py, qc.py, utils.py, __init__.py)
└── test/
    └── 30 тестовых файлов (юнит-тесты на headless-ядро)
```

**Всего файлов в поставке:** 99 (из них 51 — `.py`-файлы пакета, 30 — тесты, 7 — конфиги/документация/тулзы/CI, 1 — пример манифеста модели).

---

## 3. Детальный аудит переименований и корректности переноса

### 3.1 Корень пакета
- Имя корневого пакета: `ai_studio_core` (как согласовано с пользователем).
- Все строки импорта вида `from engine.xxx`, `import engine.xxx`, `from engine import xxx`, `import engine` в 51 Python-файле пакета и 30 тестах заменены на `ai_studio_core.xxx` (проверено grep-ом: **0 остаточных строк `from/import engine...`** в коде).
- Относительные импорты (`from .device import detect_device`, `from ..de_esser import ...`) не тронуты — они корректно работают после переименования корня.

### 3.2 Публичный API не нарушен
- Все имена, которые были доступны в исходном `engine.*` (функции, классы, константы), доступны в `ai_studio_core.*` с теми же именами.
- Фасад `ai_studio_core.env_setup` продолжит делать star-import из `env_core.*` и переэкспортировать внутренние помощники (в том числе `_read_pip_output`) — поведение идентично исходному.
- `tts_runner.py` в своём относительном импорте (`from .tts import ...`) не изменился.

### 3.3 install_state.py
- Перенесён **дословно** из `engine/gui/env_settings.py` строки 28–93 (сверено по коду).
- Дополнительно перенесена `_is_install_running()` как вспомогательная, вызываемая из `_can_clear_diagnostics_cache()` (без неё в новом модуле была бы неразрешённая ссылка).
- `engine/gui/env_settings.py` (на исходнике, не в новом проекте) импортирует эти имена через `from engine.env_core.install_state import (...)` — реэкспорт, публичные имена для остального GUI сохранены.

### 3.4 i18n-фолбэк
- В `ai_studio_core/gpt_client.py` и в исходнике блок try/except с identity-фолбэком работает корректно.
- Проверка в изолированном PYTHONPATH без `i18n.py`:
  ```
  OK: i18n отсутствует в изолированном окружении
  OK: gpt_client импортирован, _t работает как identity-фолбэк
  ```

### 3.5 GUI-импорты
- **0** импортов `tkinter`, `customtkinter`, `tkinterdnd2`, `PySide`, `PyQt` в пакете `ai_studio_core/` (проверено grep-ом по всем .py).
- `diagnostics.py` сохраняет `try/except` вокруг `import customtkinter` в диагностической функции (это не импортирует модуль, если он не установлен — не нарушает headless).
- **0** ссылок на `ai_studio_core.gui` (в новом проекте GUI-слоя вообще нет).
- Старый монолит `engine/rvc_catalog.py` (1557 строк) **не перенесён** — подтверждено, что в исходнике никто на него не ссылается (см. отчёт №2, п.9).

### 3.6 Исключённые из переноса файлы (согласно ТЗ §3.1)
- Весь `engine/gui/` — не перенесён. ✅
- `engine/batch_window.py` (tkinter GUI) — не перенесён. ✅
- `engine/gui_cyrillic_checker.py` (специфично для старого GUI) — не перенесён. ✅
- Дополнительно не перенесены не упомянутые в ТЗ файлы: `engine/audio_backend.py`, `engine/text_tools.py` (проверено — не импортируются переносимыми модулями).

---

## 4. Результаты запуска инструментов

### 4.1 import-linter на новом проекте
```
Analyzed 51 files, 84 dependencies.
-----------------------------------
layered_architecture KEPT
Contracts: 1 kept, 0 broken.
```

### 4.2 check_architecture.py
Запускает `importlinter.cli.lint_imports_command` напрямую — возвращает exit code 0, контракт KEPT. ✅

### 4.3 check_plugin_deps.py
```
[check_plugin_deps] OK: проверено 1 манифест(а/ов), ошибок нет.
```

### 4.4 Headless pytest (без torch/TTS/customtkinter)
**269 passed, 0 failed** за 0.56s. ✅
Примечание: Тесты, требующие `torch`/`TTS`/`rvc-python`/`llama-cpp-python`/`customtkinter`, по умолчанию не запускаются в быстром CI-добе `headless-tests`; они лежат рядом и будут запускаться при установке соответствующих extras в отдельных job-ах (не входят в минимальную поставку, подготовлены к переносу).

### 4.5 Headless smoke-import
```
import ai_studio_core.env_core                    # OK
import ai_studio_core.env_core.install_state      # OK
import ai_studio_core.gpt_client                  # OK (i18n-fallback работает)
...все нижние слои импортируются без подтягивания tkinter/customtkinter...
```
Сканирование `sys.modules` после серии импортов показывает **0** загруженных GUI-модулей. ✅

---

## 5. Результаты Этапа A (исходная копия) — сводка для контекста

Правленая копия `_source_xtts_studio/`:
- import-linter на 125 файлах, 659 зависимостей → **1 kept, 0 broken**.
- Быстрые тесты: **193 passed** на baseline, **193 passed** после правок (без регрессий).
- Сгенерирован diff-отчёт `_source_xtts_studio_CHANGES.diff` — он лежит в `/home/user/`.

---

## 6. Отклонения от ТЗ и замечания (прозрачность)

1. **Вместо трёх отдельных контрактов** (`env_core_independence`, `ai_modules_independence`, `gui_is_top_layer`) используется **один** контракт `layered_architecture`, который проверяет все три инварианта одновременно (слои строго упорядочены сверху вниз). Практика показала, что три контракта с одинаковым корневым списком слоёв взаимно избыточны и дают те же нарушения, но в другом формате вывода.
2. **В `.importlinter` для нового проекта отсутствует GUI-слой** (в новом проекте GUI пока нет, строится позже на PySide6). Конфиг для исходника (в `_source_xtts_studio/.importlinter`) содержит GUI в самом верху иерархии.
3. **Тесты, перенесённые в новый проект, не были «изменены» в логике**, но строковые литералы `"engine.xxx"`, передаваемые в `monkeypatch.setattr(...)` / `unittest.mock.patch(...)` / `sys.modules[...]`, были массово заменены на `"ai_studio_core.xxx"` (sed-ом) — это ожидаемая правка путей, а не изменение тестовой логики. В `test_smart_pauses.py` поправлен вызов фикстуры `engine` (была затёрта sed-заменой, восстановлено).
4. **`py-cpuinfo`** импортируется как модуль `cpuinfo`, в зависимостях указан как `py-cpuinfo` (pip-name) — это соответствует исходнику.
5. **Тяжёлые зависимости** (`torch`, `torchaudio`, `TTS`, `llama-cpp-python`, `rvc-python` вынесены в extras `[ml]`, `[local-llm]`, `[rvc]`), а не в core-requirements — это соответствует факту, что модули, их использующие (`tts/device.py`, `rvc_pipeline.py`, `local_llm_client.py`, `env_core/torch_setup.py`, `env_core/rvc_setup.py`, `env_core/llama_setup.py`), делают импорт **лениво** (внутри функций), поэтому headless-импорт env_core возможен без установленных ML-библиотек (что и проверено в п.4.5).

---

## 7. Что делать пользователю дальше (руководство к действию)

1. **Забрать три артефакта** из рабочего пространства агента:
   - `/home/user/_source_xtts_studio/` — рабочая копия с правками Этапа A;
   - `/home/user/_source_xtts_studio_CHANGES.diff` — обязательный diff-отчёт Этапа A;
   - `/home/user/ai_studio_core/` — основной результат, готовая файловая структура нового проекта.
   `/home/user/_source_xtts_studio_clean/` можно удалить после того, как вы убедитесь, что diff-отчёт вас устраивает.

2. **Локальная проверка у вас** (с установленным `torch`/`TTS`/`rvc-python` по желанию):
   ```bash
   cd ai_studio_core
   pip install -r requirements-core.txt
   pip install import-linter pytest pytest-timeout
   python tools/check_architecture.py    # должен выдать "Contracts: 1 kept, 0 broken"
   python tools/check_plugin_deps.py     # "OK: ..."
   pytest test/ -v                       # быстрые headless тесты
   ```

3. **Создание git-репозитория и CI** — по инструкциям ТЗ: вы делаете `git init`, привязываете remote, пушите — файл `.github/workflows/architecture_gate.yml` готов и запустится на GitHub Actions автоматически при первом push-е в main/PR.

4. **Дальнейшие этапы (вне этого ТЗ)** — по уставу проекта: PySide6 GUI-обвязка и plugin-архитектура на dummy-модели.

---

## 8. Приложение: перечень всех отчётов этой серии

| Файл | Описание |
|---|---|
| `AUDIT_01_surface.md` | Поверхностный аудит до начала работ |
| `AUDIT_02_detailed.md` | Детальный аудит перед рефакторингом (граф импортов, зависимости, тесты, матрица приёмки) |
| `AUDIT_03_stage_a.md` | Отчёт по Этапу A (правки в исходнике) |
| `AUDIT_04_final.md` | Этот файл — итоговый отчёт по завершении Этапа B |
| `_source_xtts_studio_CHANGES.diff` | Обязательный unified-diff от ТЗ §2.5 |
