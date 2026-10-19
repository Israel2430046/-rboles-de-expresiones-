# Forma de trabajar en este proyecto

Responde en español salvo que el usuario pida otro idioma. Antes de cambiar código, inspecciona los archivos y los comandos de prueba disponibles. Divide los trabajos grandes en tareas comprobables; implementa una parte, compruébala y continúa. No inventes resultados de pruebas ni capacidades de los modelos.

Los agentes disponibles tienen responsabilidades concretas:

- `@architect` (Llama 3.1): diseño y decisiones técnicas antes de cambios amplios.
- `build` (Llama 3.1): implementación y coordinación de cambios.
- `@reviewer` (Phi-4 mini): revisión de defectos y riesgos, sin editar.
- `@tester` (Llama 3.1): pruebas relevantes y diagnóstico de fallos.
- `@documenter` (Phi-4 mini): documentación y ejemplos de uso.

Usa cada subagente cuando su aporte sea útil para la tarea. En esta máquina, invócalos de manera secuencial para reducir el uso simultáneo de memoria. Si el modelo local no logra llamar herramientas de forma fiable, informa del fallo concreto y reduce el alcance de cada instrucción. Carga las skills pertinentes antes de tareas complejas: `project-planning`, `implementation`, `testing`, `code-review`, `documentation`.

Al terminar, resume archivos cambiados, pruebas ejecutadas y límites conocidos. Pide confirmación antes de publicar, desplegar, borrar datos o ejecutar operaciones irreversibles.
