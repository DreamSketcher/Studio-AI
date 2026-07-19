# AI Studio — подробная документация проекта

**Версия документа:** 2026-07-19
**Состояние кода:** этапы 06–11 завершены, 620 тестов зелёные, `lint-imports` — KEPT.

---

## Содержание

1. [Обзор проекта](#1-обзор-проекта)
2. [Быстрый старт](#2-быстрый-старт)
3. [Архитектура](#3-архитектура)
4. [Структура репозитория](#4-структура-репозитория)
5. [Ядро `ai_studio_core`](#5-ядро-ai_studio_core)
6. [UI-слой на PySide6](#6-ui-слой-на-pyside6)
7. [Потоки данных (сценарии)](#7-потоки-данных-сценарии)
8. [Конфигурация и персистентность](#8-конфигурация-и-персистентность)
9. [Интернационализация (i18n)](#9-интернационализация-i18n)
10. [Бэкенды и провайдеры](#10-бэкенды-и-провайдеры)
11. [Безопасность](#11-безопасность)
12. [Тестирование](#12-тестирование)
13. [Руководство разработчика](#13-руководство-разработчика)
14. [Известные ограничения](#14-известные-ограничения)
15. [История этапов 06–11](#15-история-этапов-0611)
16. [Приложение: справка по ключевым API](#16-приложение-справка-по-ключевым-api)

---

## 1. Обзор проекта

**AI Studio** — настольное приложение для работы с аудио- и LLM-инструментами:
синтез речи (TTS), чат с языковыми моделями, конвертация голоса (RVC),
генерация изображений, визуальный пайплайн обработки. Проект извлечён из
публичного монолита [XTTS-Studio-AI](https://github.com/DreamSketcher/XTTS-Studio-AI)
и разделён на две части:

- **Headless-ядро `ai_studio_core`** (`ai_studio_core/ai_studio_core/`) — вся логика
  без графики: TTS/RVC-пайплайны, LLM-клиенты, обработка текста/аудио,
  управление окружением, обновления, хранилища. Импортируется и тестируется
  без PySide6 (кроме UI-подпакета).
- **UI-слой `ai_studio_core/ai_studio_core/ui/`** — PySide6-приложение поверх ядра:
  workspaces, dock-панели, контроллеры-посредники.

### Принципы проекта (этапы 06–11)

1. **Без заглушек.** В интерфейсе и контроллерах нет демо-данных,
   файлов-пустышек и фальшивых результатов. Список пуст — показывается
   честное пустое состояние.
2. **Честные гейты.** Если окружение не даёт реальную функцию (нет torch,
   нет API-ключа, нет бинарника) — пользователь получает понятную ошибку или
   индикатор недоступности (📥/❌), а не подделку.
3. **Вся новая функциональность — с тестами.** Тесты ходят на настоящие
   локальные ресурсы: реальный espeak/ffmpeg, реальный HTTP-сервер на
   loopback, реальные файлы в tmp-каталогах.
4. **Слоистая архитектура** фиксируется контрактом import-linter — регрессии
   слоёв ломают сборку.

---

## 2. Быстрый старт

### Требования

- Python ≥ 3.10 (разработка и CI велись на 3.13).
- Для GUI: PySide6 ≥ 6.6 (проверено на 6.11).
- Для синтеза без ML: `espeak-ng` (apt/brew) и `ffmpeg` (экспорт mp3/flac/ogg).
- Опционально: extras `.[ml]` (torch+TTS для XTTS v2), `.[rvc]`,
  `.[local-llm]`, `.[dev]` (тесты/линтеры).

### Установка и запуск

```bash
cd ai_studio_core
pip install -e ".[gui]"      # ядро + PySide6
python run_gui.py            # запуск GUI
```

`run_gui.py` → `ai_studio_core.ui:run()` → QApplication + тёмная тема +
`MainWindow`. Альтернатива без установки пакета:

```bash
cd ai_studio_core
python -c "from ai_studio_core.ui import run; run()"
```

### Headless-использование ядра

```python
from ai_studio_core import espeak_tts, gpt_client

res = espeak_tts.synthesize("Привет, мир")         # реальный WAV
print(res.path, res.duration_sec)

gpt_client.set_api_key("gsk_...", "groq")
print(gpt_client.chat("Кратко о проекте"))
```

---

## 3. Архитектура

### 3.1 Слои

Слойность закреплена в `.importlinter` (контракт `layered_architecture`,
**KEPT**). Каждый слой импортирует только себя и слои ниже:

```
┌─────────────────────────────────────────────────────────────────┐
│ UI (ui.workspaces / ui.panels / ui.dialogs / ui.widgets)        │  не входит
├─────────────────────────────────────────────────────────────────┤
│ Контроллеры (ui.controllers — QObject, WorkerThread)            │  в контракт
├═════════════════════════════════════════════════════════════════┤  import-linter:
│ ai_studio_core.tts          — TTS-пайплайн (cache/device/qc)    │
│ ai_studio_core.rvc_catalog  — каталог и скачивание RVC-моделей  │
│ ai_studio_core.rvc_pipeline — конвертация голоса                │
│ ai_studio_core.ai_conductor — оркестрация AI-шагов              │
│ ai_studio_core.gpt_client   — облачные LLM (OpenAI-совместимые) │
│ ai_studio_core.local_llm_client — локальные GGUF-модели         │
│ ai_studio_core.env_core     — диагностика/установка окружения   │
│ ai_studio_core.logging_utils— логирование                       │
│ ai_studio_core.paths        — все пути проекта                  │
│ ai_studio_core.atomic_write — атомарная запись файлов           │
└─────────────────────────────────────────────────────────────────┘
```

UI **никогда** не импортирует engine-модули напрямую из виджетов — только
через контроллеры (`ui/controllers/*`), которые переводят UI-события в
вызовы ядра, а результаты — обратно в сигналы Qt. Тяжёлые операции идут в
`WorkerThread`, см. §6.3.

### 3.2 Поток сигналов

Виджеты общаются с контроллерами только сигналами/слотами Qt:

```
Workspace (view)  ──signal──▶  Controller  ──import──▶  Core
Workspace (view)  ◀─signal──   Controller  ◀─result──   Core (worker thread)
```

---

## 4. Структура репозитория

```
Studio-AI/                         ← корень репозитория
├── AUDIT_01…AUDIT_11.md           ← аудиты по этапам (рус.)
├── STAGE_06…STAGE_11.diff         ← диффы этапов (git show)
├── DOCUMENTATION.md               ← этот документ
├── README.md, uploads/            ← исходные материалы проекта
├── ui_workspace_*.png             ← скриншоты подтверждения
└── ai_studio_core/                ← основной проект
    ├── pyproject.toml             ← пакет ai-studio-core 0.1.0, extras
    ├── requirements-core.txt
    ├── run_gui.py                 ← точка входа GUI
    ├── README.md
    ├── .importlinter              ← контракт слоёв
    ├── json/                      ← рантайм-данные (settings, history…)
    ├── logs/                      ← лог-файлы
    ├── models/                    ← локальные модели (rvc/, …)
    ├── tools/                     ← check_architecture.py, check_plugin_deps.py
    ├── test/                      ← 42 файла, ~653 теста
    └── ai_studio_core/            ← пакет (ядро ~20.6k строк)
        ├── <модули ядра — §5>
        ├── env_core/              ← окружение: diagnostics, cpu_gpu, install_state,
        │                            llama_setup, rvc_setup, torch_setup
        ├── rvc_catalog/           ← каталог RVC: sources/downloader/cache/metadata/
        │                            preview/_constants
        ├── tts/                   ← TTS-подпакет: cache, device, export, qc
        └── ui/                    ← PySide6 слой — §6
            ├── app.py             ← run(): QApplication, палитра, QSS, язык
            ├── main_window.py     ← MainWindow — композиция всего
            ├── controllers/       ← base, tts, chat, image, model, queue
            ├── workspaces/        ← base, tts, chat, image, pipeline
            ├── panels/            ← history, inspector, model_hub, queue, settings
            ├── widgets/           ← waveform, status_bar, model_selector, …
            ├── dialogs/           ← about, env_setup_wizard, model_download, error_report
            └── theme/             ← tokens.py, palette.py, stylesheet.qss
```

---

## 5. Ядро `ai_studio_core`

### 5.1 Файлы первого уровня

| Модуль | Назначение |
|---|---|
| `paths.py` | Все пути: `BASE_DIR`, `JSON_DIR`, `OUTPUT_DIR`, `MODEL_DIR`, `LOG_DIR`, пути настроек/истории. Неизвестные имена — безопасный fallback через `__getattr__` (PEP 562) для совместимости со старым кодом. |
| `atomic_write.py` | Атомарная запись файлов (tmp + `os.replace`), защита от усечения JSON при сбое. |
| `logging_utils.py` | Настройка loguru (файл `logs/xtts_studio.log`, ротация). |
| `i18n.py` | Словари EN/RU (186 ключей, паритет обеспечен), `set_language`, `t(key)` — никогда не кидает исключений. |
| `secret_store.py` | Защита API-ключей: Windows DPAPI (`dpapi:v1:`), тестовый режим (`XTTS_TEST_SECRET_STORE=1` → `test-only:v1:`), иначе **fail-closed** `SecretStoreUnavailable`. |
| `settings_store.py` | Чтение/запись `json/settings.json`. |
| `history_store.py` | Журнал генераций `json/history.json` (`save_history(task)`), атомарно. |
| `output_naming.py` | Имена выходных файлов из текста (`_make_output_name(text)` → `outputs/….wav`). |
| `normalizer.py` | `TextNormalizer` — нормализация текста для TTS (числа→слова через num2words и пр.). |
| `chunker.py` | `TextChunker.chunk_text` — разбиение длинного текста на чанки по предложениям. |
| `text_utils.py` | Вспомогательный разбор текста/списков. |
| `word_replacer.py` | Словарные замены (`json/word_rules.json`). |
| `smart_pauses.py` | Вставка/нормализация пауз для речи. |
| `prosody_layer.py` | Просодическая разметка. |
| `de_esser.py` | Де-эссер (подавление сибилянтов в аудио). |
| `reference_processor.py` | Обработка reference-аудио для клонирования голоса. |
| `voice_manager.py` | Управление голосами/референсами (`reference/`). |
| `validation.py` | Валидация ввода и настроек. |
| `error_report.py` | Сбор диагностических отчётов об ошибках. |
| `lazy_loader.py` | Ленивые прокси тяжёлых модулей (torch, TTS) — импорт по требованию. |
| `task_models.py` / `task_manager.py` | Модель задач и менеджер фоновых задач ядра. |
| `tts_runner.py` | Алиас-фасад на TTS-стек. |
| `ai_conductor.py` | Оркестрация многошаговых AI-операций (TTS+GPT цепочки). |
| `gpt_client.py` | Облачные LLM — подробно §10.2. |
| `local_llm_client.py` | Локальные GGUF через llama-cpp (extras `.[local-llm]`). |
| `env_setup.py` | Фасад реэкспорта `env_core.*` (совместимость). |
| `env_core/` | Диагностика/установка окружения: `diagnostics.py` (полная проверка, кэши, pip-активность), `cpu_gpu.py`, `install_state.py`, `torch_setup.py`, `rvc_setup.py`, `llama_setup.py`. |
| `rvc_catalog/` | Каталог голосов RVC: `sources.py` (seed/кэш/сеть, voice-models.com), `downloader.py` (прямые URL/HF/GDrive, zip→pth, SHA256, отмена, прогресс), `metadata.py` (.metadata/*.json, trust по SHA-256), `cache.py`, `preview.py`. |
| `rvc_pipeline.py` | Конвертация голоса (rvc-python, extras `.[rvc]`). |
| `tts/` | Подпакет TTS: `cache.py`, `device.py`, `export.py`, `qc.py` (контроль качества). |
| `updater.py` | Проверка/загрузка обновлений (`_urlopen_with_retry`, SSL-контекст). |
| `update_signing.py` | Ed25519-подпись манифестов обновлений. |
| `release_hashing.py` | Хеширование релизных файлов. |

### 5.2 Ключевые внутренние инварианты

- Все JSON-файлы пишутся атомарно (`atomic_write`, `_write_all_settings`).
- Настройки/историю/outputs в тестах перенаправляют monkeypatch'ем
  соответствующих констант (`paths.OUTPUT_DIR`, `history_store.HISTORY_PATH`,
  `gpt_client._SETTINGS_PATH`, `paths.MODEL_DIR`,
  `rvc_catalog.RVC_MODELS_DIR` + `_constants.RVC_METADATA_DIR`) — репозиторий
  не загрязняется.
- Подменяемые пути в `rvc_catalog` читаются через объект пакета
  (`_pkg.RVC_MODELS_DIR`) — паттерн задокументирован в `downloader.py`;
  исключение `_constants.RVC_METADATA_DIR` патчится отдельно.

---

## 6. UI-слой на PySide6

### 6.1 Точка входа и главное окно

`ui/app.py::run()`:

1. `QApplication` (имя `AI Studio`, org `ai_studio`), PassThrough HiDPI.
2. Язык из `QSettings("ai_studio","studio")["ui/language"]` **до** построения
   виджетов.
3. Тёмная палитра (`theme/palette.py::make_dark_palette`) + `stylesheet.qss`.
4. `MainWindow().show()` → `app.exec()`.

`ui/main_window.py::MainWindow` — композиция:

```
┌──────────────────────────────────────────────────────────────┐
│ Меню: Файл (New/Open/Save *.json, Экспорт, Выход) · Вид (·dock)│
│       Модели (Скачать, Model Hub) · Инструменты · Справка      │
├───────────┬──────────────────────────────┬───────────────────┤
│ Model Hub │  QTabWidget workspaces:      │ Settings /        │
│ + История │  TTS · Чат · Изображения ·   │ Inspector (tab)   │
│  (left)   │  Пайплайн                    │ (right)           │
├───────────┴──────────────────────────────┴───────────────────┤
│ Очередь / Консоль (bottom, tabbed)                            │
├───────────────────────────────────────────────────────────────┤
│ Status: GPU · VRAM · CPU · RAM · Queue                        │
└───────────────────────────────────────────────────────────────┘
```

Состояние (геометрия, `saveState()` доков, язык) сохраняется в QSettings
при `closeEvent` и восстанавливается при старте. Переключение языка —
живое: `retranslate_ui()` пробегает меню, вкладки, доки, все workspace и
панели без пересоздания (этап 07), включая подписи провайдеров в
`gpt_client.refresh_i18n_labels()` и пересборку комбобокса провайдеров.

### 6.2 Workspaces (центральная область)

Общий базовый класс `workspaces/base_workspace.py::BaseWorkspace` собирает
toolbar + `QSplitter`(canvas|sidebar) + `PipelineStrip` из `_pipeline_steps()`.

| Workspace | Сигналы → | Особенности |
|---|---|---|
| **TTS** (`tts_workspace.py`) | `generate_requested(text, params)`, `stop_requested`, `export_requested` | Drop-зона reference-аудио, слайдеры (temp/speed/top_p/rep-penalty, index-rate, pitch), язык auto/ru/en/es/fr/de/zh/ja, формат WAV/MP3/FLAC/OGG, sample-rate, autoplay, RVC-блок. `current_params()/apply_params()` — для проекта. Селектор движка — реальный (`TTSController.available_models`). |
| **Чат** (`chat_workspace.py`) | `send_requested(msg, system, model_id, temperature, max_tokens)`, `stop_requested`, `clear_requested` | Пузыри `ChatBubble`, системный промпт, температура 0–2.00, max_tokens 256–8192, оценка контекста. `set_models()/model_selector()/system_prompt()/load_messages()`. |
| **Изображения** (`image_workspace.py`) | `generate_requested(prompt, params)`, `stop_requested` | Prompt + теги (`TagInput`), steps/cfg/seed (–1 = random), размеры, batch, 4 ячейки результатов (честные placeholders, фальшивых картинок нет). |
| **Пайплайн** (`pipeline_workspace.py`) | `run_requested(text)`, `stop_requested` | 6 нод Input→Normalize→TTS→RVC→De-ess→Output; `set_node_state/reset_nodes`; Run гоняет реальную TTS-цепочку (этап 10). |

### 6.3 Контроллеры (`ui/controllers/`)

**`base_controller.py`** — инфраструктура:

- `WorkerThread(fn, *args, **kwargs)` вызывает `fn(*args, progress_callback, cancel_check, **kwargs)`;
  сигналы `progress(int,str)`, `result(object)`, `error(str)`, `finished_clean()`.
- `BaseController._run_in_background(fn)` — отменяет предыдущий worker,
  эмитит `busy_changed`, маршрутизирует ошибки в `error_occurred`+`log_message`.

| Контроллер | Реальная функция |
|---|---|
| **TTSController** | `on_generate(text, params)`: движки **coqui** (extras `.[ml]`, нужен reference) → **espeak** (системный бинарник) с автоопределением, либо закреплённый выбор `select_backend()` (auto/coqui/espeak, честная ошибка недоступного). Цепочка: normalize → chunk → синтез чанков → склейка WAV (`wave`, паузы 150 мс) → `_make_output_name` → конвертация формата (pydub+ffmpeg) → `save_history` → сигналы + очередь (`attach_queue`). `export_last(target)` — копия/конвертация. `rvc_models()` — скан `MODEL_DIR/**/*.pth`. RVC без бэкенда — гейт `ctl_rvc_missing` **до** генерации. |
| **ChatController** | `on_send(msg, system, model, temperature, max_tokens)` → `gpt_client.chat` в worker'е; история контроллера (`history()/set_history()`) копится ходами и уходит в API; `available_models()` — каталог активного провайдера со статусом ключа; `select_model()` персистит выбор; любой сбой → «⚠ …» в чат + статус, фальшивых ответов нет; гейт `ctl_llm_missing` если ядро не импортируется. |
| **ImageController** | `available_models()` — diffusers+torch (ready/download). `on_generate` — честный гейт `ctl_img_missing` без файлов; diffusers-путь (SD 1.5, steps/cfg/seed/size, callback-прогресс, отмена) реализован для сред с `.[ml]`. |
| **ModelController** | `scan_local_models(MODEL_DIR)` (7 расширений моделей, категория по подкаталогу, пропуск `.preview_cache/.parameter_preview_cache/.metadata`); `delete_model(path)` — реальное удаление **только внутри** `MODEL_DIR` (realpath-защита от traversal); `catalog()` — живой RVC-каталог; `download_entry(entry)` — реальное HTTP-скачивание через `rvc_catalog.downloader` в worker'е (прогресс по байтам, отмена, SHA256). |
| **QueueController** | Реестр задач `QueueTask(id,type,model,status,progress,…)`; `add_task/cancel_task/clear_completed/set_task_progress`; `queue_changed(list)` драйвит панель очереди **и** индикатор Queue статус-бара. |

### 6.4 Панели (docks)

| Панель | Назначение |
|---|---|
| **ModelHubPanel** | Реальный список из `ModelController.models_updated`; фильтр категорий (динамически из данных), поиск по имени; выбор → Inspector; кнопки Скачать (диалог каталога), Удалить (путь файла; GUI спрашивает подтверждение), Обновить. Пусто — честный текст `hub_empty` (некликабельный). |
| **HistoryPanel** | `scan_outputs(OUTPUT_DIR)`: реальные аудиофайлы (wav/mp3/flac/ogg), сортировка по mtime, размер/дата с диска, поиск; выбор → `item_selected(path)` → Inspector (Size/Path). |
| **SettingsPanel** | Язык (EN/RU), тема (dark), устройство (auto/CPU[/CUDA если torch]), потоки/batch, пути models/output; **группа LLM Provider**: провайдер (встроенные+кастомные, подписи i18n), API-ключ (Password echo, очищается после сохранения), состояние ключа (задан ✓/не задан), сигнал `llm_saved(pid)`. Сигналы: `settings_changed(dict)`, `language_changed(code)`, `paths_changed`, `llm_saved`. |
| **InspectorPanel** | Свойства выбранной сущности (история/модель): имя, тип, пары ключ-значение, детали. |
| **QueuePanel** | Таблица живых задач очереди (статус/прогресс), кнопки отмены/очистки завершённых. |

### 6.5 Виджеты (`ui/widgets/`)

- **`waveform_view.py::WaveformView`** — реальная огибающая WAV: `compute_peaks`
  (numpy, min/max по окнам), QPainter-рендер, длительность/время, seek,
  воспроизведение через `QSoundEffect` (кнопка честно отключена, если
  мультимедиа-бэкенда нет).
- **`model_selector.py::ModelSelector`** — пустой конструктор (без демо-стабов!),
  `set_models([{id,name,provider,status,current}])` с иконками ✅📥❌⏳ и
  групповыми разделителями, пересборка **без ложной эмиссии**,
  `current_model_id()`, `select_id()`, сигнал `model_changed(id)`.
- **`status_bar.py::ResourceStatusBar`** — CPU/RAM из psutil раз в 2 с;
  GPU/VRAM только при torch+CUDA (иначе честные «—»); `set_queue_size(n)`
  от очереди; `set_message` для статусов.
- **`pipeline_strip.py::PipelineStrip`** — стрип этапов с состояниями
  idle/active/done/error (`set_step_state`, `set_steps` для retranslate).
- **`log_console.py`** — журнал (уровень/текст, фильтр, очистка).
- **`toast.py`** — всплывающие уведомления (info/success/warning/error).
- **`file_drop_zone.py`** — drop-зона файлов с фильтром расширений и
  `current_path()`; **`collapsible_group.py`** — сворачиваемая группа с
  `set_title` (retranslate); **`tag_input.py`** — редактор тегов;
  **`progress_overlay.py`** — затемнение с прогрессом.

### 6.6 Диалоги (`ui/dialogs/`)

- **`model_download.py::ModelDownloadDialog`** — живой RVC-каталог
  (`ModelController.catalog()`), уже скачанное скрыто, офлайн → честная
  подпись; реальный прогресс-бар на сигналах контроллера.
- **`env_setup_wizard.py::EnvSetupWizard`** — «Проверка окружения»: реальные
  чеки ffmpeg (`-version`), espeak (`espeak_tts.find_espeak()`), импортов
  torch/TTS/diffusers с версиями, CUDA (имя устройства); ✅/❌ отчёт и сводка.
  Ничего не качает и не обещает.
- **`about.py`**, **`error_report.py`** — информация и отправка отчётов.

---

## 7. Потоки данных (сценарии)

### 7.1 Генерация TTS

```
[TTSWorkspace] кнопка «Сгенерировать» → generate_requested(text, params)
  → TTSController.on_generate
    ├─ _ensure_engine (normalizer/chunker) + _ensure_backend (coqui→espeak | pinned)
    ├─ RVC-гейт (params.rvc_enabled → ошибка ctl_rvc_missing, стоп)
    ├─ очередь: add_task("TTS", backend, …)
    └─ WorkerThread(_generate_impl)
         normalize → pipeline_step(0,1) → chunk → per-chunk espeak_tts.synthesize
         → concat WAV (+150 мс) → _make_output_name → [mp3/flac/ogg: pydub+ffmpeg]
         → save_history → result
  → MainWindow._on_tts_done: waveform.set_audio, Export enable, autoplay,
    HistoryPanel.refresh, toast
```

### 7.2 Ход чата

```
[ChatWorkspace] Enter → send_requested(msg, sys, model_id, temp, max_tokens)
  → ChatController.on_send
    ├─ model_id → gpt_client.set_model (persist)
    └─ WorkerThread: gpt_client.chat(msg, history, system, max_tokens, temperature)
         → messages [system, *history, user]
         → _build_provider_chain (active + fallback с ключами)
         → _call_api → POST OpenAI-совместимый JSON
    → result: history += (user, assistant); message_added → пузырь; busy off
    → error: «⚠ AIUnavailable: …» в чат + статус (фабрикации нет)
```

### 7.3 Pipeline Run

`MainWindow._on_pipeline_run(text)` → тот же `TTSController.on_generate`
(параметры из сайдбара TTS, autoplay=off). `pipeline_step_changed`
одновременно драйвит стрип TTS (`_on_tts_step`) и ноды пайплайна
(`_on_pipeline_step`) — подсветка зеркалит реальные этапы.

### 7.4 Скачивание модели

`Hub → download_requested` → `ModelDownloadDialog(ModelController)` → выбор
записи каталога → `download_entry(entry)` → worker →
`rvc_catalog.downloader.download_model` (URL→`models/rvc/`, прогресс байт→%,
SHA256 если задан, zip→pth, отмена) → `download_finished` → обновлённый скан
Hub. Ошибка/404 — `download_failed`, файла нет.

### 7.5 Экспорт аудио

`Export` (toolbar TTS или меню) → `QFileDialog.getSaveFileName` →
`TTSController.export_last(target)`: совпадающий формат — `shutil.copyfile`,
иначе pydub+ffmpeg; пустой результат — RuntimeError. «Нечего экспортировать» —
честное предупреждение.

### 7.6 Проект (New/Open/Save)

`save_project_to(path)` пишет JSON `{version:1, language, tts:{text,params},
chat:{history,system,model}, pipeline:{text}}`; `load_project_from(path)`
валидирует `version`, применяет язык (с retranslate), текст и параметры,
историю чата (контроллер + пузыри), модель (select_id). `_clear_project` —
New. Диалоги добавляют/исправляют расширение `.json`.

---

## 8. Конфигурация и персистентность

| Хранилище | Файл/место | Что |
|---|---|---|
| LLM-настройки | `json/gpt_settings.json` | активный провайдер, `api_key_<pid>` (**защищены** secret_store), `model_<pid>`, custom_providers, hidden_providers, key_library, ui_state. Атомарная запись. |
| UI-настройки | `QSettings("ai_studio","studio")` | язык, геометрия/состояние доков. |
| История генераций | `json/history.json` | записи `save_history` (текст/путь/длительность). |
| Проект | произвольный `*.json` | см. §7.6, `version: 1`. |
| Модели | `models/**` | сканируются Hub'ом и RVC-селектором; `models/rvc/.metadata/*.json` — источники/trust скачанных. |
| Логи | `logs/xtts_studio.log` | loguru. |

---

## 9. Интернационализация (i18n)

- Модуль `ai_studio_core/i18n.py`: `LANGUAGES = {"en": "English", "ru": "Русский"}`,
  `TRANSLATIONS` — 186 ключей на язык, **паритет ключей обязателен**
  (проверяется тестом).
- `t(key, lang=None)` никогда не кидает исключение (отсутствующий ключ →
  сам ключ), `set_language(code) -> bool` валидирует код.
- Все видимые строки UI — через `tr = i18n.t`, включая подписи провайдеров и
  каталога в `gpt_client` (`refresh_i18n_labels()` после смены языка).
- Живое переключение: `MainWindow.retranslate_ui()` → меню/вкладки/доки/
  workspaces/панели обновляют тексты на месте (`set_title`, `set_label`,
  `set_steps`, пересборка комбобокса провайдеров). Исторически краш был из-за
  `settings_changed = None` (этап 07) — сигналы теперь настоящие.
- **Добавить строку UI** = добавить ключ в оба словаря + использовать `tr("key")`.

---

## 10. Бэкенды и провайдеры

### 10.1 TTS-движки

| Движок | Условие | Особенности |
|---|---|---|
| **Coqui XTTS v2** | extras `.[ml]` (torch+TTS) | Клонирование голоса по reference-аудио (обязателен). Устройство auto (cuda→cpu). |
| **espeak-ng** | системный бинарник | `espeak_tts.synthesize` → WAV 22050 Гц mono 16-bit; автоопределение ru/en по кириллице; `wpm_from_speed` (80–450 WPM). Отказ → RuntimeError, пустышек нет. |

Выбор: Auto (coqui→espeak) или закрепление через тулбар-селектор — статусы
✅/📥 по факту окружения.

### 10.2 LLM-провайдеры (`gpt_client`)

- Встроенные: **groq**, **openrouter**, **proxy** (боевой OpenAI-совместимый
  агрегатор, URL в `PROXY_BASE_URL`), **local** (GGUF через `local_llm_client`).
- **Кастомные провайдеры**: `add_custom_provider(pid, label, url, models, fallback, headers, key_hint)` — любой OpenAI-совместимый endpoint. Extra-заголовки не могут переопределить `Authorization` и др. sensitive (см. §11).
- Цепочка fallback: активный провайдер → остальные с ключами → кастомные;
  по каждому — primary, затем fallback-модель. Сетевые сбои всех — «нет
  интернета»; исчерпание — `AIUnavailable`.
- Приложимость определяется наличием ключа (`_provider_available`), каталог
  моделей можно подтянуть с `models_url` (`fetch_models_from_url`).

### 10.3 RVC

Бэкенд конвертации — extras `.[rvc]` (в данной сборке отсутствует → честный
гейт). **Каталог** (`rvc_catalog`) — реальный: seed/кэш/сеть, скачивание
прямых `.pth/.zip`, HuggingFace `/resolve/`, Google Drive (best-effort),
проверка SHA256, защита zip, метаданные и trust.

### 10.4 Изображения

Бэкенд — diffusers (Stable Diffusion, extras `.[ml]`). Недоступен → гейт
`ctl_img_missing`. Пустые ячейки канваса — честный empty-state, не «примеры».

---

## 11. Безопасность

1. **Ключи API**: `secret_store.protect_secret` — Windows DPAPI (`dpapi:v1:`);
   на Linux миграция plaintext→защищённое хранение **fail-closed**
   (`SecretStoreUnavailable` вместо тихого хранения открытым текстом);
   тестовый режим только через `XTTS_TEST_SECRET_STORE=1` (`test-only:v1:`).
2. **URL-валидация** (`gpt_client._validate_api_url`): только HTTPS;
   `http://` — исключительно loopback (localhost/127.0.0.1/::1); запрещены
   учётные данные в URL и фрагменты. Это же правило применяет
   `add_custom_provider` и `fetch_models_from_url`.
3. **Sensitive-заголовки**: extra_headers провайдера не могут подменить
   `Authorization`, `Host`, `Content-Type`, `Content-Length`,
   `Transfer-Encoding`, `Cookie`, `Set-Cookie`, `Proxy-Authorization`
   (регистронезависимо, без падения).
4. **Path traversal**: `ModelController.delete_model` — realpath-проверка
   «внутри MODEL_DIR»; `rvc_catalog` — извлечение zip с проверкой членов,
   `_path_is_inside`, basename-нормализация.
5. **Скачивания**: опциональная проверка SHA256; распознавание HTML-страниц
   ошибок вместо бинарника; `.part`-файлы и подчистка при сбое/отмене.
6. **Обновления**: Ed25519-подписи манифестов (`update_signing`), хеши релизов
   (`release_hashing`), SSL-контекст с certifi.

---

## 12. Тестирование

### 12.1 Запуск

```bash
cd ai_studio_core
QT_QPA_PLATFORM=offscreen python3 -m pytest test/ -q --timeout=300 \
  --ignore=test/test_qc.py --ignore=test/test_task_manager.py --ignore=test/test_tts_utils.py
# → 620 passed (в среде без torch)
```

`test_qc.py`, `test_task_manager.py`, `test_tts_utils.py` требуют torch —
в средах без него исключаются; всего в проекте 42 файла / ~653 теста.

Архитектурный контракт: `lint-imports` (или
`python -m importlinter.cli …`) → `layered_architecture KEPT`.

### 12.2 Паттерны тестов (важно для новых)

- **Qt**: `os.environ.setdefault("QT_QPA_PLATFORM","offscreen")` до импорта
  PySide6; `pytest.importorskip("PySide6")`; общий `QApplication` на модуль;
  ожидание worker'ов — цикл `processEvents()` + `cond()` (helper `_wait`).
- **Сетевые функции — без внешней сети**: настоящий `http.server` на
  `127.0.0.1:0`. gpt_client разрешает `http://` только для loopback — это же
  используется тестами чата; downloader RVC тестируется побайтовой
  отдачей `.pth` тем же сервером.
- **Изоляция побочных эффектов**: monkeypatch путей (см. §5.2) + tmp_path;
  ключи — `XTTS_TEST_SECRET_STORE=1`; QSettings — `XDG_CONFIG_HOME=tmp` +
  `clear()`.
- **Анти-пустышки**: проверяются размер/параметры реальных файлов (WAV
  22050 Гц, >N байт), побайтовое равенство скачанного, отсутствие файлов
  при гейтах, отсутствие текста ключа в файле настроек (не plaintext).

### 12.3 Покрытие по этапам

| Этап | Новые тесты | Фокус |
|---|---|---|
| 07 | 26 | i18n-паритет, переключение языка на живом окне (ping-pong), QSettings |
| 08 | 46 | espeak-бекенд, волна, TTS-flow, история, очередь, экспорт |
| 09 | 28 | чат loopback (payload/history/отказы), настройки провайдера, селекторы, выбор бэкенда |
| 10 | 26 | скан/удаление/скачивание моделей, проект roundtrip, pipeline run, image-гейт, статус-бар |
| 11 | 8 | реальные чеки мастера окружения |

---

## 13. Руководство разработчика

### 13.1 Добавить TTS-движок

1. Модуль в ядре с `available()` / `synthesize(...)`.
2. `TTSController`: `_coqui_available`-подобный предикат, ветка в
   `_resolve_backend`/`_generate_impl`, запись в `available_models()`.
3. Тесты: свободные детекторы статуса + сквозной синтез (skipif по
   `available()`), честный отказ при принудительной недоступности.

### 13.2 Добавить LLM-провайдера

- Разово в рантайме: UI Settings → LLM Provider принимает встроенные и
  кастомные; программно — `gpt_client.add_custom_provider(...)` + ключ.
- Встроенным: запись в `PROVIDERS` (+ ключ подписи в `_PROVIDER_LABEL_KEYS`
  и i18n-словари обоих языков), fallback-модель, `models_url` при наличии.

### 13.3 Добавить ключ i18n

Добавить в оба словаря `TRANSLATIONS` одновременно (паритет проверяется
тестом), затем `tr("key")` в коде. Никакого ручного кэширования — `t()` всегда
свежий.

### 13.4 Написать тест на UI-функцию

Использовать паттерны §12.2; worker-контроллер проверять через сигналы и
`_wait`; без сети к внешним хостам; репозиторий не загрязнять (проверка:
`git status` чист после прогона).

### 13.5 Ритуал коммита этапа

```bash
cd Studio-AI
rm -rf ai_studio_core/outputs ai_studio_core/json/history.json
find . -name "__pycache__" -type d -not -path "./.git/*" -exec rm -rf {} +
git checkout -- ai_studio_core/logs/xtts_studio.log
QT_QPA_PLATFORM=offscreen python3 -m pytest test/ -q --timeout=300 \  # (в ai_studio_core)
  --ignore=test/test_qc.py --ignore=test/test_task_manager.py --ignore=test/test_tts_utils.py
lint-imports                       # KEPT
git add <изменённые файлы + AUDIT_NN.md + скрины>
git -c user.email=... -c user.name=... commit -m "Stage NN — …"
git show HEAD > STAGE_NN_name.diff # STAGE_*.diff исключены из git'а (.git/info/exclude)
```

Аудит (`AUDIT_NN_*.md`) — русскоязычный: таблица «было→стало», новые тесты,
осознанные границы окружения.

---

## 14. Известные ограничения

1. **torch-зависимое** (XTTS v2, RVC-инференс, diffusers, 3 файла тестов)
   требует extras `.[ml]`/`.[rvc]`; в средах без них функции честно
   недоступны (гейты/статусы 📥), а не имитируются.
2. **Клонирование голоса** — только движок Coqui + reference-аудио; espeak
   reference игнорирует (честный WARN в лог).
3. **DPAPI-хранилище** на Linux-проде: сохранение ключа завершится явной
   `SecretStoreUnavailable` (by design ядра, fail-closed). Обход — Windows
   или доработка keystore-бэкенда.
4. **Стриминг ответов LLM** не реализован — провайдеры отдают ответ целиком;
   шаг «Стриминг» пайплайна отражает ожидание ответа.
5. **boевые провайдеры/Cаталог в сети** в тестах не дёргаются (офлайн):
   покрыто идентичными код-путями на loopback-сервере.
6. **Просодия/de-esser и др. ядра** есть в коре, но не подключены к
   UI-цепочке (этапы подключения следуют тем же паттернам контроллеров).

---

## 15. История этапов 06–11

| Коммит | Этап | Содержание |
|---|---|---|
| `073bcc6` | 06 | Запускаемость UI; workspaces по blueprint; скрины |
| `0d686f4` | 07 | Краш переключения языка; i18n EN/RU; живой retranslate; persist |
| `33baea6` | 08 | Реальный TTS (espeak), волна, история, очередь, экспорт |
| `4dc542b` | 09 | Реальный чат (провайдеры/ключи/история), настоящие селекторы, выбор бэкенда |
| `a5afe33` | 10 | Model Hub (скан/удаление/скачивание), проекты, Pipeline Run, статус-бар, image-гейт |
| `d2c0963` | 11 | Мастер окружения → реальные проверки |

Аудиты: `AUDIT_06_ui_fixes.md` … `AUDIT_11_env_wizard.md`; диффы:
`STAGE_06_*.diff` … `STAGE_11_*.diff` (рядом, вне `ai_studio_core/`).

---

## 16. Приложение: справка по ключевым API

### 16.1 `ai_studio_core.gpt_client`

```python
chat(prompt, history=None, system=None, max_tokens=2048, temperature=0.7) -> str
improve_for_tts(text) -> str            # мягкий фолбэк к исходному тексту
preprocess_for_tts(text, mode="assistant")
validate_key(key, provider=None) -> (bool, str)

get_provider() / set_provider(pid)
get_api_key(pid=None) / set_api_key(key, pid=None)
get_model(pid=None) / set_model(m, pid=None) / get_fallback_model(pid=None)
get_provider_info(pid=None) -> dict
list_custom_providers() / add_custom_provider(...) / delete_custom_provider(pid)
hide_provider(pid) / show_provider(pid)
list_keys(pid=None) / add_key(label, key, pid=None) / update_key / delete_key / apply_key_from_library(id)
fetch_models_from_url(models_url, api_key="") -> list[str]
get_chain_diagnostics() -> dict          # состояние цепочки для UI «AI статус»
refresh_i18n_labels()

Исключения: AIUnavailable, GroqRateLimitError, GroqNetworkError.
```

### 16.2 `ai_studio_core.espeak_tts`

```python
find_espeak() -> str | None
available() -> bool
synthesize(text, out_path=None, language="auto", speed=1.0) -> SynthesisResult
    # SynthesisResult: path, duration_sec, sample_rate (22050), frames
resolve_voice(text, language) -> str     # авто ru/en по кириллице
wpm_from_speed(speed) -> int             # 80–450 WPM
wav_info(path) -> (frames, rate, duration)
```

### 16.3 Контроллеры (сигналы BaseController: `busy_changed`, `status_message`, `error_occurred`, `log_message`)

```python
TTSController:
    signals: generation_started, generation_progress(int,str),
             generation_complete(str), pipeline_step_changed(int,str),
             backend_changed(str)
    attach_queue(qc); on_generate(text, params); on_stop()
    export_last(target) -> str; last_output() -> str | None
    available_models(); select_backend("auto"|"coqui"|"espeak")
    rvc_models() -> list[dict]; backend(); preferred_backend()

ChatController:
    signals: message_received(str), message_added(role, content),
             generation_started/finished
    on_send(msg, system_prompt="", model="", temperature=0.7, max_tokens=2048)
    on_stop(); on_clear(); history(); set_history(list)
    available_models(); select_model(model_id)

ImageController:
    signals: image_ready(str), generation_progress(int,str)
    on_generate(prompt, params); on_stop(); available_models(); last_image()

ModelController:
    signals: models_updated(list), download_started(name),
             download_progress(name, pct), download_finished(name),
             download_failed(name, reason)
    refresh(); list_models(); delete_model(path) -> bool
    catalog() -> list[dict]; is_downloaded(entry) -> bool
    download_entry(entry); cancel_download()
    # модульная функция: scan_local_models(model_dir) -> list[dict]

QueueController:
    signals: queue_changed(list), task_added/updated/removed(id)
    add_task(type_, model, params=None) -> id
    cancel_task(id); clear_completed(); set_task_progress(id, pct, status)
    tasks(); running_count(); queued_count()
```

### 16.4 Ключевые виджеты/панели

```python
ModelSelector: set_models(list[dict]); current_model_id() -> str;
    select_id(id) -> bool; signal model_changed(id)
WaveformView: set_audio(path)
ResourceStatusBar: set_message(str); set_queue_size(int); update_stats(...)
PipelineStrip: set_steps(list[str]); set_step_state(idx, state)
ModelHubPanel: set_models(list); selected_model(); signals download_requested,
    delete_requested(path), refresh_requested, selection_changed(dict)
SettingsPanel: signals settings_changed(dict), language_changed(code),
    paths_changed(kind, path), llm_saved(pid); set_language(code); selected_provider()
MainWindow: save_project_to(path); load_project_from(path); retranslate_ui()
```

### 16.5 Схема params генерации TTS

```python
{
    "language": "auto" | "ru" | "en" | "es" | "fr" | "de" | "zh" | "ja",
    "temperature": float,        # 0.0–1.0 (слайдер 0–100)
    "speed": float,              # 0.5–2.0
    "top_p": float, "repetition_penalty": float,
    "rvc_enabled": bool, "rvc_model": str (путь .pth),
    "rvc_index_rate": float, "rvc_pitch": int (-12..12),
    "output_format": "wav"|"mp3"|"flac"|"ogg",
    "sample_rate": int, "autoplay": bool,
    "reference_audio": str,      # путь, только для coqui
}
```

### 16.6 Схема файла проекта (version 1)

```json
{
  "version": 1,
  "language": "ru",
  "tts":  {"text": "…", "params": { …см. 16.5… }},
  "chat": {"history": [{"role": "user"|"assistant", "content": "…"}],
           "system": "…", "model": "model-id"},
  "pipeline": {"text": "…"}
}
```

---

## 17. Experience layer (этап 12)

**`ui/experience/`** — событийный слой микро-обратной связи и статистики.
Отделён от ядра: подписывается на сигналы контроллеров и колбэки окна,
не нарушая контракт слоёв. Правило безопасности: transient-эффекты
(toast/звук/пульс) — без спроса; персистентные изменения — только через
явные тумблеры в Settings.

- **Уровень 1 (события → пресеты).** `events.py` — реестр имён событий
  (валидируется при загрузке пресета). `theme/presets/experience.default.json`
  — mapping событие → `{toast, sound, accent_pulse}`; toast-тексты через
  i18n-ключи или литералы с `{payload}`-плейсхолдерами. `sounds.py` —
  **реальные** тона: numpy-синтез (огибающая attack/release) в WAV
  22050 Гц, кэш в `CACHE_DIR/experience/`; воспроизведение через
  `QSoundEffect` (guarded — без аудио-устройства тихо). `manager.py` —
  `ExperienceManager.handle(event, payload)` + `AccentPulse` (полоса 5 px
  с анимацией затухания, самоудаляется).
- **Уровень 2 (статистика → эвристики).** `stats.py::UsageStats` —
  атомарный `json/usage_stats.json`: сессии, активации вкладок, действия,
  использование бэкендов, активные секунды. Эвристика
  `suggested_start_workspace` — детерминированная: максимум активаций при
  ≥3 событиях, ничья → дефолт; причина решения возвращается и пишется в лог.
  Отключение — Settings → «Адаптивная стартовая вкладка» (QSettings
  `ui/adaptive_start_tab`); звуки — `ui/exp_sounds`.
- События-проводка в `MainWindow`: generation complete/failed, queue
  drained (had_running→0), project saved/loaded/new, download finished,
  export done, chat reply, app started; активации вкладок и длительность
  сессии записываются (программный выбор вкладки эвристикой не засчитывается).
- Тесты (`test_experience_layer.py`, 22): реальные WAV (частота/формат/
  анти-тишина), кэш, валидация и merge пресетов, исполнение действий
  менеджера, отключение звука, авто-скрытие пульса, roundtrip статистики,
  эвристика (threshold/winner/tie), интеграция с MainWindow (адаптивная
  вкладка, тумблеры, запись активаций, queue_drained один раз).

*Документация отражает код на 2026-07-19 (этапы 06–12). При изменении
поведения обновляйте соответствующие разделы и аудит этапа.*
