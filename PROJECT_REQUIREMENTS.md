# Objetivo de esta aplicación

Crear una aplicación local en Python para interpretar expresiones matemáticas como árboles de expresión. El archivo actual `src/grafo.py` es un ejemplo incompleto de `sin(x)`; no representa la aplicación solicitada.

## Requisitos observados en la solicitud del usuario

1. Permitir ingresar una expresión matemática variable, con operaciones comunes y anidamiento.
2. Parsear la expresión de forma segura y construir un árbol de expresión visible.
3. Evaluar y graficar la función para valores reales de la variable, distinguiendo tramos válidos, discontinuidades y valores indefinidos.
4. Soportar resultados complejos, por ejemplo `sqrt(-1)`, y explicar cuándo una gráfica real no corresponde. No representar automáticamente números complejos como puntos de una gráfica real.
5. Tratar divisiones por cero, polos e intervalos no válidos sin bloquear la interfaz ni dibujar líneas engañosas a través de discontinuidades.
6. Mostrar en una interfaz gráfica local hecha con Python la entrada de expresión, el árbol, la gráfica y los intervalos o dominios pertinentes.
7. Separar parser, árbol, evaluación, análisis de dominio, gráfica e interfaz en módulos reutilizables para futuros algoritmos genéticos.

## Criterios para declarar la tarea terminada

- Existe un comando documentado que inicia la interfaz local.
- Se puede ingresar una expresión distinta de `sin(x)` y cambian el árbol y la gráfica.
- Hay comprobaciones para paréntesis, potencias, raíces de negativos y división por cero.
- La interfaz no se congela ni se cierra ante una expresión inválida: muestra un error entendible.
- Los resultados de las pruebas se ejecutaron y se informan con sus comandos.

Si el usuario cambia el alcance, sigue su instrucción más reciente. Las dudas sobre bibliotecas o diseño se pueden resolver con una elección razonable y documentada.
