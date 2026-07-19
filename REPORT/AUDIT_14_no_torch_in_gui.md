# AUDIT_14 — Убран прямой `import torch` из GUI-процесса

**Дата:** 2026-07-19
**Статус:** ✅ Выполнено
**Связанное ТЗ:** `TS/AUDIT_14_no_torch_in_gui_TZ.txt`
**Diff:** `diffs/STAGE_14_no_torch_in_gui.diff`

## Проблема

GUI-процесс (`ai_studio_core/ui/*`) делал синхронный `import torch` на пути старта
окна (`MainWindow.__init__ → _setup_workspaces → ... → available_models() →
_coqui_available()`). При битом/отсутствующем torch (illegal instruction, битые
CUDA-DLL и т.п.) процесс умирал молча, без исключения и без логов, ещё до
`window.show()`.

В проекте уже есть безопасный механизм — `env_core.diagnostics.run_full_diagnostics()`,
который проверяет torch/TTS/rvc_python в изолированном сабпроцессе с таймаутом и
кэширует результат, но GUI-слой его не использовал.

## Что было сделано

### 1. Ре-классификация компонентов в `env_core/diagnostics.py`

- `CRITICAL_COMPONENTS` теперь содержит только то, без чего GUI не может
  стартовать как таковой: `numpy, soundfile, pygame, num2words, cryptography`.
- Добавлено множество `ML_COMPONENTS = {torch, torchaudio, torchvision, tts}` —
  это ML-фичи, а не условие запуска окна.
- `customtkinter` (наследие tkinter-версии) перенесён в `OPTIONAL_COMPONENTS`.
- Добавлены функции:
  - `load_diagnostics_cache()` — безопасное чтение JSON-кэша (не импортирует
    torch, не запускает подпроцессов, не падает на битом кэше).
  - `_component_ok(results, name)` — вспомогательный предикат.

### 2. Новый модуль `ai_studio_core/ui/diag_bridge.py`

Центральный мост между GUI и диагностикой. Предоставляет:

- **Безопасные предикаты без импорта torch:**
  - `torch_available()`, `tts_available()` (alias `coqui_available()`),
    `diffusers_available()` — все читают кэш диагностики.
- **`DiagnosticsBridge` (QObject-singleton):**
  - `cached_results()` / `component_ok(name)` / `cuda_available()` / `cuda_device_name()`.
  - `kickoff_refresh(force=False)` — один фоновый запуск `run_full_diagnostics()`
    в daemon-потоке (без блокировки UI). По окончании в UI-потоке (через
    `QMetaObject.invokeMethod(..., QueuedConnection)`) испускаются сигналы
    `diagnostics_updated()` и `cuda_info_changed(available, name)`.
  - После подтверждения работоспособности torch в кэше — ленивый замер CUDA
    (torch импортируется только в этот момент, в фоне).

### 3. Замена `import torch` в 5 файлах GUI

| Файл | Было | Стало |
|------|------|-------|
| `ui/controllers/tts_controller.py::_coqui_available()` (строка ~28) | `import torch; import TTS` | вызов `coqui_available()` из `diag_bridge` (чтение кэша) |
| `ui/controllers/image_controller.py::_diffusers_available()` (строки ~20, ~68) | `import torch; import diffusers` | `diffusers_available()` из `diag_bridge` (кэш + лёгкий `import diffusers` только если кэш подтвердил torch) |
| `ui/panels/settings_panel.py::_cuda_available()` (строка ~24) | `import torch; torch.cuda.is_available()` | `get_bridge().cuda_available()`. Добавлены `_rebuild_device_combo()` и публичный слот `refresh_device_options()`, чтобы опция CUDA появлялась в комбобоксе после прихода диагностики. |
| `ui/dialogs/env_setup_wizard.py::_check_cuda()` (строка ~55) | `import torch` в GUI-процессе | `get_bridge().component_ok("torch")` + `bridge.cuda_available()`. Добавлен `_check_module_from_cache()`, который для torch/TTS/diffusers идёт через кэш, а не через прямой __import__. |
| `ui/widgets/status_bar.py` (строка ~98) | `import torch` в теле `_poll_resources` на каждом тике таймера | Ленивый `_ensure_torch()`, который пытается импортировать torch ТОЛЬКО если: (1) кэш сказал что torch ОК, (2) окно уже показано (таймер 2 с), (3) флаг `_torch_load_failed` не поднят. Неудача запоминается навсегда (до перезапуска процесса), индикаторы просто остаются на «—». Есть подписка на `diagnostics_updated/cuda_info_changed`. |

Строка ~328 в `tts_controller.py` (`import torch` в `_synthesize_coqui`) и строка
~68 в `image_controller.py` (`import torch` в `_generate_diffusers`) **оставлены
как есть** — они вызываются исключительно внутри `WorkerThread` (через
`_run_in_background`), т.е. не на стартовом пути окна.

### 4. Подключение в `MainWindow`

- Импортируется `get_bridge`.
- После построения UI виджетов на `diagnostics_updated` подписывается слот
  `_on_diagnostics_updated()`, который перезаполняет селекторы TTS/Image
  бэкендов и опцию CUDA в настройках.
- `QTimer.singleShot(0, ...)` запускает `bridge.kickoff_refresh()` уже ПОСЛЕ
  того как окно показано и успело отрисоваться — никаких подпроцессов в
  `__init__`.

### 5. Обновлён тест `test/test_diagnostics.py::TestBrokenCritical::test_broken`

Приведён в соответствие с новой классификацией: `torch/tts/torchaudio/torchvision`
не должны входить в список сломанных критичных компонентов (не должны триггерить
"аварийное восстановление").

## Критерий приёмки — проверка

### ✅ `grep -rn "import torch" ai_studio_core/ui/`

Все оставшиеся вхождения:

```
ai_studio_core/ui/controllers/tts_controller.py:332     # _synthesize_coqui → WorkerThread
ai_studio_core/ui/controllers/image_controller.py:70    # _generate_diffusers → WorkerThread
ai_studio_core/ui/widgets/status_bar.py:143             # _ensure_torch → ленивый, guarded, on-timer
ai_studio_core/ui/diag_bridge.py:81                     # _probe_cuda_in_torch → daemon thread (после подтверждения)
```

Остальные строки — комментарии/докстринги. НИ ОДНОГО `import torch` на
синхронном пути инициализации окна нет.

### ✅ GUI стартует без импорта torch

Проверка (QT_QPA_PLATFORM=offscreen, в окружении БЕЗ torch):

```
Before UI imports: torch in sys.modules? False
After controller imports: torch in sys.modules? False
After TTS/Image init: torch in sys.modules? False
After MainWindow() init: torch in sys.modules? False
After processEvents: torch in sys.modules? False
SUCCESS: MainWindow started without importing torch in GUI process.
```

Coqui и diffusers честно показываются как недоступные (`status: "download"`),
в фоне запускается диагностика, которая по завершении обновит селекторы сигналом.

### ✅ Тесты зелёные

```
test_diagnostics.py .............                                   14 passed
test_ui_language_switch.py ............                             12 passed
test_env_wizard_real.py ........                                     8 passed
test_ai_conductor.py .......................                        23 passed
test_chunker.py .................                                    17 passed
test_i18n_core.py ..............                                     14 passed
test_cpu_gpu.py .........                                             9 passed
------------------------------------------------------------------------
Итого: 97 passed (1 pre-existing failure в test_experience_layer.py воспроизводится
на чистом main до моих правок, к этой задаче не относится).
```

## Поведение в пограничных случаях

1. **torch не установлен** — GUI стартует, Coqui в селекторе = "download",
   CUDA в настройках не показана, TTS работает через espeak, в статус‑баре
   GPU/VRAM = "—".
2. **torch установлен, но нативно битый (illegal instruction / битые DLL)** —
   изолированный сабпроцесс `run_full_diagnostics()` падает (в худшем случае
   по таймауту 90 с), кэш пишет `torch: <ошибка>`, GUI не трогает import
   torch в принципе → окно открывается, см. п.1.
3. **torch рабочий, но CUDA нет** — диагностика фиксирует `torch: True`,
   CUDA-опция в настройках не появляется, GPU-индикаторы "—".
4. **torch + CUDA рабочие** — после фоновой проверки в комбобокс устройства
   добавляется CUDA, статус‑бар начинает каждые 2 с показывать GPU%/VRAM.
5. **Пользователь открывает Env Setup Wizard** — проверки torch/TTS/CUDA
   идут через кэш (без импорта в GUI), показывая честный статус.
6. **Повторный запуск** — кэш валиден (сверяется с msite+count site‑packages),
   диагностика не перезапускается, GUI показывает актуальный статус сразу,
   без задержки.

## Изменённые файлы

```
modified:   ai_studio_core/env_core/__init__.py                     (+экспорт)
modified:   ai_studio_core/env_core/diagnostics.py                  (+load_diagnostics_cache, реклассификация)
new file:   ai_studio_core/ui/diag_bridge.py                        (модуль-мост)
modified:   ai_studio_core/ui/controllers/tts_controller.py         (_coqui_available через кэш)
modified:   ai_studio_core/ui/controllers/image_controller.py       (_diffusers_available через кэш)
modified:   ai_studio_core/ui/panels/settings_panel.py              (_cuda_available через bridge, rebuild combo)
modified:   ai_studio_core/ui/dialogs/env_setup_wizard.py           (_check_cuda/_check_module_from_cache через bridge)
modified:   ai_studio_core/ui/widgets/status_bar.py                 (ленивый импорт, guarded)
modified:   ai_studio_core/ui/main_window.py                        (kickoff + refresh slot)
modified:   test/test_diagnostics.py                                (адаптация теста)
```
