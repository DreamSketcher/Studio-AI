#!/bin/sh
# Форматирование/проверка стиля проекта (Black + Ruff, line-length 100).
#   tools/format.sh         -- авто-правка
#   tools/format.sh --check -- только проверка (для CI)
cd "$(dirname "$0")/.." && exec python3 tools/format_code.py "$@"
