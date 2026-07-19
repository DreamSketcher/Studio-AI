# AUDIT 16 — access violation при старте: продолжение расследования

Дата: 2026-07-19. Предыстория: `AUDIT_14_no_torch_in_gui` (создание моста),
`AUDIT_15_access_violation` (CUDA-проба вынесена в сабпроцесс, сигналы
починены — коммит `7fadf74`).

## Что изменилось после STAGE_15

Краш **повторился на пропатченном коде** (второй дамп). Сопоставление номеров
строк дампа с новыми файлами подтверждает, что запускался именно фикс:
`diag_bridge.py:133` = вызов `run_full_diagnostics`, `diagnostics.py:560` =
`write_log` перед стартом probe-сабпроцесса, `logging_utils.py:38`.

## Пересмотр гипотезы

Оба дампа (до и после STAGE_15) показывают **одну и ту же картину**:

* падающий (current) поток — GUI, стек заканчивается на `app.exec()`,
  т.е. fault в нативном коде Qt внутри цикла событий;
* единственный другой Python-поток — `[diag-refresh]`, и оба раза он
  застигнут на записи строки «Запуск полного сканирования…» — то есть
  **ещё до старта probe-сабпроцесса**. Ни в одном из дампов импорта torch
  в GUI-процессе не было (после STAGE_15 его и быть не может).

Вывод: диаг-поток, скорее всего, **невиновен** — просто он всегда на том же
месте, когда GUI-поток гибнет. Гипотеза STAGE_15 (in-process import torch)
не подтверждена как триггер: краш воспроизводится без него.

Текущий список подозреваемых (по убыванию вероятности, все — в первые
сотни миллисекунд event loop, Windows-специфика):

1. **QSoundEffect / Qt Multimedia** — первый `play()` (приветственный тон
   в 300 мс после старта) инициализирует WASAPI; на битом/отсутствующем
   аудиоустройстве это исторически даёт AV в Qt 6 на Windows.
2. **Stylesheet/палитра** на первом paint (шрифты DirectWrite/GDI).
3. **psutil-таймер** статус-бара (native-вызовы раз в 2 с).
4. **Платформа/окружение Qt**: `qwindows.dll` + оверлеи (Discord, RTSS,
   GeForce Experience), антивирусные инжекты, драйвер GPU/ANGLE, битый шрифт.
5. Фоновой diag-поток (теперь — формально; проверяется выключателем №1).

## Что сделано в STAGE_16 (коммит `c758c5d`, патч `diffs/STAGE_16_…patch`)

Инструментарий расследования — всё реальное, никаких заглушек:

* **faulthandler → `logs/crash_dump.txt`** (run_gui.py): каждый крепкий
  fault теперь остаётся в файле с меткой запуска.
* **Qt-warnings → `logs/xtts_studio.log`** (ui/app.py): DirectWrite/WASAPI/
  plugin-предупреждения, предшествующие падению, попадают в лог.
* **Бут-маркеры** в лог: создание QApplication, палитра/QSS, построение
  MainWindow, вход в exec, выход из exec — видно, на каком шаге обрыв.
* **Выключатели окружения** (main_window/app/status_bar):
  `AI_STUDIO_NO_DIAG`, `AI_STUDIO_NO_XP`, `AI_STUDIO_NO_QSS`, `AI_STUDIO_NO_PS`.
  При `NO_XP` слой полностью обходится: ни QSoundEffect, ни usage_stats.json.
* **Тесты**: `test_startup_switches.py` — 5 шт.; полный набор: 661 passed.

## Runbook (PowerShell, в порядке информативности)

После каждого запуска: если окно прожило >10 секунд без падения — строчка
«OK», иначе «CRASH». Между запусками переменные сбрасывать (`Remove-Item Env:…`).

```powershell
cd 'C:\Users\User\Desktop\Ai Studio'

# 1) Без диаг-потока
$env:AI_STUDIO_NO_DIAG="1"; python -u run_gui.py; Remove-Item Env:AI_STUDIO_NO_DIAG

# 2) Без experience-слоя (звуки QSoundEffect, пульсы)
$env:AI_STUDIO_NO_XP="1"; python -u run_gui.py; Remove-Item Env:AI_STUDIO_NO_XP

# 3) Без stylesheet и тёмной палитры
$env:AI_STUDIO_NO_QSS="1"; python -u run_gui.py; Remove-Item Env:AI_STUDIO_NO_QSS

# 4) Программный растеризатор (без D3D/OpenGL от драйвера GPU)
$env:QT_OPENGL="software"; python -u run_gui.py; Remove-Item Env:QT_OPENGL

# 5) Без psutil-опроса
$env:AI_STUDIO_NO_PS="1"; python -u run_gui.py; Remove-Item Env:AI_STUDIO_NO_PS

# 6) Контроль платформы: окно Qt «из коробки», без нашего кода — закройте
#    его через 10 секунд. Если упадёт и ОНО — проблема вне проекта.
python -c "import sys; from PySide6.QtWidgets import QApplication, QLabel; a=QApplication(sys.argv); w=QLabel('qt-min-ok'); w.resize(300,120); w.show(); sys.exit(a.exec())"
```

Матрица результатов позволит назвать отказавший компонент одним файлом-
коммитом (например, «CRASH везде кроме №2» → Qt Multimedia: заменим
QSoundEffect на ленивое создание + полное отключение при флаге оффлайн/
хедлесс-режиме, либо отложенную первую инициализацию после 2 с).

## Что прислать

1. Табличку OK/CRASH по 6 запускам.
2. `logs\crash_dump.txt` (последний блок после «===== запуск … =====»).
3. Хвост `logs\xtts_studio.log` (особенно строки `[QT-WARN] [QT-CRIT]`).
4. Из Просмотра событий (Журналы Windows → Приложение → «Application Error»
   свежий по python.exe): **Faulting module name** и **Exception code** —
   это сразу назовёт DLL-виновника (qwindows.dll / Qt6Multimedia.dll /
   ntdll.dll / драйвер GPU и т.п.).
5. Есть ли оверлейный софт: Discord overlay, MSI Afterburner/RTSS,
   GeForce Experience ShadowPlay, Bandicam; и менялись ли недавно драйверы GPU.

## Границы этого этапа

Данные по виновнику ждём с машины пользователя — воспроизвести Windows-фолт
в Linux-среде невозможно, а гадать по следам неинформативно. Как только
компонент назван по матрице 1–6 — фикс будет точечным (наиболее вероятный
исход №1 → отказ от раннего QSoundEffect + явный gate при нуле аудио-
устройств, плюс отложенный первый тон).
