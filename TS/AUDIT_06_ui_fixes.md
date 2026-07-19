# Отчёт №6 — Приведение UI-слоя (PySide6 workspaces) в рабочее состояние

**Дата:** 2026-07-18
**Этап:** Отладка и достройка workspace-UI (`ai_studio_core/ui/`) по blueprint
из `uploads/Новый текстовый документ.txt`. Без правки ядра (headless-модули не тронуты).

---

## 1. Сводка

Клонирован `DreamSketcher/Studio-AI` (ветка `main`). Обнаружено, что workspace-UI
из blueprint уже присутствует в `ai_studio_core/ai_studio_core/ui/`, но приложение
**не запускалось**: конструктор главного окна падал в `TTSWorkspace`.

Проведён аудит всех 36 файлов UI-слоя по шаблонам blueprint, исправлены
3 дефекта, добавлены 2 недостающих файла из дерева blueprint
(`image_workspace.py`, `inspector_panel.py`). Проверено offscreen-рендерингом,
функциональными прогонами (TTS-генерация, чат) и регрессией ядра.

**Результат:** `python run_gui.py` стартует; 4 рабочих пространства
(🎙 TTS / 💬 Chat / 🖼 Image / 🔗 Pipeline), 6 dock-панелей, toast,
pipeline-strip и очередь задач — работают.

---

## 2. Исправленные дефекты

### 2.1 `workspaces/tts_workspace.py` — краш при запуске (критично)

Конструктор `MainWindow` падал:

```
AttributeError: 'TTSWorkspace' object has no attribute '_accent_btn_style'
```

Файл был оборван: отсутствовали метод `_accent_btn_style()` и обработчик
`_on_generate` (на который ссылался `clicked.connect(...)`), поэтому сигнал
`generate_requested` не мог быть испущен в принципе.

**Исправление:** дописан `_accent_btn_style()` (стили по дизайн-токенам) и
`_on_generate()` — собирает параметры из сайдбара (язык, temperature/speed/top-p/
repetition, блок RVC, формат/частота, reference audio) и эмитит
`generate_requested(text, params)` согласно протоколу blueprint.
`set_busy()` теперь также корректно управляет кнопкой Export.

### 2.2 `controllers/tts_controller.py` — TTS-движок никогда не загружался

```python
from ai_studio_core.chunker import TextChunker
self._chunk_fn = TextChunker().chunk      # <-- метода нет
```

У `TextChunker` метод называется `chunk_text(...)`; `AttributeError` попадал в
`try/except`, и UI всегда показывал «TTS engine unavailable».

**Исправление:** `TextChunker().chunk_text`. После правки загрузка
`normalizer` + `chunker` проходит (см. лог-консоль: `TTS engine dependencies loaded`).

### 2.3 `controllers/chat_controller.py` — дублирование сообщения пользователя

Workspace рисует user-пузырь сам (`_on_send` → `ChatBubble("user", ...)`), а
контроллер вторично эмитил `message_added("user", ...)` → в чате появлялись
два одинаковых пузыря подряд.

**Исправление:** эхо-эмиссия удалена (с комментарием в коде).

---

## 3. Новые файлы (заявлены в дереве blueprint, отсутствовали в репо)

| Файл | Назначение |
|---|---|
| `ui/workspaces/image_workspace.py` | 🖼 Image Generation (заглушка): тулбар Generate/Stop + селектор модели, поле промпта, ввод стилевых тегов (`TagInput`), сетка-плейсхолдеры результатов 2×2, сайдбар Sampler (steps/CFG/seed) и Output (size/batch), pipeline-strip `Prompt → Model → Sampler → Upscale → Output`. Сигналы `generate_requested(prompt, params)` / `stop_requested` — под будущий image-контроллер. |
| `ui/panels/inspector_panel.py` | Инспектор выбранного элемента: заголовок, тип, таблица «ключ → значение», поле деталей. Публичный API `show_item()/clear()` под будущую интеграцию с сигналами выбора (Model Hub/Queue/Pipeline). |

Сопутствующие правки:
- `ui/widgets/tag_input.py` — конструктор принимает `placeholder=...`
  (обратно-совместимо, дефолт `"add tag…"`).
- `ui/workspaces/__init__.py` — экспорт `ImageWorkspace`.
- `ui/panels/__init__.py` — экспорт `InspectorPanel`.
- `ui/main_window.py` — вкладка **🖼 Image** между Chat и Pipeline (соответствует
  схеме в docstring `MainWindow`); dock **Inspector** табифицирован с Settings
  (соответствует блоку «Settings / Inspector» в той же схеме). По умолчанию
  видна Settings.

---

## 4. Проверка

| Проверка | Результат |
|---|---|
| Конструирование `MainWindow` + 4 вкладки (offscreen) | ✅ |
| Инстанцирование всех виджетов, панелей, диалогов | ✅ |
| TTS flow: текст → normalize → chunk → синтез (demo) → `generation_complete` | ✅ |
| Pipeline-strip: состояния шагов active/done/error | ✅ |
| Chat flow: отправка → user-пузырь (один) → ответ ассистента | ✅ |
| Лог-консоль: записи `(INFO/…)` доходят из контроллеров | ✅ |
| `pytest test/` (без torch-зависимых: `test_qc`, `test_task_manager`, `test_tts_utils`) | ✅ **486 passed** |
| `lint-imports` (contract `layered_architecture`) | ✅ **KEPT, 0 broken** |

Скриншоты offscreen-рендера (1440×900) приложены в корне репозитория:
`ui_workspace_tts.png`, `ui_workspace_chat.png`, `ui_workspace_image.png`,
`ui_workspace_pipeline.png`. Стрельнувшие «🖼»-иконки на скриншотах — особенность
offscreen-шрифтов среды, на десктопе отображаются нормально.

> torch-зависимые тесты не запускались: в среде нет `torch` (опциональная
> ML-зависимость, ставится через `pip install -e ".[ml]"`); к правкам UI
> отношения не имеет.

---

## 5. Изменённые файлы (diff относительно `main`)

```
 M  ai_studio_core/ai_studio_core/ui/controllers/chat_controller.py
 M  ai_studio_core/ai_studio_core/ui/controllers/tts_controller.py
 M  ai_studio_core/ai_studio_core/ui/main_window.py
 M  ai_studio_core/ai_studio_core/ui/panels/__init__.py
 M  ai_studio_core/ai_studio_core/ui/widgets/tag_input.py
 M  ai_studio_core/ai_studio_core/ui/workspaces/__init__.py
 M  ai_studio_core/ai_studio_core/ui/workspaces/tts_workspace.py
??  ai_studio_core/ai_studio_core/ui/panels/inspector_panel.py
??  ai_studio_core/ai_studio_core/ui/workspaces/image_workspace.py
```

Ядро (`normalizer`, `chunker`, `gpt_client`, `tts/*`, `env_core/*` и т.д.) —
**без изменений**.

---

## 6. Запуск

```bash
cd ai_studio_core
pip install -e ".[gui]"      # или: pip install PySide6 num2words
python run_gui.py
```

Без `num2words` UI всё равно стартует (core_bridge-подход), но TTS flow
остановится на шаге загрузки движка с понятным сообщением в тосте и консоли.
