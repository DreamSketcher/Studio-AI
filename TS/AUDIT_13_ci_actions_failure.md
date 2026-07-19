# AUDIT 13 — падение GitHub Actions (run 29679875653)

Дата: 2026-07-19. Репозиторий: `DreamSketcher/Studio-AI`, ветка `main`.

## Симптом

Workflow **«Architecture Gate & Headless Tests»** (`.github/workflows/architecture_gate.yml`),
run [29679875653](https://github.com/DreamSketcher/Studio-AI/actions/runs/29679875653) — **failure**.

| Job | Результат |
|---|---|
| Architecture gate (import-linter + plugin manifests) | ✅ success |
| Headless tests (ubuntu-latest / py3.11) | ❌ failure |
| Headless tests (windows-latest / py3.11) | ❌ failure |
| Headless tests (macos-latest / py3.11) | ❌ failure |

Во всех трёх упавших job'ах ломается **один и тот же шаг №5
«Install core dependencies (no GUI frameworks, no heavy ML)»**;
шаги smoke-import и pytest идут с `skipped` (последствие, а не причина).

## Контекст: что за коммит `2d419f6`

История `main` на GitHub:

```
2d419f6  Update              ← упавший пуш (CI-триггер)
42afaed  Docs — …            ← наш коммит документации (push ок)
05ffe87  (Stage 12 — ТОЛЬКО локально, на remote НЕТ)
… Stage 06–11 …               ← наши этапы, запушены ранее
```

Пуш `2d419f6` сделан поверх `42afaed` (т.е. **Stage 12 / experience layer
на GitHub ещё не попадал** — он существует только в локальном клоне
`/home/user/Studio-AI` как `05ffe87`).

Коммит `2d419f6` помимо workflow принёс случайный мусор:
**47 байткод-файлов `__pycache__/*.cpython-314.pyc`** (репозиторный
`.gitignore` содержал только `.import_linter_cache`) и маркер
`.sudo_as_admin_successful`.

## Причина (root cause)

Шаг №5 workflow выполняет:

```bash
pip install -r requirements-core.txt
```

Файла **`requirements-core.txt` в репозитории НЕТ** (проверено по дереву
коммита `2d419f6` через API — 229 файлов, из `requirements*` есть только
`requirements.txt`). В апстриме `DreamSketcher/XTTS-Studio-AI` этого файла
тоже нет. `pip` завершается с `ERROR: Could not open requirements file` →
exit code 1 → шаг падает на всех трёх ОС, остальные шаги пропускаются.

При этом нужный набор зависимостей уже существует: `requirements.txt`
в репозитории — это ровно **headless-набор ядра без GUI и без ML**
(numpy, soundfile, pydub, cryptography, certifi, num2words, psutil,
py-cpuinfo, packaging, PyYAML, requests, loguru), о чём прямо сказано
в его шапке-комментарии.

## Фикс

Подготовлено два `git am`-патча поверх `2d419f6`:

1. **`CI_FIX_01_requirements_core.patch`** — обязательный.
   В workflow одна строка:
   `pip install -r requirements-core.txt` →
   `pip install -r requirements.txt  # headless-набор ядра (без GUI и ML)`.
   Единый источник правды о зависимостях, без дублирования файла.

2. **`CI_FIX_02_cleanup_pycache.patch`** — рекомендуемый (гигиена).
   Убирает из индекса 47 `__pycache__/*.pyc` и `.sudo_as_admin_successful`,
   расширяет `.gitignore` (`__pycache__/`, `*.py[cod]`, `outputs/`,
   `cache/`, `json/usage_stats.json`, `json/history.json`,
   `.sudo_as_admin_successful`, `.import_linter_cache`).
   Файлы не удаляются с диска — только из индекса (`git rm --cached`).

## Верификация (полный прогон CI-шагов на исправленном дереве)

Клон репозитория на коммите `2d419f6` + оба патча, чистый venv, только
зависимости из `requirements.txt` + `pytest pytest-timeout pytest-cov
import-linter packaging`:

```
pip install -r requirements.txt ................................ OK
python -c "import ai_studio_core.env_core ..." ................. headless import OK
python tools/check_architecture.py ............................. layered_architecture KEPT (1 kept, 0 broken)
python tools/check_plugin_deps.py .............................. OK (1 манифест, ошибок нет)
pytest (13 файлов из workflow) ................................. 176 passed, 1 skipped
```

Т.е. после патча №1 весь workflow должен стать зелёным на всех трёх ОС
(все зависимости имеют колёса/чистый Python под win/mac/linux + py3.11;
apt-шаг (ffmpeg, libsndfile1) нужен только для Linux и в workflow уже
условный).

## Как применить (на машине с push-доступом)

```bash
git clone https://github.com/DreamSketcher/Studio-AI
cd Studio-AI
git am /путь/к/CI_FIX_01_requirements_core.patch
git am /путь/к/CI_FIX_02_cleanup_pycache.patch   # опционально, но рекомендую
git push
```

После пуша Actions перезапустится сам.

## Замечания на будущее (не блокеры)

- **Stage 12 (`05ffe87`, experience layer) есть только локально.** Его
  код писался поверх вложенной структуры, а remote после `2d419f6` —
  «плоский». Перед пушем Stage 12 нужна будет аккуратная переброска
  (rebase/cherry-pick с учётом нового корня).
- В репозитории трекαется `logs/xtts_studio.log` — runtime-лог. Желательно
  тоже убрать из индекса и добавить `logs/*.log` в `.gitignore`
  (не включено в патч №2, т.к. локальный ритуал коммитов опирался на этот файл).
- Коммиты лучше делать **до** запуска приложения после `git add -A` —
  именно так в индекс попали `*.pyc` и sudo-маркер.
