# AUDIT 14 — Windows fatal exception: access violation при запуске GUI

Дата: 2026-07-19. Машина пользователя: Windows, Python 3.14.6 (обычная сборка,
без free-threading), PySide6 6.11.1. Версия кода: `main` @ `273836c`.

## Симптом

`python -u run_gui.py` →

```
Windows fatal exception: access violation

Thread 0x1a8c [diag-refresh]:
  os.makedirs → logging_utils.write_log:36 →
  env_core.diagnostics.run_full_diagnostics:552 →
  ui.diag_bridge._worker:134

Current thread 0x1d90 (GUI):
  ui.app.run:40 → app.exec()
```

GUI-поток падает в нативном коде Qt внутри `app.exec()` через доли секунды
после старта; фоновой поток `[diag-refresh]` в это время пишет лог-строку
«[Diagnostics] Запуск полного сканирования библиотек в изолированном
процессе...».

## Причина №1 (основная): import torch внутри GUI-процесса

Краcиво оформленный в `diag_bridge._worker()` хвост:

```python
if results.get("torch") is True:
    cuda_ok, cuda_name = _probe_cuda_in_torch()   # ← import torch ЗДЕСЬ
```

`_probe_cuda_in_torch()` делал `import torch` и `torch.cuda.is_available()`
**в процессе GUI** (в фоновом потоке). Но именно на этой машине «битый
torch убивал GUI-процесс ещё до window.show()» (само это зафиксировано в
докстринге файла). Сама диагностика уже давно изолирована в сабпроцесс
(`run_full_diagnostics` гоняет probe-скрипт через `python -c`), а мост
тихо возвращал нативный импорт обратно в процесс.

Ключевой факт: **access violation, сегфолт и т.п. при импорте/инициализации
DLL убивают процесс целиком — независимо от того, в каком потоке сделан
`import`.** «Перенести импорт в фоновый поток» нельзя — можно только
перенести его в другой процесс. Именно это замечается в дампе: падающий
(current) — GUI-поток, хотя инициатор — фоновой.

## Причина №2 (попутный баг): сигналы диагностики никогда не эмитились

В `_worker()` определялась функция `_apply()` (которая эмитит
`cuda_info_changed` / `diagnostics_updated`), но на happy-path она
**не вызывалась** — вызывался слот `_apply_in_gui`, который только
перечитывал кэш и ничего не эмитил. Итог: статус-бар, селекторы моделей и
комбобокс устройства после фоновой диагностики никогда не обновлялись.
На fallback-path `_apply()` могла эмитить прямо из рабочего потока —
второй потенциальный источник access violation в Qt.

## Причина №3 (потерянный merge): experience-слой Stage 12 частично исчез

В коммитах `6c3c530 → 273836c` файлы `main_window.py`/`settings_panel.py`
были откачены к состоянию Stage 11: при том что пакет `ui/experience/` и
все тесты `test_experience_layer.py` в репозитории есть, **вся интеграция
из MainWindow/SettingsPanel (`_setup_experience`, адаптивная стартовая
вкладка, exp-тумблеры, реальные события контроллеров) отсутствовала**.
Именно поэтому падали 4 интеграционных теста experience-слоя.

## Исправление (коммит `7fadf74`, патч `STAGE_15_cuda_isolation_crash.patch`)

**`env_core/diagnostics.py`**
* probe-скрипт сабпроцесса теперь сам опрашивает `torch.cuda.is_available()`
  и `torch.cuda.get_device_name(0)` и печатает маркер `CUDA_RESULT={...}`;
  GUI-процесс torch не импортирует вообще — ни на старте, ни в потоках.
* Родитель парсит оба маркера. `available` признаётся только при живом
  `torch` в том же прогоне (защита от «ложного» флага).
* CUDA раскладывается в отдельный блок `cache["cuda"]` (не в
  `cache["results"]`, чтобы не ломать критерий «все 12 компонентов == True»);
  `run_full_diagnostics()` и `load_diagnostics_cache()` отдают вызывающим
  поля `cuda_available` / `cuda_name`.

**`ui/diag_bridge.py`** (переписан)
* Удалён `_probe_cuda_in_torch`. В GUI-процессе нет ни одного
  `import torch/TTS/torchvision/torchaudio` — правило зафиксировано в
  докстринге и проверяется тестами (включая перехват `builtins.__import__`
  на время фонового рефреша).
* Сигналы испускаются строго из GUI-потока через queued-слот
  `_apply_in_gui` — ровно один раз на одну проверку.
* Защита от параллельных проверок: повторный `kickoff_refresh(force=True)`
  во время работающей проверки игнорируется (не плодим сабпроцессы,
  пишущие один cache-файл).

**`ui/main_window.py` / `ui/panels/settings_panel.py`**
* Возвращена вся integration-часть Stage 12 поверх их диаг-интеграции
  (тасты, конфликтов с diag_bridge нет — `_on_diagnostics_updated` и
  `refresh_device_options()` сохранены).

**Тесты** (`test_diag_bridge.py` — 8, `test_diagnostics_cuda.py` — 6):
эмиссия сигналов (happy/error/force/concurrent), запрет нативных ML-импортов,
разбор `CUDA_RESULT` (живой/битый torch, старый кэш без CUDA-блока),
реальный прогон сабпроцесса-пробы.

## Верификация

```
pytest test/ (без 3 torch-файлов из списка ignore) ... 656 passed
lint-imports ......................................... layered_architecture KEPT
QT_QPA_PLATFORM=offscreen python run_gui.py .......... 25 c в event loop,
                                                       краша/Traceback нет;
                       в логе виден запуск сабпроцесса диагностики
git apply --check патча на чистом main@273836c ....... OK
```

До фикса на этом же коде (без моих правок) было: `4 failed, 638 passed`
(упавшие — 4 интеграционных теста experience-слоя, причина №3).

## Как применить

```bash
git clone https://github.com/DreamSketcher/Studio-AI && cd Studio-AI
git am /путь/к/STAGE_15_cuda_isolation_crash.patch
git push
```

Готовый репозиторий с применённым фиксом и полной историей —
это этот проект (`Studio-AI/` в workspace): remote `main` + 5 коммитов
(фикс, разминусовка мусора, этот документ).

## Остаточные замечания (не блокеры)

1. **Если краш сохранится после патча** — значит второй фактор в
   окружении Qt/DLL. Прогоните изоляцию и пришлите вывод:
   `python -c "import sys; from PySide6.QtWidgets import QApplication, QLabel; a=QApplication(sys.argv); QLabel('ok').show(); sys.exit(a.exec())"`
   (окно на пару секунд, затем закрыть). Если падает даже оно — дело не в
   нашем коде (драйверы GPU/оверлеи/антивирус/битый шрифт).
2. В репозитории `.gitignore` обновлён (лизал CI_FIX_02), но **сами файлы
   так и трекаются**: `__pycache__/*.pyc` (47 шт.), `json/usage_stats.json`,
   `logs/xtts_studio.log`. Убрать из индекса (с диска не удалится):
   ```powershell
   git rm -r --cached --ignore-unmatch (git ls-files | Select-String '__pycache__|\.pyc$|usage_stats|xtts_studio' | % { $_.Line })
   git commit -m "Untrack runtime/junk files"; git push
   ```
3. `fix_diag`-патч сознательно не трогает `QSettings`-путь и логирование —
   отдельным этапом можно вести crash-дамп faulthandler в `logs/crash_dump.txt`.
