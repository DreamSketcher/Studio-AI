# -*- coding: utf-8 -*-
"""
engine/env_setup.py — тонкий прокси-модуль.

Переэкспортирует установщики и диагностику из ai_studio_core.env_core.*, чтобы GUI
мог делать `from ai_studio_core import env_setup` и вызывать
env_setup.run_full_diagnostics() / run_error_recovery() / install_torch() и т.п.

ВАЖНО: `from module import *` НЕ захватывает имена, начинающиеся с
подчёркивания (если в модуле не задан __all__). Поэтому внутренние
помощники вроде _read_pip_output (используется установщиками TTS/RVC через
env_setup._read_pip_output) нужно переэкспортировать ЯВНО, иначе при
нажатии «Установить TTS» падает
AttributeError: module 'ai_studio_core.env_setup' has no attribute '_read_pip_output'.
"""
from ai_studio_core.env_core.diagnostics import *

# Явная переэкспортируем внутренние помощники с подчёркиванием,
# которые используются установщиками напрямую через env_setup.<имя>.
from ai_studio_core.env_core.llama_setup import *
from ai_studio_core.env_core.rvc_setup import *
from ai_studio_core.env_core.torch_setup import *
