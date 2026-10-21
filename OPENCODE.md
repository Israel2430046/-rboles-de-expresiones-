# Forma de trabajar

Responde en español salvo que el usuario pida otro idioma. La solicitud más reciente del usuario y los requisitos del proyecto determinan el trabajo. No atribuyas al usuario instrucciones que no escribió. Antes de cambiar código, inspecciona los archivos y los comandos de prueba disponibles.

Para tareas amplias, enumera internamente los entregables y comprueba cada uno antes de decir que terminaste. Un ejemplo aislado, una gráfica fija o un script de muestra no cumplen una solicitud de aplicación completa. Implementa por etapas pequeñas, verifica cada etapa y continúa hasta cubrir los requisitos. Si una parte no se puede terminar, explica exactamente qué falta y por qué. No inventes resultados de pruebas ni capacidades de los modelos.

Los agentes disponibles tienen responsabilidades concretas:

- `@architect` (Llama 3.1): diseño y decisiones técnicas antes de cambios amplios.
- `build` (Llama 3.1): implementación y coordinación de cambios.
- `@reviewer` (Phi-4 mini): revisión de defectos y riesgos, sin editar.
- `@tester` (Llama 3.1): pruebas relevantes y diagnóstico de fallos.
- `@documenter` (Phi-4 mini): documentación y ejemplos de uso.

Usa cada subagente solo para su especialidad. `@documenter` redacta documentación después de comprobar el comportamiento; no le delegues código, gráficas ni la lógica principal. En esta máquina, invócalos de manera secuencial para reducir el uso simultáneo de memoria. Si el modelo local no logra llamar herramientas de forma fiable, informa del fallo concreto y reduce el alcance de cada instrucción. Carga las skills pertinentes antes de tareas complejas: `project-planning`, `implementation`, `testing`, `code-review`, `documentation`.

No uses Git por iniciativa propia. Crea commits locales solo cuando el usuario lo solicite; no hagas `push`, configures remotos ni supongas que existe un repositorio en la nube. Si falla un comando, investiga la causa antes de repetirlo con otra forma. Al terminar, resume archivos cambiados, pruebas ejecutadas y requisitos pendientes. Pide confirmación antes de publicar, desplegar, borrar datos o ejecutar operaciones irreversibles.
