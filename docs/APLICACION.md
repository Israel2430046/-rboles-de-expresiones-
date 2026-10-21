# Laboratorio de árboles de expresión

Aplicación de escritorio escrita en Python con Tkinter, Matplotlib y SymPy. Permite editar expresiones de una variable, ver su árbol, evaluar números complejos, graficar y resolver igualdades.

## Instalación e inicio

Python 3.11 o posterior, con Tkinter disponible. En este proyecto las dependencias ya se instalaron en `venv/`.

```bash
venv/bin/python main.py
```

También funciona `venv/bin/python src/grafo.py`. Para preparar otro equipo:

```bash
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python main.py
```

En Debian/Ubuntu, si Python no incluye Tkinter o venv, instala los paquetes del sistema `python3-tk` y `python3-venv`. La aplicación requiere una sesión gráfica local; el motor y las pruebas matemáticas funcionan sin pantalla.

## Uso

1. Escribe `sin(x)+x/3`, `sqrt(x)`, `1/x`, `exp(i*x)` u otra expresión del catálogo.
2. Ajusta inicio, fin, paso y altura máxima. Pulsa **Analizar y graficar** o Enter.
3. El panel izquierdo muestra los operadores y sus hijos. Usa las barras de desplazamiento para árboles grandes. La gráfica incluye zoom, desplazamiento y guardado de imagen.
4. Elige **Solo reales** o **Real e imaginaria**. La segunda vista representa ambas componentes frente a una variable real; no es un mapa del plano complejo.
5. Revisa **Muestras y estados** para consultar cada punto y exportar un CSV. **Evaluar punto** admite constantes reales y complejas, como `pi`, `2` o `1+i`.
6. Para una ecuación, escribe `x^2+1=0` y selecciona soluciones reales o complejas antes de analizar. La gráfica muestra izquierda menos derecha; sus ceros representan soluciones válidas.
7. En **Biblioteca de operadores**, selecciona cuáles puede usar el generador. **Árbol aleatorio** crea una expresión que respeta la altura; **Guardar lote** escribe archivos independientes en `ecuaciones_prueba/`.
8. **Exportar árbol** y **Importar árbol** guardan y recuperan la estructura en JSON. El JSON de un lote tiene otro formato, con múltiples casos.

Los cambios de intervalo, altura o dominio se aplican al pulsar **Analizar y graficar**. La selección de vista actualiza la gráfica disponible inmediatamente. Si una entrada nueva es inválida, se indica el error y se conserva el último resultado válido con su título original.

## Sintaxis y biblioteca

Se admite la variable `x`, números enteros/decimales/notación científica y las constantes `pi`, `e`, `i`. También funcionan `π`, `j`, `ln` como alias de `log` y `sen` como alias de `sin`.

| Operadores | Ejemplo | Convención |
| --- | --- | --- |
| `+ - * /` | `(x+1)/(x-2)` | Multiplicación explícita: `2*x` |
| `^` o `**` | `x^2`, `x^(1/3)` | Potencia compleja principal |
| `%` | `x%3` | Resto solo de números reales |
| `sin cos tan` | `sin(pi/2)` | Ángulos en radianes |
| `asin acos atan` | `acos(x)` | Ramas principales |
| `sinh cosh tanh` | `tanh(x)` | Funciones hiperbólicas |
| `sqrt cbrt` | `sqrt(-4)`, `cbrt(-8)` | Cuadrada principal; cúbica real para argumentos reales |
| `log log10 exp` | `log(x)`, `exp(i*x)` | `log` es natural; logaritmos complejos principales |
| `abs re im conj` | `abs(3+4*i)` | Módulo, partes real/imaginaria y conjugado |
| `=` | `x/x=1` | Una igualdad de una variable |

No se admiten multiplicación implícita (`2x`), múltiples variables, desigualdades, sistemas de ecuaciones, código Python ni funciones fuera del catálogo. Las funciones reciben un argumento. Para logaritmos de otra base se puede escribir `log(x)/log(2)`.

## Casos matemáticos especiales

| Entrada | Resultado o interpretación |
| --- | --- |
| `sqrt(-4)` | `2i` |
| `cbrt(-8)` | `-2`; `(-8)^(1/3)` usa la rama compleja principal |
| `1/0` | Indefinido; no se representa como un número infinito |
| `0/0`, `0^0` | Indeterminado por la convención del intérprete |
| `log(0)` | Indefinido |
| `exp(1000)` | Desbordamiento numérico; no demuestra infinito matemático |
| `x/x=1` | Infinitas soluciones, excluyendo cero |
| `0*(1/x)=0` | Conserva también la exclusión de cero |
| `x+1=x` | Sin soluciones |
| `x^2+1=0` | Sin soluciones reales; `{-i,i}` en complejos |
| `sin(x)=0` | Infinitas soluciones periódicas |
| `0^x=0` | Soluciones reales `x>0` |

Las operaciones indefinidas de los subárboles no se borran al simplificar. Una división entre cero y una ecuación con infinitas soluciones son situaciones distintas. Un valor indeterminado tampoco significa que se hayan calculado infinitas soluciones. El análisis calcula los límites laterales en cada singularidad del intervalo (hasta 8) y los clasifica como discontinuidad evitable (por ejemplo `sin(x)/x → 1` en `x=0`), asíntota vertical, salto finito, oscilación o frontera del dominio real; también informa el comportamiento cuando `x → ±∞` y avisa si la expresión es constante.

SymPy expresa los conjuntos con nombres como `EmptySet` (vacío), `Reals`, `Interval`, `Union`, `ImageSet` (familia parametrizada) y `ConditionSet` (condición aún no resuelta). Las soluciones se buscan en todo ℝ o ℂ; el intervalo solo restringe la gráfica y el dominio mostrado. El análisis simbólico no resuelve todas las expresiones: si falla, se cancela o vence el tiempo, la interfaz lo comunica. El solver complejo no admite la convención por tramos de `cbrt`; para ese análisis utiliza potencias.

Referencia del solucionador: [documentación oficial de SymPy: solveset](https://docs.sympy.org/latest/modules/solvers/solveset.html). El adaptador construye objetos SymPy desde nodos validados; no envía cadenas del usuario a `sympify`, `eval` o `parse_expr`.

## Interfaz

- **Árbol y gráfica** se muestran juntos en la primera pestaña; «Mostrar» elige ambos o uno solo y la división central se arrastra. Cada nodo indica el valor de su subárbol en el punto `x` elegido; el borde señala complejo (morado), indefinido (rojo), indeterminado (naranja) o desbordamiento (ámbar). Un clic sobre un nodo resalta su subárbol y muestra su expresión, altura, nodos y valor.
- Bajo el campo `f(x)` hay un teclado de operadores y funciones que inserta en la posición del cursor.
- La **altura máxima** se ajusta con el selector numérico o con el deslizador; el texto inferior avisa si el árbol actual la supera.
- La línea roja bajo las métricas resume los casos especiales detectados: singularidades simbólicas y tramos complejos, indefinidos o indeterminados de las muestras. La pestaña **Análisis** los detalla junto con el dominio, las soluciones y los límites.
- **Operadores** muestra la biblioteca completa con su tipo (unario o binario) y permite elegir todos, ninguno o los predeterminados para generar, mutar y cruzar.
- **Mutar f(x)** y **Cruzar f × g** aplican los operadores genéticos del módulo `genetics` respetando la altura máxima.
- **Ventana:** abre ocupando toda la pantalla. En niri y otros compositores en mosaico (vía Xwayland), Tk ignora `-fullscreen`; por eso la aplicación fija la geometría al tamaño de la pantalla. F11 alterna con una ventana del 75 %.
- **Vistas:** `2D` (con un recuadro de MSC/MSE, RMSE y NMSE cuando hay g(x)), `3D curva` (x, Re f, Im f) y `3D superficie`: |f(a+bi)| sobre el plano complejo, coloreada por la fase, donde los polos son picos y los ceros, valles. La altura se recorta en el percentil 95.
- **CSV por función:** los botones «CSV de f(x)» y «CSV de g(x)» están junto a la gráfica, en Datos / CSV y en Métricas. El CSV de f(x) incluye, punto por punto, g(x), el error cuadrático y las métricas MSC/MSE = (1/n) Σ |f−g|², RMSE = √MSE y NMSE = MSE / Var(g).

## Ajuste de puntos de un CSV

La pestaña **Ajuste CSV** busca árboles cuya curva pase cerca de los puntos (xᵢ, yᵢ). La programación genética es el método predeterminado.

1. **Datos:** «Cargar CSV…» (columnas `x,y`; también `;` con coma decimal, sin cabecera o el CSV exportado por la aplicación con `x,real`), un archivo **precargado** de `datos_csv/`, «CSV aleatorio» o «CSV función de prueba». Este último genera `6.87 + 11*cos(7.23*x^3)` sin ruido.
2. **Búsqueda:** cada candidato es un árbol con los operadores marcados y la altura máxima. El método genético crea una población, selecciona padres, cruza y muta árboles; la búsqueda aleatoria opcional genera cada árbol de forma independiente. Para cada xᵢ se calcula **ŷᵢ = f(xᵢ)** y su error **MSE = (1/n) Σ (yᵢ − ŷᵢ)²**, más RMSE = √MSE y NMSE = MSE / Var(y). Los candidatos con algún ŷ complejo, indefinido o desbordado reciben aptitud infinita en el método genético.
3. **Resultados:** la gráfica muestra los puntos y, la curva ŷ de la mejor ecuación (o la seleccionada en la tabla), los residuos yᵢ − ŷᵢ y el candidato que se prueba en ese momento. La curva respeta los cortes detectados en discontinuidades. Abajo aparece la convergencia del mejor MSE. «Usar como f(x)» la lleva al analizador; «CSV de x, y, ŷ» exporta `x, y, y_gorro, error, error_cuadrado, ecuacion, MSC_MSE, RMSE, NMSE`.

La búsqueda avanza por lotes sin bloquear la ventana y se puede detener. Repetir «Evolucionar» continúa desde el estado actual; cambiar los operadores o la altura la reinicia. No garantiza encontrar la función original.

```bash
PYTHONPATH=src venv/bin/python -m expresiones.regression   # regenera datos_csv/
```

## Programación genética (método por defecto de «Ajuste CSV»)

| Concepto | En este programa |
| --- | --- |
| Individuo | Un solo gen: su árbol de expresión |
| Genotipo | El árbol: nodos internos = operadores, hojas = operandos (x, enteros, pi, e) |
| Fenotipo | La ecuación ŷ = f(x) que expresa el árbol |
| Aptitud | MSE = (1/n) Σ (yᵢ − ŷᵢ)²; menor es mejor. Un ŷ complejo o indefinido da aptitud infinita |

**Paso 1 · Población inicial.** 100 árboles aleatorios (configurable), con alturas escalonadas de 2 a la altura máxima. Si se habilitan los operadores necesarios, parte de la población explora árboles trigonométricos con potencias de `x` y constantes aleatorias.

**Paso 2 · Evaluación.** Cada individuo se evalúa en todos los puntos del CSV.

**Paso 3 · Nueva generación.**
- *Élite:* los mejores (2 por defecto) pasan sin cambios, así el mejor error nunca empeora.
- *Selección:* la población se ordena por MSE y el corte de selección toma su mitad izquierda (los mejores). La ruleta por rango es el método predeterminado; el torneo de `k` individuos es opcional. La selección no modifica los padres.
- *Cruza (90 %):* en cada pareja, el padre de menor error es el **dominante** y el otro el **recesivo**. Se corta una rama de cada uno en un punto aleatorio (el 90 % de las veces un operador y el 10 % una hoja) y se intercambian. El **hijo** es el dominante con la rama del recesivo; el **recíproco**, el recesivo con la rama del dominante. Los cortes solo se aceptan si ambos hijos caben en la altura máxima.
- *Mutación (50 % en el motor; configurable en la interfaz):* se pueden activar los cuatro tipos:
  - **Subárbol:** reemplaza una rama por otra aleatoria.
  - **Hoja:** cambia una hoja o altera el valor de una constante. Es la única forma de afinar constantes.
  - **Operador:** cambia un operador por otro de la misma aridad.
  - **Intercambio (switch):** en un operador binario invierte los hijos izquierdo y derecho (`x − 3 → 3 − x`). Prefiere `−`, `/`, `^` y `%`, donde el cambio altera el resultado. En las funciones de un argumento el único hijo es siempre el izquierdo, por eso no se intercambian.
- *Diversidad:* los árboles con la misma expresión cuentan una sola vez. Cada generación entra un 10 % de **inmigrantes** aleatorios y, si el error no mejora durante 60 generaciones, se conserva la élite y se reinicia el resto.
- *Aleatoriedad:* el campo «Semilla» de la pestaña está vacío por defecto, así que cada ejecución es distinta. La semilla usada aparece en el estado; escríbela para repetir exactamente una ejecución.
- *Acercamiento al resultado:* el árbol se evalúa directamente. No hay regresión lineal ni ajuste de parámetros externo a la evolución.

La interfaz muestra la generación, los individuos válidos y distintos, las cruzas y mutaciones de cada tipo, la última cruza (dominante × recesivo → hijo y recíproco), el origen de cada ecuación, la curva ŷ sobre los puntos y la convergencia. «Evolucionar» de nuevo continúa con la misma población; cambiar algún parámetro la reinicia.

```python
from expresiones.regression import load_points
from expresiones.gp import GeneticProgramming

xs, ys, _ = load_points("datos_csv/objetivo_coseno.csv")
gp = GeneticProgramming(xs, ys, ("+", "-", "*", "/", "**", "sin", "cos"), max_height=6,
                        population_size=100, seed=1, stagnation=100)
best = gp.run(60)
print(best.expression, best.mse)
```

## Límites y precisión

- Una hoja tiene altura 1. Una función agrega un nivel; un operador binario agrega un nivel sobre su hijo más alto. En ecuaciones, `=` cuenta como raíz. Se aceptan alturas de 1 a 12 y como máximo 255 nodos.
- Máximo 4000 caracteres y constantes literales de magnitud hasta `1e100`.
- Inicio y fin finitos, inicio menor que fin y paso positivo. Máximo 5000 muestras. Se incluye el extremo final aunque el último segmento sea más corto.
- Evaluación con números complejos de precisión de máquina. Se conserva cualquier parte imaginaria distinta de cero; el redondeo puede dejar residuos imaginarios pequeños. La tangente trata `abs(cos(z))<1e-14` como un polo.
- Si un eje supera `1e150`, la gráfica aplica un factor indicado en su etiqueta para evitar desbordamientos al dibujar. La tabla y el CSV conservan los valores originales.
- La gráfica corta singularidades encontradas simbólicamente y saltos detectados por denominadores, puntos medios y cambios de curvatura. El muestreo no garantiza encontrar todas las discontinuidades u oscilaciones; reduce el paso para investigar.
- El dominio mostrado corresponde al análisis simbólico real en el intervalo y puede ser inconcluyente. Se conserva la información numérica de cada muestra.
- El cálculo se ejecuta en otro proceso con cancelación y un límite de 15 segundos. En Linux también se limita la memoria virtual adicional del proceso a 512 MiB. Al interrumpir el análisis se conservan las muestras ya recibidas.

## Generar lotes desde la terminal

```bash
PYTHONPATH=src venv/bin/python -m expresiones.cases \
  --cantidad 50 --altura 6 --semilla 2026 --directorio ecuaciones_prueba
```

Cada lote tiene un TXT legible y un JSON con semilla, operadores, altura, número de nodos, árboles serializados y `special_cases`: el conteo de estados (real, complejo, indefinido, indeterminado, desbordamiento) de cada expresión en `x ∈ [-5, 5]` con paso 0.25. Contiene expresiones aleatorias y casos límite conocidos que caben en la altura elegida. Los casos límite pueden usar operadores distintos de la selección aleatoria. Se admiten hasta 500 expresiones aleatorias por lote. No se sobrescriben lotes previos.

## API para algoritmos genéticos

El motor funciona sin importar Tkinter. Añade `src/` a `PYTHONPATH` o instala su ruta en tu aplicación.

```python
from expresiones import Node, parse, evaluate
from expresiones.genetics import TreeFactory, mean_squared_error

expression = parse("x^2 + 1", max_height=6)
tree = expression.left
print(evaluate(tree, x=2).display())  # 5

factory = TreeFactory(operators=("+", "-", "*", "sin"), seed=42)
individual = factory.generate(max_height=6)
mutated = factory.mutate(individual, max_height=6)
child_a, child_b = factory.crossover(individual, mutated, max_height=6)
fitness = mean_squared_error(child_a, [0, 1, 2], [1, 2, 5])

restored = Node.from_dict(tree.to_dict())
for path, subtree in restored.walk():
    print(path, subtree.value)
replaced = restored.replace((0,), Node("variable", "x"), max_height=6)
```

Los nodos son inmutables. Mutación y cruce respetan altura y número de nodos; si no encuentran un reemplazo válido tras sus intentos, devuelven los padres originales. La generación es reproducible con semilla. El fitness real penaliza resultados complejos o indefinidos con `invalid_penalty` (por defecto `1e12`). El ciclo evolutivo completo está en `gp.py`.

| Módulo | Responsabilidad |
| --- | --- |
| `tree.py` | Nodos, rutas, serialización, reemplazos y límites |
| `operators.py` | Catálogo compartido de operadores y constantes |
| `parser.py` | Parser AST con lista permitida y ecuaciones |
| `evaluation.py` | Evaluación compleja, clasificación de resultados y valores por nodo |
| `sampling.py` | Intervalos, muestreo, cortes y rejilla compleja |
| `symbolic.py` | Dominio, restricciones, soluciones y límites con SymPy |
| `genetics.py` | Generación, mutación, cruce y fitness |
| `gp.py` | Programación genética: población jerárquica, ruleta, torneo, elitismo, cruza y 4 mutaciones |
| `regression.py` | Lectura de CSV de puntos, búsqueda aleatoria de ecuaciones, ŷ y exportación |
| `cases.py` | Lotes de pruebas en JSON y TXT |
| `plotting.py` | Gráficas 2D, curva 3D y superficie compleja 3D |
| `jobs.py` | Trabajo aislado en proceso cancelable |
| `gui.py` | Ventana Tkinter |

## Verificación

```bash
PYTHONPATH=src MPLCONFIGDIR=/tmp/arbol-mpl venv/bin/python -m unittest discover -s tests -v
venv/bin/python scripts/check_gui.py
```

El primer comando prueba parser, evaluación, dominios, soluciones, muestreo, serialización y operadores genéticos. El segundo abre una ventana temporal y comprueba cambios de expresión y gráfica, números complejos, exportación/importación, errores de entrada, altura, cancelación, límites, estados por nodo, vista combinada, teclado, deslizador de altura, mutación y cruce; requiere una sesión gráfica. No se ejecuta automáticamente al importar el motor.
