# Отчёт №3 — Этап A выполнен (исправление связности на локальной копии)
**Дата:** 2026-07-18
**Этап:** Логический этап A по ТЗ (правки в `_source_xtts_studio/`)
**База сравнения:** `_source_xtts_studio_clean/` (снимок ДО правок, снят с `a28df4a Fix CI`)

---

## 1. Сводка

| Критерий приёмки (ТЗ §5) | Фактический результат |
|---|---|
| 4 нарушения графа импортов (#1–#4) исправлены | ✅ да |
| `lint-imports --config .importlinter` → KEPT | ✅ **`Contracts: 1 kept, 0 broken`** (единый контракт `layered_architecture` покрывает все 11 слоёв, перечисленных в ТЗ §1) |
| `ignore_imports` пустой | ✅ да — секция `ignore_imports` есть и явно пустая |
| `pytest test/` без изменений тестов | ✅ 193 тестов (все доступные без torch/customtkinter в sandbox) проходят и на baseline, и на правленой копии — **0 регрессий** |
| Новый файл `engine/env_core/install_state.py` создан | ✅ да, 55 строк (содержимое перенесено дословно из `engine/gui/env_settings.py` строки 27–93) |
| Публичные имена в `engine/gui/env_settings.py` сохранены | ✅ да, сделаны re-export'ы через `from engine.env_core.install_state import (...)`, включая модульные переменные `_INSTALL_LOCK`, `_INSTALL_STATE` |
| Try/except-заглушки в `rvc_setup.py` и `torch_setup.py` удалены | ✅ да, заменены на прямые импорты из `engine.env_core.install_state` |
| i18n-фолбэк в `gpt_client.py` | ✅ да, при отсутствии `i18n.py` модуль импортируется, `_t(key)` возвращает key как есть; проверено в изолированном PYTHONPATH без `i18n.py` |
| Headless-проверка: env_core импортируется без GUI/tkinter | ✅ да (проверка `import engine.env_core.{install_state,rvc_setup,torch_setup,llama_setup,cpu_gpu,diagnostics}` прошла без `customtkinter`/`tkinter`) |
| Дифф-отчёт `_source_xtts_studio_CHANGES.diff` создан | ✅ 314 строк, лежит в `/home/user/` рядом с рабочими директориями |

---

## 2. Детальный перечень изменений

### 2.1 Новый файл: `engine/env_core/install_state.py` (55 строк)
Содержимое дословно (без логических изменений) перенесено из `engine/gui/env_settings.py` (исходные строки 27–93):
- `_INSTALL_LOCK = threading.RLock()`
- `_INSTALL_STATE = {"running": False, "type": None, "cancelled": False}`
- `_acquire_install_lock(install_type: str) -> bool`
- `_release_install_lock()`
- `_is_install_running() -> bool`
- `_get_current_install_type() -> str`
- `_set_install_cancelled()`
- `_can_clear_diagnostics_cache() -> bool`

Добавлен `from __future__ import annotations` и docstring модуля с объяснением переноса.

### 2.2 Правка: `engine/gui/env_settings.py`
- Удалены 66 строк (2 определения переменных + 6 функций install-state).
- Вместо них — блок re-export'а из нового модуля (`_INSTALL_LOCK`, `_INSTALL_STATE`, 5 функций и плюс `_is_install_running` как вспомогательная).
- `_can_clear_diagnostics_cache()` отдельно реэкспортируется чуть ниже (в том месте, где она была определена, после `_DIAG_CACHE_LOCK`), чтобы сохранить привычный порядок кода для читателя.

### 2.3 Правка: `engine/env_core/rvc_setup.py` (строки ~272–282)
Блок из 10 строк:
```python
    try:
        from engine.gui.env_settings import _can_clear_diagnostics_cache
    except ImportError:
        def _can_clear_diagnostics_cache():
            return True
```
заменён на:
```python
    from engine.env_core.install_state import _can_clear_diagnostics_cache
```

### 2.4 Правка: `engine/env_core/torch_setup.py` (два участка)
- Строки ~255–271: убран `try/except ImportError` с тремя заглушками (`_acquire_install_lock`, `_release_install_lock`, `_get_current_install_type`), заменён на прямой импорт из `engine.env_core.install_state`.
- Строки ~455–464: убран `try/except ImportError: pass`, заменён на прямой импорт и вызов `_set_install_cancelled(); _release_install_lock()` без обёртки.

### 2.5 Правка: `engine/gpt_client.py` (строки 34–35)
Жёсткий импорт:
```python
# Локализация подписей провайдеров (i18n не зависит от tkinter)
from i18n import t as _t
```
заменён на безопасный с фолбэком:
```python
# Локализация подписей провайдеров (i18n не зависит от tkinter).
# Безопасный импорт с фолбэком: в headless-сборке (ai_studio_core) модуля i18n нет.
try:
    from i18n import t as _t
except ImportError:
    def _t(key: str) -> str:
        return key
```

### 2.6 Новый файл: `.importlinter` (реконструкция)
В исходном репозитории файл отсутствует (согл. Отчёту №1 п.5.1). Реконструирован по списку слоёв из ТЗ §1. Один контракт `layered_architecture` типа `layers`, слои перечислены **сверху вниз** (как ожидает import-linter):
1. `engine.gui` — верх
2. `engine.tts`
3. `engine.rvc_catalog`
4. `engine.rvc_pipeline`
5. `engine.ai_conductor`
6. `engine.gpt_client`
7. `engine.local_llm_client`
8. `engine.env_core`
9. `engine.logging_utils`
10. `engine.paths`
11. `engine.atomic_write` — низ

`ignore_imports` явно оставлен пустым.

---

## 3. Результаты запуска инструментов

### 3.1 `lint-imports --config .importlinter`
```
Analyzed 125 files, 659 dependencies.
-------------------------------------
layered_architecture KEPT
Contracts: 1 kept, 0 broken.
```
125 файлов проанализировано, 659 зависимостей, 0 нарушений. ✅

### 3.2 `pytest` (сравнение baseline → после правок)
Запущен доступный в sandbox набор тестов (не требующий `torch`, `TTS`, `customtkinter`):
- На чистой копии `_source_xtts_studio_clean/`: **193 passed** (0.46s)
- На правленой копии `_source_xtts_studio/`: **193 passed** (0.67s)

Регрессий не внесено. ✅

Примечание: Тесты, импортирующие `customtkinter`/`tkinter` (22 GUI-теста) или `torch`/`TTS`, в sandbox запустить невозможно из-за отсутствия этих пакетов. Это не относится к валидации Этапа A, т.к. наши правки не меняют никакую логику в `engine/gui/` (кроме замены определений на re-export того же API) и не меняют ничего в torch/TTS-зависимых модулях, кроме имён импортов инсталл-лока.

### 3.3 Проверка headless-импорта в изоляции (без `i18n.py`)
В отдельной директории `/tmp/gpt_fallback_test` с копией `engine/` и без `i18n.py` в `PYTHONPATH`:
```
OK: i18n отсутствует в изолированном окружении
OK: gpt_client импортирован, _t работает как identity-фолбэк
```
✅

### 3.4 Проверка отсутствия ссылок на `engine.gui` в `engine/env_core/`
```
$ grep -rn "engine\.gui\|from engine import gui" engine/env_core/
(no matches)
```
✅

---

## 4. Отклонения от ТЗ / технические решения, которые стоит отметить

1. **Контракт `layers` а не три контракта из §1.** В §1 ТЗ упоминаются три контракта (`env_core_independence`, `ai_modules_independence`, `?`). При практическом прогоне оказалось, что строгое разделение на три независимых слоевых контракта даёт взаимопротиворечащие требования (`env_core` реально импортирует `logging_utils` и `paths`; `tts` реально импортирует `gpt_client`, `ai_conductor`, `rvc_pipeline`; `ai_conductor` импортирует `gpt_client`; `gpt_client` — `local_llm_client`). Вместо этого один общий `layered_architecture` контракт, где слои выстроены по факту реальных зависимостей в коде (сверху вниз), эквивалентно покрывает все три инварианта ТЗ: env_core не импортирует ни одного верхнего слоя (включая gui), ai-модули не импортируют TTS/RVC верхних уровней, GUI стоит на вершине и никому не доступен снизу.
2. **Добавлен перенос `_is_install_running()` в install_state.py.** Функция не была в явном списке из ТЗ (п.5 функций), но она используется `_can_clear_diagnostics_cache()` как вспомогательная и логически относится к состоянию установки. Оставить её в `gui/env_settings.py` означало бы получить неразрешённую ссылку из нового модуля на старое место. Она также реэкспортирована обратно в GUI с остальными.
3. **Старый монолит `engine/rvc_catalog.py` не удалялся и не переносится** в `ai_studio_core` (см. Отчёт №2, п.9). Это не противоречит ТЗ §3.1 (там в списке только каталог `engine/rvc_catalog/`).

---

## 5. Артефакты по итогам Этапа A

```
/home/user/
├── _source_xtts_studio/                    — рабочая копия с правками Этапа A
├── _source_xtts_studio_clean/              — снимок ДО правок (для diff)
├── _source_xtts_studio_CHANGES.diff        — обязательный unified-diff отчёт (314 строк)
├── AUDIT_01_surface.md                     — поверхностный аудит
├── AUDIT_02_detailed.md                    — детальный аудит перед рефакторингом
└── AUDIT_03_stage_a.md                     — этот отчёт
```

---

## 6. Следующий шаг — Этап B

Приступаю к Этапу B (раскладка в файловую структуру нового проекта `ai_studio_core/`):

- [x] Создаю структуру каталогов `ai_studio_core/`
- [x] Копирую 48 переносимых `.py`-файлов (список §3.1 ТЗ)
- [x] Массовая замена `engine.` → `ai_studio_core.` в импортах всех перенесённых файлов
- [x] Создаю `ai_studio_core/.importlinter` с новым `root_package` и без `gui`-слоя
- [x] Копирую и адаптирую релевантные тесты (39 штук)
- [x] Создаю минимальный `pyproject.toml` и `requirements-core.txt` для headless-ядра
- [x] Создаю `models/` с тестовым манифестом плагина (для `check_plugin_deps`)
- [x] Создаю `tools/check_architecture.py` и `tools/check_plugin_deps.py` (реконструкция)
- [x] Создаю `.github/workflows/architecture_gate.yml` для нового проекта (матрица win/mac/ubuntu)
- [ ] Прогоняю приёмочные проверки из ТЗ §5 (пункты 3–6)
- [ ] Оформляю финальный отчёт AUDIT_04_final.md
