#!/usr/bin/env python3
"""check_plugin_deps.py — валидация манифестов моделей/плагинов в models/.

Формат манифеста (JSON):
{
  "manifest_version": 1,
  "plugin_id": "str",
  "version": "X.Y.Z",
  "display_name": "str",
  "description": "str",
  "kind": "tts" | "rvc" | "llm" | "audio",
  "entrypoint": "dotted.path:callable",
  "compatibility": {"ai_studio_core": ">=X.Y.Z"},
  "requirements": ["pip-pkg-spec", ...],
  "models": [ ... ],
  "sha256": "hex" | null
}

Сценарий пробегает по *.json файлам в models/ и проверяет их на соответствие
схеме. Используется как CI-гейт и как рантайм-проверка при установке плагинов.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

PLUGIN_KINDS = {"tts", "rvc", "llm", "audio"}
REQUIRED_FIELDS = {
    "manifest_version": int,
    "plugin_id": str,
    "version": str,
    "display_name": str,
    "description": str,
    "kind": str,
    "entrypoint": str,
    "compatibility": dict,
    "requirements": list,
}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-.+][\w.+-]+)?$")
SEMVER_SPEC_RE = re.compile(r"^(?:>=|<=|==|~=|>|<|!=)?\s*\d+(\.\d+){0,2}(?:\.\*)?$")
ENTRYPOINT_RE = re.compile(r"^[a-zA-Z_][\w.]*(?::[a-zA-Z_]\w*)?$")
PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")


def _validate_version(v: str, label: str, errors: list[str]) -> None:
    if not VERSION_RE.match(v):
        errors.append(f"{label}: неверный формат версии '{v}' (ожидается X.Y.Z)")


def _validate_manifest(path: Path, data: Any) -> list[str]:
    errs: list[str] = []
    if not isinstance(data, dict):
        return [f"{path}: манифест должен быть JSON-объектом"]

    for fname, ftype in REQUIRED_FIELDS.items():
        if fname not in data:
            errs.append(f"{path}: отсутствует обязательное поле '{fname}'")
        elif not isinstance(data[fname], ftype):
            errs.append(f"{path}: поле '{fname}' должно быть {ftype.__name__}")

    if "plugin_id" in data and isinstance(data["plugin_id"], str):
        if not PLUGIN_ID_RE.match(data["plugin_id"]):
            errs.append(f"{path}: plugin_id '{data['plugin_id']}' имеет неверный формат (должен быть dot-separated lowercase)")

    if "version" in data and isinstance(data["version"], str):
        _validate_version(data["version"], f"{path}: version", errs)

    if "kind" in data and isinstance(data["kind"], str):
        if data["kind"] not in PLUGIN_KINDS:
            errs.append(f"{path}: kind '{data['kind']}' не поддерживается (допустимы {sorted(PLUGIN_KINDS)})")

    if "entrypoint" in data and isinstance(data["entrypoint"], str):
        if not ENTRYPOINT_RE.match(data["entrypoint"]):
            errs.append(f"{path}: entrypoint '{data['entrypoint']}' имеет неверный формат")

    if "compatibility" in data and isinstance(data["compatibility"], dict):
        core = data["compatibility"].get("ai_studio_core")
        if not core:
            errs.append(f"{path}: compatibility.ai_studio_core обязателен")
        elif isinstance(core, str) and not SEMVER_SPEC_RE.match(core.replace(" ", "")):
            errs.append(f"{path}: compatibility.ai_studio_core '{core}' не похож на semver-спецификацию")

    if "requirements" in data and isinstance(data["requirements"], list):
        for i, req in enumerate(data["requirements"]):
            if not isinstance(req, str):
                errs.append(f"{path}: requirements[{i}] должен быть строкой")

    if "sha256" in data and data["sha256"] is not None:
        if not (isinstance(data["sha256"], str) and re.fullmatch(r"[0-9a-fA-F]{64}", data["sha256"])):
            errs.append(f"{path}: sha256 должен быть 64-символьной hex-строкой или null")

    if "models" in data and isinstance(data["models"], list):
        # Дальнейшую структурную проверку вложенных моделей пока не делаем
        pass

    return errs


def iter_manifests(root: Path) -> Iterable[Path]:
    models_dir = root / "models"
    if not models_dir.is_dir():
        return []
    return sorted(models_dir.glob("*.json"))


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    manifests = list(iter_manifests(repo_root))
    if not manifests:
        print("[check_plugin_deps] WARN: в models/ нет ни одного манифеста (.json)")
        # Не падаем — на ранней стадии проекта допустимо, но предупреждаем.
        return 0

    all_errors: list[str] = []
    for m in manifests:
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            all_errors.append(f"{m}: невалидный JSON: {e}")
            continue
        all_errors.extend(_validate_manifest(m, data))

    if all_errors:
        print("[check_plugin_deps] FAIL: обнаружены ошибки в манифестах плагинов:", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"[check_plugin_deps] OK: проверено {len(manifests)} манифест(а/ов), ошибок нет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
