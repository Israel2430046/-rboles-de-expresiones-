# Laboratorio de árboles de expresión

Aplicación local en Python con editor de expresiones, árbol de operaciones,
gráfica, evaluación compleja y solución de ecuaciones en reales o complejos.
Incluye controles de intervalo, paso y altura máxima; catálogo de operadores;
generación de pruebas; y módulos de mutación, cruce y fitness para algoritmos genéticos.

Inicia la ventana desde esta carpeta (dependencias instaladas en `venv/`):

```bash
venv/bin/python main.py
```

Consulta [instalación, uso, convenciones matemáticas y API](docs/APLICACION.md).
Los ejemplos generados están en [ecuaciones_prueba/](ecuaciones_prueba/).

Pruebas del motor:

```bash
PYTHONPATH=src venv/bin/python -m unittest discover -s tests -v
```

Prueba de la ventana, que requiere una sesión gráfica:

```bash
venv/bin/python scripts/check_gui.py
```

## OpenCode con modelos locales

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

Los requisitos de la aplicación de árboles de expresión están en `PROJECT_REQUIREMENTS.md`. El archivo `src/grafo.py` ahora inicia la aplicación modular de `src/expresiones/`. La configuración pide verificar cada entregable y restringe a `@documenter` a documentación. Los comandos de Git que crean repositorio, preparan cambios o hacen commits requieren aprobación; `git push` y la creación de remotos están bloqueados. Cierra y vuelve a abrir OpenCode para que lea estos cambios.

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
