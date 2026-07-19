# AUDIT 17 — найден виновник: висячий указатель на Qt message handler

Дата: 2026-07-19. Предыстория: AUDIT_15 (CUDA-изоляция), AUDIT_16 (kit
расследования: faulthandler→crash_dump.txt, Qt-логгер, выключатели).

## Доказательная цепочка

1. Пользовательский `crash_dump.txt` (запуск на коде STAGE_16, 13:42):

   ```
   Thread [diag-refresh] (most recent call first):
     File "<frozen os>", line ??? in __iter__
     <invalid frame>          ← порча памяти, а не «обычное падение»
   Current thread (GUI):
     app.py:75 in run  (= app.exec())
   ```

2. `<invalid frame>` у соседнего потока = faulthandler не смог пройти по
   кадру — типичный след **порчи кучи нативным кодом**, не Python-ошибкой.

3. Разбор STAGE_16 показал ошибку инициализации логгера Qt:

   ```python
   def _install_qt_log_handler():
       def _handler(mode, _ctx, msg): ...
       qInstallMessageHandler(_handler)   # локальная переменная!
   ```

   `qInstallMessageHandler` хранит копируемый указатель на C++-обёртку;
   **Python-callable живёт лишь пока жива ссылка**. Замыкание `_handler`
   теряет последнюю ссылку при выходе из функции, CPython немедленно его
   уничтожает. Первое же сообщение Qt (шрифтовые DirectWrite-warn'и,
   плагины платформы — они приходят почти сразу после входа в exec)
   вызывает **освобождённый объект → access violation + порча кадров**
   в произвольном потоке. Это согласуется со всеми дампами: GUI в
   `app.exec()`, соседний поток — безвинный свидетель.

4. Тайминг: краш стабильно в первые доли секунды exec — как раз момент
   первых Qt-сообщений.

## Фикс (коммит `0341792`, патч `diffs/STAGE_17_qt_handler_refcount.patch`)

```python
_QT_MSG_HANDLER = None          # модульный уровень — ссылка живёт вечно

def _install_qt_log_handler() -> None:
    global _QT_MSG_HANDLER
    ...
    _QT_MSG_HANDLER = _handler   # ← ключевая строка
    qInstallMessageHandler(_handler)
```

Регрессионные тесты (`test_qt_msg_handler.py`):

* `test_handler_survives_gc_and_logs_qt_warning` — повторяет условие
  краша: install → `gc.collect()` → `qWarning(...)` → проверяем, что
  запись пришла в лог и handler жив;
* `test_handler_reference_is_global` — структурная защита от повторения.

Полный набор тестов: **663 passed** (2 новых).

## Как обновиться

На машине с pull-доступом достаточно:

```powershell
git pull   # STAGE_16/17 уже в main после пуша либо:
# git am STAGE_17_qt_handler_refcount.patch (лежит в Studio-AI/diffs/)
```

После pull: `Select-String -Path ai_studio_core\ui\app.py -Pattern "_QT_MSG_HANDLER = _handler"` —
должна найтись строка. Затем обычный запуск `python -u run_gui.py`.
Если окно проживёт >10 c — вопрос закрыт; в этом случае `crash_dump.txt`
и `run_log_*.txt` из индекса стоит убрать (их уже покрывает
`.gitignore` правилом `logs/*.log` — они попали в репо раньше, поэтому
`git rm --cached logs/crash_dump.txt run_log_20260719_132131.txt`).

## Честная оговорка

Этот баг объясняет падение **на коде STAGE_16** (логгер появился только
там). Первые два падения — на версиях без логгера — могут иметь тот же
или иной источник; у них совпадающий профиль (нативный краш в exec на
старте), что согласуется с одной причиной «сообщение Qt → битый
callable», но уверенность даст только факт: если после STAGE_17 GUI
живёт — гипотеза подтверждена. Если падение повторится, матрица
выключателей из AUDIT_16 остаётся следующим шагом (первым — NO_XP:
звук на событии старта; вторым — NO_QSS), плюс Faulting module из
Event Viewer.

## Вывод для команды разработки

Любой callable, отдаваемый в C/Qt через callback-API (message handlers,
native hooks), должен иметь **владельца уровня модуля/синглтона**;
локальные замыкания туда не передаём. Добавлен тест-страж на этот
конкретный паттерн.
