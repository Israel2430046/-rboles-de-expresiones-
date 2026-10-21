#!/usr/bin/env python3
"""Instala la configuración local de OpenCode en el perfil del usuario."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path.home() / ".config" / "opencode"
TARGET_JSON = CONFIG_DIR / "opencode.json"
TARGET_JSONC = CONFIG_DIR / "opencode.jsonc"


def main() -> None:
    if TARGET_JSON.exists() and TARGET_JSONC.exists():
        raise SystemExit("Existen opencode.json y opencode.jsonc globales; unifica primero esos archivos.")

    target = TARGET_JSON if TARGET_JSON.exists() or not TARGET_JSONC.exists() else TARGET_JSONC
    current = {}
    if target.exists():
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SystemExit(f"{target} contiene JSONC con comentarios. Haz la mezcla manual: {error}")

    project_config = json.loads((PROJECT / "opencode.json").read_text(encoding="utf-8"))
    desired = {
        key: project_config[key]
        for key in ("model", "small_model", "default_agent", "provider", "agent", "permission")
    }
    desired["instructions"] = [str(CONFIG_DIR / "LOCAL_WORKFLOW.md")]

    # Mantiene otras configuraciones y otros proveedores ya existentes.
    current.setdefault("$schema", "https://opencode.ai/config.json")
    for key in ("model", "small_model", "default_agent"):
        current[key] = desired[key]
    for key in ("provider", "agent"):
        current.setdefault(key, {}).update(desired[key])
    current.setdefault("permission", {}).setdefault("bash", {}).update(desired["permission"]["bash"])
    instructions = current.setdefault("instructions", [])
    for instruction in desired["instructions"]:
        if instruction not in instructions:
            instructions.append(instruction)

    copies = [(PROJECT / "OPENCODE.md", CONFIG_DIR / "LOCAL_WORKFLOW.md")]
    for kind in ("agents", "skills"):
        source_dir = PROJECT / ".opencode" / kind
        for source in source_dir.rglob("*"):
            if source.is_file():
                copies.append((source, CONFIG_DIR / kind / source.relative_to(source_dir)))

    conflicts = [str(destination) for _, destination in copies if destination.exists()]
    if conflicts:
        raise SystemExit("Ya existen archivos globales con estos nombres:\n" + "\n".join(conflicts))

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if target.exists():
        suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = target.with_name(f"{target.name}.backup-{suffix}")
        shutil.copy2(target, backup)
        print(f"Respaldo: {backup}")

    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    target.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Configuración global: {target}")
    print("Modelos, agentes y skills instalados. Inicia Ollama e importa los GGUF antes de usar OpenCode.")


if __name__ == "__main__":
    main()
