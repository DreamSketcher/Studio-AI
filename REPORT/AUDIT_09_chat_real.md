# Отчёт №9 — Реальный чат с LLM: провайдеры/ключи, история, выбор модели и TTS-бэкенда

**Дата:** 2026-07-19
**Этап:** Замена демо-чата на рабочую интеграцию с `gpt_client`. Без заглушек
«насколько позволяет окружение»: у среды нет ни одного реального API-ключа —
поэтому тесты ходят на **настоящий OpenAI-совместимый HTTP-сервер**, поднятый
на loopback (127.0.0.1) — единственный адрес, для которого `gpt_client`
разрешает `http://`.

---

## 1. Что было заглушкой → чем стало

| Было | Стало |
|---|---|
| Чат молча ничего не делал / манекен-ответ | Реальный вызов `gpt_client.chat` в worker-потоке, история диалога, ответ в пузырь |
| Селектор модели слал в контроллер декорированный текст «✅ name ✓ (provider)» → в `set_model` попадал мусор; `max_tokens` из сайдбара игнорировался | `send_requested` несёт честные `model_id` (userData) и `max_tokens` (int), оба проброшены в payload API |
| `gpt_client`: `temperature`/`max_tokens` захардкожены (0.7/2048) | Параметры проведены: `chat() → _call_with_chain → _call_api → payload` |
| Settings → нет управления LLM | Группа «LLM Provider»: список провайдеров (встроенные + кастомные), ввод API-ключа (Password echo), состояние ключа (задан/не задан), сохранение в `gpt_settings.json` через `secret_store` (ключ не в plaintext) |
| `ModelSelector`: вшитые демо-списки («GPT-4o», «XTTS v2.0.2», «Male v2»…) | Стартует пустым; наполняется только реальными данными контроллеров: каталог активного LLM-провайдера, доступные TTS-движки, `.pth`-файлы на диске |
| TTS-селектор декоративный | Реальный выбор движка: Auto / Coqui XTTS v2 / espeak-ng со статусами ✅/📥/❌ по факту окружения; закреплённый недоступный движок → явная ошибка `ctl_backend_missing`, файла-пустышки нет |
| RVC-селектор — вшитые «Male v2 / Female v1» | Реальный рекурсивный скан `models/` на `*.pth`; пусто — честно пусто |

## 2. Изменения по файлам

### Ядро
- **`gpt_client.py`** — `chat(prompt, history, system, max_tokens, temperature)`;
  оба параметра доезжают до JSON-payload; у кастомных провайдеров — как у встроенных.
- **`i18n.py`** — +8 ключей Settings→LLM (`set_llm`, `set_provider`, `set_api_key`,
  `set_api_key_ph`, `set_save`, `set_key_state_ok/missing`, `set_key_saved`) на EN/RU;
  +3 ключа селекторов (`model_auto`, `prov_engines`, `ctl_backend_missing`);
  `ctl_llm_missing` переформулирован под реальный путь настройки.

### UI
- **`ui/widgets/model_selector.py`** — переписан: демо-заливка удалена;
  `set_models()` пересобирает список **без ложной эмиссии** `model_changed`;
  запись `current: True` подсвечивается программно; `current_model_id()`,
  `select_id()` без сигнала.
- **`ui/workspaces/chat_workspace.py`** — `send_requested(str,str,str,float,int)`;
  публичные `set_models()/model_selector()`; sidebar-параметры честно едут в сигнал.
- **`ui/workspaces/tts_workspace.py`** — акцессоры `model_selector()/rvc_selector()`;
  `rvc_model` в params — id (путь), не label.
- **`ui/controllers/chat_controller.py`** — переписан: история контроллера;
  `available_models()` из каталога **активного** провайдера (ключ есть → ✅, нет → ❌);
  `select_model()` персистит выбор; `on_send(message, system, model, temperature, max_tokens)`;
  `AIUnavailable`/любой сбой → сообщение «⚠ …» в чат + статус, **фальшивых ответов нет**;
  `on_clear()` очищает историю.
- **`ui/controllers/tts_controller.py`** — `available_models()` (auto/coqui/espeak
  со статусами из реального окружения), `select_backend()` (неизвестный id → WARN,
  выбор не меняется), `_resolve_backend()` уважает закреплённый выбор,
  `rvc_models()` — реальный скан `MODEL_DIR/**/*.pth`.
- **`ui/panels/settings_panel.py`** — группа LLM Provider + сигнал `llm_saved`;
  `_rebuild_providers()` без дублирования connect'ов; `retranslate_ui()`
  перечитывает подписи провайдеров из `gpt_client` (живое RU/EN).
- **`ui/main_window.py`** — проводка: `model_changed → select_model/select_backend`,
  заливка селекторов при старте, `llm_saved → _on_llm_saved` (обновить каталог +
  toast «Настройки LLM сохранены»).

## 3. Тесты (новые, 28 шт.)

**`test_chat_real.py`** (20):
- *Loopback gpt_client (6):* реальный HTTP roundtrip; payload несёт
  system/history/temperature/max_tokens/model; без ключей → `AIUnavailable`
  **до** выхода в сеть; сервер 500 → `AIUnavailable`, краша нет; ключ в файле
  не plaintext.
- *ChatController (4):* два хода end-to-end (история накапливается и видна
  серверу, busy True→False, очистка); нет провайдера → «⚠ AIUnavailable…»
  в чат без фабрикации; ядро не импортируется → честный гейт `ctl_llm_missing`;
  `available_models`/`select_model` roundtrip с флагом `current`.
- *SettingsPanel (4):* кастомный провайдер виден; сохранение провайдера+ключа
  (в файле не plaintext, поле очищено, `llm_saved` эмитнут); состояние ключа
  отражает факт; пустое поле ключа не затирает сохранённый.
- *ModelSelector/ChatWorkspace (6):* конструктор без демо-стабов; тихая
  пересборка и подсветка current; выбор пользователя эмитит id;
  `select_id` без сигнала; `send_requested` несёт `(текст, системный, id, 0.42, 512)`.

**`test_backend_select_real.py`** (8): статусы движков из реального окружения;
закреплённый espeak **реально синтезирует** WAV; закреплённый недоступный
coqui → ошибка с именем движка, файла нет; неизвестный id → WARN;
auto-fallback coqui→espeak; повторный выбор сбрасывает кэш; RVC-скан
находит реальные `.pth`, пустой каталог — честно пустой.

## 4. Проверки

- Полный прогон: **586 passed** (было 558), 3 файла требуют torch — вне среды.
- `lint-imports`: контракт `layered_architecture` — **KEPT**.
- Скриншот `ui_workspace_chat_real.png`: русский UI, реальный диалог в 2 хода
  против loopback-сервера, селектор «qa-model-1 (Loopback QA)», ключ ✓.

## 5. Осознанные границы (не заглушки)

- Скрытый проброс реальных ключей невозможен офлайн: боевые Groq/OpenRouter/ProxyAPI
  не дёргались (нет ключей/сети к ним); протокол идентичен loopback-серверу.
- «Стриминг» шага пайплайна чата — декоративного посимвольного вывода нет:
  голые провайдеры отдают ответ целиком; UI честно показывает один ответ.
- `secret_store` на Linux вне тестов требует Windows DPAPI → сохранение ключа
  даст **явную** `SecretStoreUnavailable` (fail-closed by design ядра).
