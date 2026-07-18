# -*- coding: utf-8 -*-
"""ai_studio_core/i18n.py — локализация интерфейса (EN/RU).

Единый источник правды для строк UI и подписей провайдеров gpt_client.

Гарантии:
  * t(key) НИКОГДА не бросает исключений — нет ключа: возвращает сам ключ
    (видно в UI, что перевод отсутствует), нет языка: фолбэк на английский.
  * set_language() принимает только зарегистрированные коды, любой другой
    ввод безопасно игнорируется (возвращает False). История: переключение
    языка падало с AttributeError/KeyError — здесь эти пути закрыты.

Для живого переключения:
  set_language("ru"); gpt_client.refresh_i18n_labels(); UI.retranslate_ui()
"""
from __future__ import annotations

LANGUAGES: dict[str, str] = {
    "en": "English",
    "ru": "Русский",
}
DEFAULT_LANGUAGE = "en"

_current_language = DEFAULT_LANGUAGE


def available_languages() -> dict[str, str]:
    """{код: отображаемое имя} — для комбобоксов настроек."""
    return dict(LANGUAGES)


def set_language(code: str) -> bool:
    """Переключает текущий язык. Неизвестный код игнорируется (False)."""
    global _current_language
    if isinstance(code, str) and code in LANGUAGES:
        _current_language = code
        return True
    return False


def get_language() -> str:
    return _current_language


def t(key: str, lang: str | None = None) -> str:
    """Возвращает перевод ключа. Никогда не бросает исключений."""
    try:
        use_lang = lang if lang in LANGUAGES else _current_language
        text = TRANSLATIONS.get(use_lang, {}).get(key)
        if text is None:
            text = TRANSLATIONS.get(DEFAULT_LANGUAGE, {}).get(key)
        return text if isinstance(text, str) else str(key)
    except Exception:  # pragma: no cover - защита от экзотики
        return str(key)


# Короткий алиас для мест, где строк много
tr = t


TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # ── main window: menus & actions ──
        "menu_file": "&File",
        "menu_view": "&View",
        "menu_models": "&Models",
        "menu_tools": "&Tools",
        "menu_help": "&Help",
        "act_new_project": "New Project",
        "act_open_project": "Open Project…",
        "act_save_project": "Save Project…",
        "act_export": "Export…",
        "act_exit": "Exit",
        "act_download_model": "Download Model…",
        "act_manage_models": "Manage Models…",
        "act_env_wizard": "Environment Setup Wizard…",
        "act_about": "About",
        # ── workspaces tabs & docks ──
        "tab_tts": "🎙  TTS",
        "tab_chat": "💬  Chat",
        "tab_image": "🖼  Image",
        "tab_pipeline": "🔗  Pipeline",
        "dock_model_hub": "Model Hub",
        "dock_settings": "Settings",
        "dock_inspector": "Inspector",
        "dock_queue": "Queue",
        "dock_console": "Console",
        "dock_history": "History",
        # ── statusbar / common status ──
        "sb_queue": "Queue:",
        "msg_ready": "Ready",
        "msg_welcome": "Welcome to AI Studio",
        "msg_menu_stub": "This menu item is a placeholder in the demo UI",
        "msg_generation_complete": "Generation complete",
        "msg_project_saved": "Project saved",
        "msg_project_loaded": "Project loaded",
        # ── pipeline steps (shared) ──
        "step_input": "Input",
        "step_normalize": "Normalize",
        "step_tts": "TTS",
        "step_rvc": "RVC",
        "step_deess": "De-ess",
        "step_output": "Output",
        "step_user": "User",
        "step_sysctx": "System+Context",
        "step_llm_api": "LLM API",
        "step_stream": "Stream",
        "step_response": "Response",
        "step_prompt": "Prompt",
        "step_model": "Model",
        "step_sampler": "Sampler",
        "step_upscale": "Upscale",
        "step_process": "Process",
        # ── TTS workspace ──
        "tts_generate": "▶  Generate",
        "tts_stop": "⏹  Stop",
        "tts_export": "📥  Export",
        "tts_model_ph": "Select TTS model…",
        "tts_drop_label": "Drop reference audio here\nor click to browse",
        "tts_text_ph": "Enter text to synthesize…\n\nSupports multi-paragraph, auto-chunking, and SSML tags.",
        "tts_voice_params": "Voice Parameters",
        "tts_language": "Language:",
        "tts_temperature": "Temperature:",
        "tts_speed": "Speed:",
        "tts_top_p": "Top-P:",
        "tts_repetition": "Repetition:",
        "tts_rvc_block": "RVC Voice Conversion",
        "tts_rvc_enable": "Enable RVC",
        "tts_rvc_model": "Model:",
        "tts_rvc_ph": "Select RVC…",
        "tts_index_rate": "Index rate:",
        "tts_pitch": "Pitch shift:",
        "tts_output_block": "Output",
        "tts_format": "Format:",
        "tts_sample_rate": "Sample rate:",
        "tts_autoplay": "Auto-play after generation",
        # ── Chat workspace ──
        "chat_model": " Model: ",
        "chat_temp": " Temp: ",
        "chat_clear": "🗑  Clear",
        "chat_input_ph": "Type a message…",
        "chat_sys_block": "System Prompt",
        "chat_sys_ph": "You are a helpful assistant…",
        "chat_params": "Parameters",
        "chat_max_tokens": "Max tokens:",
        "chat_context": "Context",
        "chat_tokens_lbl": "Tokens:",
        "chat_cost_lbl": "Estimated cost:",
        "chat_greeting": "Hello! How can I help you today?",
        # ── Image workspace ──
        "img_model_ph": "Select image model…",
        "img_prompt_ph": "Describe the image to generate…\n\nSupports prompts, negative prompts and style tags.",
        "img_tags_ph": "Style tags (Enter to add)…",
        "img_sampler": "Sampler",
        "img_steps": "Steps:",
        "img_cfg": "CFG:",
        "img_seed": "Seed:",
        "img_seed_random": "random",
        "img_output_block": "Output",
        "img_size": "Size:",
        "img_batch": "Batch:",
        "img_cell": "Image",
        # ── Pipeline workspace ──
        "pipe_title": "Visual pipeline editor",
        "pipe_hint": "Build processing chains from nodes: Input → Normalize → TTS → RVC → Output.",
        "pipe_input_lbl": "Source text:",
        "pipe_input_ph": "Enter text that the pipeline will process when you press «Run»…",
        "pipe_add_input": "+ Input",
        "pipe_add_proc": "+ Processor",
        "pipe_add_out": "+ Output",
        "pipe_run": "▶ Run pipeline",
        # ── Model hub ──
        "hub_search_ph": "🔍 Search models…",
        "hub_all": "All",
        "hub_download": "📥 Download",
        "hub_delete": "🗑 Delete",
        "hub_refresh": "↻ Refresh",
        "hub_empty": "(no models found — place files into models/)",
        "hub_size": "Size:",
        # ── History ──
        "hist_search_ph": "Search history…",
        "hist_all": "All",
        "hist_empty": "(no generations yet)",
        "hist_open": "Open file",
        # ── Queue ──
        "queue_status": "Status",
        "queue_type": "Type",
        "queue_model": "Model",
        "queue_progress": "Progress",
        "queue_actions": "Actions",
        "queue_clear_done": "Clear Completed",
        # ── Inspector ──
        "insp_nothing": "Nothing selected",
        "insp_details_ph": "Details / metadata…",
        # ── Settings panel ──
        "set_general": "General",
        "set_theme": "Theme:",
        "set_language": "Language:",
        "set_autosave": "Auto-save projects",
        "set_performance": "Performance",
        "set_device": "Device:",
        "set_threads": "Worker threads:",
        "set_batch": "Batch size:",
        "set_paths": "Paths",
        "set_models_dir": "Models dir:",
        "set_output_dir": "Output dir:",
        "set_about": "About",
        "set_choose_dir": "Select directory",
        "theme_dark": "Dark",
        "device_auto": "Auto (GPU if available)",
        # ── Controllers / messages ──
        "ctl_engine_loaded": "TTS engine dependencies loaded",
        "ctl_tts_missing": "No TTS backend available: install Coqui TTS (pip install -e \".[ml]\") or espeak-ng",
        "ctl_rvc_missing": "RVC backend is not installed in this build (rvc-python + models)",
        "ctl_gen_cancelled": "Generation cancelled",
        "ctl_chat_cancelled": "Chat cancelled",
        "ctl_chat_cleared": "Chat cleared",
        "ctl_reply_received": "Reply received",
        "ctl_llm_missing": "LLM API key is not configured. Set it via Settings → Models (gpt settings) and try again.",
        "ctl_img_missing": "No image backend available: install diffusers/torch or configure an image API key",
        "ctl_export_done": "Exported:",
        "ctl_export_fail": "Export failed",
        # ── gpt_client provider labels ──
        "prov_groq": "Groq (fast, VPN required)",
        "prov_openrouter": "OpenRouter (works without VPN)",
        "prov_proxy": "Proxy (proxyapi/aitunnel, RUB payments)",
        "cat_openrouter_notes": "Access to hundreds of models; no VPN needed; top-up via card/crypto.",
        "cat_together_notes": "Fast inference of open models; card payment.",
        "cat_mistral_notes": "Official Mistral API; EU hosting.",
        "cat_deepinfra_notes": "Cheap inference of open models; simple pricing.",
        "cat_vsegpt_label": "VseGPT",
        "cat_vsegpt_notes": "RUB payments, broad model catalogue, RU support.",
        "cat_aitunnel_label": "AITunnel",
        "cat_aitunnel_notes": "RU payments, aggregator of popular models.",
        "cat_proxyapi_label": "ProxyAPI",
        "cat_proxyapi_notes": "RUB payments, stable proxy for OpenAI-compatible APIs.",
        # ── Dialogs ──
        "dlg_about_title": "About AI Studio",
        "dlg_ok": "OK",
        "dlg_cancel": "Cancel",
        "dlg_download_title": "Download model",
    },
    "ru": {
        # ── main window: menus & actions ──
        "menu_file": "&Файл",
        "menu_view": "&Вид",
        "menu_models": "&Модели",
        "menu_tools": "&Инструменты",
        "menu_help": "&Справка",
        "act_new_project": "Новый проект",
        "act_open_project": "Открыть проект…",
        "act_save_project": "Сохранить проект…",
        "act_export": "Экспорт…",
        "act_exit": "Выход",
        "act_download_model": "Скачать модель…",
        "act_manage_models": "Управление моделями…",
        "act_env_wizard": "Мастер настройки окружения…",
        "act_about": "О программе",
        # ── workspaces tabs & docks ──
        "tab_tts": "🎙  TTS",
        "tab_chat": "💬  Чат",
        "tab_image": "🖼  Изображения",
        "tab_pipeline": "🔗  Пайплайн",
        "dock_model_hub": "Модели",
        "dock_settings": "Настройки",
        "dock_inspector": "Инспектор",
        "dock_queue": "Очередь",
        "dock_console": "Консоль",
        "dock_history": "История",
        # ── statusbar / common ──
        "sb_queue": "Очередь:",
        "msg_ready": "Готов",
        "msg_welcome": "Добро пожаловать в AI Studio",
        "msg_menu_stub": "Этот пункт меню — заглушка в демо UI",
        "msg_generation_complete": "Генерация завершена",
        "msg_project_saved": "Проект сохранён",
        "msg_project_loaded": "Проект загружен",
        # ── pipeline steps ──
        "step_input": "Ввод",
        "step_normalize": "Нормализация",
        "step_tts": "TTS",
        "step_rvc": "RVC",
        "step_deess": "Де-есс",
        "step_output": "Вывод",
        "step_user": "Пользователь",
        "step_sysctx": "Система+Контекст",
        "step_llm_api": "LLM API",
        "step_stream": "Стриминг",
        "step_response": "Ответ",
        "step_prompt": "Промпт",
        "step_model": "Модель",
        "step_sampler": "Сэмплер",
        "step_upscale": "Апскейл",
        "step_process": "Обработка",
        # ── TTS workspace ──
        "tts_generate": "▶  Сгенерировать",
        "tts_stop": "⏹  Стоп",
        "tts_export": "📥  Экспорт",
        "tts_model_ph": "Выберите TTS-модель…",
        "tts_drop_label": "Перетащите референсное аудио сюда\nили нажмите для выбора",
        "tts_text_ph": "Введите текст для озвучки…\n\nПоддерживаются абзацы, авторазбивка на чанки и SSML-теги.",
        "tts_voice_params": "Параметры голоса",
        "tts_language": "Язык:",
        "tts_temperature": "Температура:",
        "tts_speed": "Скорость:",
        "tts_top_p": "Top-P:",
        "tts_repetition": "Повторы:",
        "tts_rvc_block": "RVC-конвертация голоса",
        "tts_rvc_enable": "Включить RVC",
        "tts_rvc_model": "Модель:",
        "tts_rvc_ph": "Выберите RVC…",
        "tts_index_rate": "Index rate:",
        "tts_pitch": "Сдвиг тона:",
        "tts_output_block": "Вывод",
        "tts_format": "Формат:",
        "tts_sample_rate": "Частота:",
        "tts_autoplay": "Автовоспроизведение после генерации",
        # ── Chat workspace ──
        "chat_model": " Модель: ",
        "chat_temp": " Темп.: ",
        "chat_clear": "🗑  Очистить",
        "chat_input_ph": "Введите сообщение…",
        "chat_sys_block": "Системный промпт",
        "chat_sys_ph": "Ты — полезный ассистент…",
        "chat_params": "Параметры",
        "chat_max_tokens": "Макс. токенов:",
        "chat_context": "Контекст",
        "chat_tokens_lbl": "Токены:",
        "chat_cost_lbl": "Оценка стоимости:",
        "chat_greeting": "Привет! Чем могу помочь?",
        # ── Image workspace ──
        "img_model_ph": "Выберите image-модель…",
        "img_prompt_ph": "Опишите изображение для генерации…\n\nПоддерживаются промпты, негативные промпты и стилевые теги.",
        "img_tags_ph": "Стилевые теги (Enter — добавить)…",
        "img_sampler": "Сэмплер",
        "img_steps": "Шаги:",
        "img_cfg": "CFG:",
        "img_seed": "Seed:",
        "img_seed_random": "случайный",
        "img_output_block": "Вывод",
        "img_size": "Размер:",
        "img_batch": "Пакет:",
        "img_cell": "Изображение",
        # ── Pipeline workspace ──
        "pipe_title": "Визуальный редактор пайплайнов",
        "pipe_hint": "Собирайте цепочки обработки из нод: Ввод → Нормализация → TTS → RVC → Вывод.",
        "pipe_input_lbl": "Исходный текст:",
        "pipe_input_ph": "Введите текст, который пайплайн обработает по кнопке «Запустить»…",
        "pipe_add_input": "+ Ввод",
        "pipe_add_proc": "+ Обработчик",
        "pipe_add_out": "+ Вывод",
        "pipe_run": "▶ Запустить пайплайн",
        # ── Model hub ──
        "hub_search_ph": "🔍 Поиск моделей…",
        "hub_all": "Все",
        "hub_download": "📥 Скачать",
        "hub_delete": "🗑 Удалить",
        "hub_refresh": "↻ Обновить",
        "hub_empty": "(модели не найдены — положите файлы в models/)",
        "hub_size": "Размер:",
        # ── History ──
        "hist_search_ph": "Поиск по истории…",
        "hist_all": "Все",
        "hist_empty": "(генераций пока нет)",
        "hist_open": "Открыть файл",
        # ── Queue ──
        "queue_status": "Статус",
        "queue_type": "Тип",
        "queue_model": "Модель",
        "queue_progress": "Прогресс",
        "queue_actions": "Действия",
        "queue_clear_done": "Убрать завершённые",
        # ── Inspector ──
        "insp_nothing": "Ничего не выбрано",
        "insp_details_ph": "Детали / метаданные…",
        # ── Settings panel ──
        "set_general": "Общие",
        "set_theme": "Тема:",
        "set_language": "Язык:",
        "set_autosave": "Автосохранение проектов",
        "set_performance": "Производительность",
        "set_device": "Устройство:",
        "set_threads": "Потоки воркеров:",
        "set_batch": "Размер пакета:",
        "set_paths": "Пути",
        "set_models_dir": "Каталог моделей:",
        "set_output_dir": "Каталог вывода:",
        "set_about": "О программе",
        "set_choose_dir": "Выберите каталог",
        "theme_dark": "Тёмная",
        "device_auto": "Авто (GPU, если доступен)",
        # ── Controllers / messages ──
        "ctl_engine_loaded": "Зависимости TTS-движка загружены",
        "ctl_tts_missing": "Нет доступного TTS-бэкенда: установите Coqui TTS (pip install -e \".[ml]\") или espeak-ng",
        "ctl_rvc_missing": "RVC-бэкенд не установлен в этой сборке (rvc-python + модели)",
        "ctl_gen_cancelled": "Генерация отменена",
        "ctl_chat_cancelled": "Чат отменён",
        "ctl_chat_cleared": "Чат очищен",
        "ctl_reply_received": "Ответ получен",
        "ctl_llm_missing": "API-ключ LLM не настроен. Укажите его в настройках моделей (gpt settings) и повторите.",
        "ctl_img_missing": "Нет image-бэкенда: установите diffusers/torch или укажите ключ image API",
        "ctl_export_done": "Экспортировано:",
        "ctl_export_fail": "Ошибка экспорта",
        # ── gpt_client provider labels ──
        "prov_groq": "Groq (быстрый, нужен VPN)",
        "prov_openrouter": "OpenRouter (работает без VPN)",
        "prov_proxy": "Прокси (proxyapi/aitunnel, оплата в рублях)",
        "cat_openrouter_notes": "Доступ к сотням моделей; VPN не нужен; пополнение картой/криптой.",
        "cat_together_notes": "Быстрый инференс открытых моделей; оплата картой.",
        "cat_mistral_notes": "Официальный API Mistral; хостинг в ЕС.",
        "cat_deepinfra_notes": "Дешёвый инференс открытых моделей; простая тарификация.",
        "cat_vsegpt_label": "VseGPT",
        "cat_vsegpt_notes": "Оплата в рублях, широкий каталог моделей, RU-поддержка.",
        "cat_aitunnel_label": "AITunnel",
        "cat_aitunnel_notes": "Оплата в рублях, агрегатор популярных моделей.",
        "cat_proxyapi_label": "ProxyAPI",
        "cat_proxyapi_notes": "Оплата в рублях, стабильный прокси для OpenAI-совместимых API.",
        # ── Dialogs ──
        "dlg_about_title": "О программе AI Studio",
        "dlg_ok": "OK",
        "dlg_cancel": "Отмена",
        "dlg_download_title": "Скачивание модели",
    },
}
