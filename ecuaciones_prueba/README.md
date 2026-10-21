# Ecuaciones de prueba

El lote inicial contiene 50 expresiones aleatorias (semilla 2026, altura máxima 6) y 17 casos límite. El TXT se puede leer y copiar directamente en la aplicación. El JSON incluye los árboles aleatorios y sus metadatos para reutilizarlos en pruebas o algoritmos genéticos. Los lotes desde el 20/10/2026 registran además, por expresión, cuántos puntos de `x ∈ [-5, 5]` dan resultado real, complejo, indefinido, indeterminado o desbordamiento (`special_cases`), y el TXT lo anota junto a cada línea.

Genera más archivos con **Guardar lote** en la ventana o con:

```bash
PYTHONPATH=src venv/bin/python -m expresiones.cases --cantidad 50 --altura 6 --semilla 2026
```

Los casos aleatorios pueden tener valores complejos, divisiones entre cero o desbordamientos deliberadamente. No se garantiza que sean funciones reales válidas en todo el intervalo. Los casos límite incluyen una descripción de lo esperado.
