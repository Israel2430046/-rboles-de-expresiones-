# OpenCode con modelos locales

Esta carpeta configura OpenCode para usar los dos modelos GGUF distintos encontrados en esta máquina. Los archivos duplicados en `taller_crewai/` representan los mismos modelos. La configuración usa Ollama en `127.0.0.1:11434` y no necesita claves de API.

| Modelo | Uso principal | Contexto configurado |
| --- | --- | --- |
| Llama 3.1 8B Q4_K_M | implementación, arquitectura y pruebas | 16 384 tokens |
| Phi-4 mini Q4_K_M | planificación rápida, revisión y documentación | 8 192 tokens |

## Empezar en este proyecto

Desde esta carpeta, ejecuta:

```bash
bash scripts/start-local-opencode.sh
```

El script inicia Ollama si hace falta, importa ambos GGUF si faltan y abre OpenCode. La primera importación puede usar unos 7 GB adicionales de disco. Para preparar los modelos sin abrir OpenCode:

```bash
bash scripts/start-local-opencode.sh --setup-only
```

Después puedes usar `opencode` directamente desde esta carpeta. En OpenCode, `/models` muestra ambos modelos. Pide tareas concretas a `@architect`, `@reviewer`, `@tester` o `@documenter`; `build` es el agente principal. Las instrucciones y skills del proyecto se cargan desde `opencode.json` y `.opencode/`.

## Usarlo en otros proyectos

Una vez comprobado este proyecto, instala una copia global con:

```bash
python3 scripts/install-global.py
```

El instalador conserva otros proveedores y agentes del archivo global, crea un respaldo de la configuración previa y se detiene si ya existen agentes o skills globales con los mismos nombres. Luego ejecuta `opencode` desde cualquier proyecto. Las rutas GGUF de los Modelfiles son específicas de esta máquina; si mueves los archivos, actualízalas y vuelve a crear los modelos con `ollama create`.

## Comprobaciones y límites

```bash
ollama list
opencode models ollama
opencode agent list
opencode debug skill
```

La ejecución de tareas complejas depende de que los modelos locales produzcan llamadas a herramientas correctas. En particular, Phi-4 mini es pequeño; úsalo para revisiones breves y comprueba sus hallazgos. Con 15 GiB de RAM, conviene invocar los subagentes uno tras otro. Si Ollama ya estaba activo, el script usa ese servidor y sus límites de memoria existentes.
