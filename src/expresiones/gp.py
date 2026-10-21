"""Programación genética de árboles de expresión para puntos (x, y).

Vocabulario usado en el código y en la interfaz:

- Individuo: tiene un solo gen, su árbol de expresión (genotipo). Los nodos
  internos son operadores y las hojas son operandos (x, números, pi, e).
- Fenotipo: la ecuación que expresa exactamente el árbol, ŷ = f(x).
- Aptitud (fitness): el error MSE = (1/n) Σ (yᵢ − ŷᵢ)²; menor es mejor. Un ŷ
  complejo, indefinido o desbordado da aptitud infinita.

Ciclo en tres pasos:
  1. población inicial de N árboles aleatorios (por defecto 100), con alturas
     escalonadas de 2 a la altura máxima («ramped»);
  2. evaluación de la población;
  3. nueva generación: selección por ruleta o torneo (no cambia a los individuos),
     cruza de subárboles y mutación. La altura máxima se respeta siempre.

Cruza: en cada pareja el padre de menor error es el «dominante» y el otro el
«recesivo». Se corta un subárbol de cada uno en un punto aleatorio (90 % de
las veces un operador, 10 % una hoja, como propone Koza) y se intercambian:
  hijo      = dominante con el subárbol del recesivo,
  recíproco = recesivo con el subárbol del dominante.

Mutaciones (cuatro tipos):
  - «subarbol»:    reemplaza un subárbol por otro aleatorio.
  - «hoja»:       cambia una hoja por otra o altera su valor numérico.
  - «operador»:   cambia un operador por otro de la misma aridad.
  - «intercambio»: método switch; en un operador binario cambia el hijo
                   izquierdo por el derecho (x − 3 → 3 − x). Prefiere operadores
                   no conmutativos, donde el cambio sí altera el resultado.
En las funciones de un argumento el único hijo es siempre el izquierdo
(índice 0); por eso el intercambio solo actúa sobre operadores binarios.

Diversidad (para que la población no se llene de variantes de una ecuación):
  - se eliminan árboles con la misma expresión;
  - cada generación entra un porcentaje de inmigrantes totalmente aleatorios;
  - si el mejor error no mejora en `stagnation` generaciones, se conserva la
    élite y se reinicia el resto de la población;
  - las constantes son decimales aleatorios, no solo enteros, y sin semilla
    explícita cada ejecución es distinta (la semilla usada queda en `seed`).
El ajuste de constantes procede únicamente de la mutación de hojas.
"""
from dataclasses import dataclass
import math
import random
from .evaluation import evaluate
from .genetics import TreeFactory
from .operators import OPERATORS
from .tree import Node, validate_size

MUTATIONS = {
    "subarbol": "Subárbol: reemplaza una rama por otra aleatoria",
    "hoja": "Hoja: cambia x o una constante",
    "operador": "Operador: cambia un operador por otro de la misma aridad",
    "intercambio": "Intercambio (switch): invierte los hijos izquierdo y derecho",
}
DEFAULT_MUTATIONS = tuple(MUTATIONS)
NON_COMMUTATIVE = ("-", "/", "**", "%")
MAX_PREDICTION = 1e12


class _Factory(TreeFactory):
    """Hojas más variadas: x, decimales aleatorios en [-5, 5], enteros 1-9 o constantes."""

    def leaf(self):
        draw = self.random.random()
        if draw < 0.5:
            return Node("variable", "x")
        if draw < 0.75:
            return Node("number", round(self.random.uniform(-12, 12), 3))
        if draw < 0.9 or not self.constants:
            return Node("number", self.random.randint(1, 9))
        return Node("constant", self.random.choice(self.constants))


@dataclass
class Individual:
    tree: Node                 # genotipo: el gen único del individuo
    mse: float = math.inf      # aptitud; menor es mejor
    generation: int = 0        # generación en la que apareció
    origin: str = "inicial"    # inicial, élite, cruza, recíproco, copia, inmigrante, reinicio (+ mutación)
    signature: str | None = None  # identidad del árbol

    @property
    def model(self):
        """El fenotipo es exactamente el árbol evolucionado."""
        return self.tree

    @property
    def expression(self):      # fenotipo
        return self.model.to_expression()

    @property
    def gene(self):            # genotipo como texto
        return self.tree.to_expression()

    @property
    def iteration(self):       # compatible con la tabla de la búsqueda aleatoria
        return self.generation

    @property
    def valid(self):
        return math.isfinite(self.mse)


@dataclass(frozen=True)
class GenerationStats:
    generation: int
    best: float
    mean: float                # media del MSE de los individuos válidos
    median: float              # mediana del MSE de los válidos (no la dominan los atípicos)
    valid: int
    unique: int                # expresiones distintas en la población


@dataclass(frozen=True)
class CrossoverRecord:
    dominant: str
    recessive: str
    child: str
    reciprocal: str


class GeneticProgramming:
    def __init__(self, xs, ys, operators, max_height=5, population_size=100, tournament=3, crossover_rate=0.9,
                 mutation_rate=0.5, mutations=DEFAULT_MUTATIONS, elitism=2, seed=None, constants=("pi", "e"),
                 immigrants=0.1, stagnation=60, selection="ruleta", cutoff=0.5):
        if len(xs) != len(ys) or len(xs) < 2:
            raise ValueError("Se necesitan al menos 2 puntos con x e y.")
        if not all(math.isfinite(x) and math.isfinite(y) for x, y in zip(xs, ys)):
            raise ValueError("Los puntos deben ser reales y finitos.")
        validate_size(Node("variable", "x"), max_height)
        if max_height < 2:
            raise ValueError("La programación genética necesita una altura máxima de al menos 2.")
        if type(population_size) is not int or not 4 <= population_size <= 5000:
            raise ValueError("La población debe tener entre 4 y 5000 individuos.")
        if type(tournament) is not int or not 2 <= tournament <= population_size:
            raise ValueError("El torneo debe tener entre 2 individuos y el tamaño de la población.")
        if not (0 <= crossover_rate <= 1 and 0 <= mutation_rate <= 1 and 0 <= immigrants < 1):
            raise ValueError("Las probabilidades de cruza, mutación e inmigrantes van de 0 a 1.")
        mutations = tuple(dict.fromkeys(mutations))
        if any(m not in MUTATIONS for m in mutations):
            raise ValueError(f"Mutaciones válidas: {', '.join(MUTATIONS)}.")
        if not mutations:
            raise ValueError("Elige al menos un tipo de mutación.")
        if selection not in ("ruleta", "torneo") or not 0 < cutoff <= 1:
            raise ValueError("Usa selección ruleta o torneo y un corte entre 0 y 1.")
        if type(elitism) is not int or not 0 <= elitism < population_size:
            raise ValueError("La élite debe ser menor que la población.")
        if type(stagnation) is not int or stagnation < 1:
            raise ValueError("El límite de estancamiento debe ser un entero positivo.")
        # Sin semilla, cada ejecución es distinta; la usada se guarda para poder repetirla.
        self.seed = seed if seed is not None else random.SystemRandom().randrange(10**9)
        self.xs, self.ys = list(xs), list(ys)
        self.factory = _Factory(operators, self.seed, constants)
        self.random = self.factory.random
        self.max_height = max_height
        self.population_size = population_size
        self.tournament = tournament
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.mutations = mutations
        self.elitism = elitism
        self.selection = selection
        self.cutoff = cutoff
        self.immigrants = immigrants
        self.stagnation = stagnation
        self.generation = 0
        self.population = []
        self.history = []
        self.best = None                       # mejor individuo de toda la ejecución
        self.last_crossover = None
        self.mutation_counts = {name: 0 for name in mutations}
        self.crossovers = 0
        self.restarts = 0
        self.duplicates = 0                    # hijos rechazados por repetir la expresión
        self.last_improvement = 0
        self.cache = {}
        self.mean_y = sum(self.ys) / len(self.ys)
        self.variance = sum((y - self.mean_y) ** 2 for y in self.ys) / len(self.ys)

    # Paso 1 ------------------------------------------------------------
    def _random_tree(self, index=None):
        # Esta familia es una ecuación aleatoria del mismo lenguaje de árboles.
        # Permite explorar fases no lineales sin ajustar parámetros externamente.
        if self.max_height >= 6 and {"+", "*", "**", "cos"}.issubset(self.factory.operators) and self.random.random() < 0.3:
            r = self.random
            power = Node("operator", "**", (Node("variable", "x"), Node("number", r.choice((2, 3, 4)))))
            phase = Node("operator", "*", (Node("number", round(r.uniform(0.2, 12), 3)), power))
            function = r.choice(("sin", "cos")) if "sin" in self.factory.operators else "cos"
            wave = Node("operator", function, (phase,))
            amplitude = Node("operator", "*", (Node("number", round(r.uniform(-15, 15), 3)), wave))
            return Node("operator", "+", (Node("number", round(r.uniform(-12, 12), 3)), amplitude))
        heights = range(2, self.max_height + 1)
        height = heights[index % len(heights)] if index is not None else self.random.choice(heights)
        return self.factory.generate(height)

    def initialize(self):
        """Población inicial con alturas escalonadas («ramped») y formas de curva distintas."""
        population, index = [], {}
        attempts = 0
        while len(population) < self.population_size and attempts < self.population_size * 20:
            attempts += 1
            self._add(population, index, self._random_tree(len(population)), "inicial", retries=0)
        while len(population) < self.population_size:
            population.append(self._make(self._random_tree(), "inicial"))
        self.population = population
        self._record()
        return self.population

    # Paso 2 ------------------------------------------------------------
    def _measure(self, tree):
        """MSE del árbol completo; infinito para cualquier predicción inválida."""
        key = tree.to_expression()
        if key in self.cache:
            return self.cache[key]
        predictions = []
        for x in self.xs:
            result = evaluate(tree, x)
            if not result.finite or result.value.imag != 0 or abs(result.value.real) > MAX_PREDICTION:
                predictions = None
                break
            predictions.append(result.value.real)
        if predictions is None:
            measured = math.inf
        else:
            mse = sum((y - p) ** 2 for p, y in zip(predictions, self.ys)) / len(predictions)
            measured = mse if math.isfinite(mse) else math.inf
        if len(self.cache) > 50_000:
            self.cache.clear()
        self.cache[key] = measured
        return measured

    def fitness(self, tree):
        return self._measure(tree)

    def _make(self, tree, origin):
        return Individual(tree, self._measure(tree), self.generation, origin, tree.to_expression())

    def evaluate(self, individuals=None):
        for individual in individuals if individuals is not None else self.population:
            individual.mse = self._measure(individual.tree)
            individual.signature = individual.tree.to_expression()
        self._record()

    def _record(self):
        ranked = self.ranking()
        if ranked and (self.best is None or ranked[0].mse < self.best.mse):
            leader = ranked[0]
            # Solo una mejora real (≥ 0.5 %) cuenta como progreso; los retoques mínimos de
            # constantes no deben impedir el reinicio por estancamiento.
            if self.best is None or leader.mse < self.best.mse * 0.995:
                self.last_improvement = self.generation
            self.best = Individual(leader.tree, leader.mse, leader.generation, leader.origin, leader.signature)
        self.population.sort(key=lambda i: (i.mse, i.tree.size, i.expression))
        valid = sorted(i.mse for i in self.population if i.valid)
        self.history.append(GenerationStats(self.generation, self.best.mse if self.best else math.inf,
                                            sum(valid) / len(valid) if valid else math.inf,
                                            valid[len(valid) // 2] if valid else math.inf, len(valid),
                                            len({i.signature for i in self.population})))

    def ranking(self, limit=None, unique=True):
        """Individuos ordenados por error (y por tamaño en caso de empate); únicos por forma de curva."""
        ordered = sorted(self.population, key=lambda i: (i.mse, i.tree.size))
        if unique:
            seen, out = set(), []
            for individual in ordered:
                key = individual.signature or individual.expression
                if key not in seen:
                    seen.add(key)
                    out.append(individual)
            ordered = out
        return ordered[:limit] if limit else ordered

    def diverse_ranking(self, limit=10, min_distance=0.15):
        """Primeros individuos con expresiones diferentes, por menor MSE."""
        return self.ranking(limit)

    # Paso 3 ------------------------------------------------------------
    def select(self):
        """Corte izquierdo de la jerarquía y ruleta por rango o torneo."""
        if not self.population:
            raise ValueError("Inicializa la población antes de seleccionar.")
        pool = self.population[:max(2, math.ceil(len(self.population) * self.cutoff))]
        if self.selection == "torneo":
            contestants = [self.random.choice(pool) for _ in range(self.tournament)]
            return min(contestants, key=lambda i: (i.mse, i.tree.size))
        # La ruleta por rango funciona incluso con aptitudes infinitas.
        weights = [1 / (rank + 1) for rank in range(len(pool))]
        return self.random.choices(pool, weights=weights, k=1)[0]

    def _paths(self, tree, max_subtree_height=None, prefer_operators=True):
        paths = [(path, node) for path, node in tree.walk()
                 if max_subtree_height is None or node.height <= max_subtree_height]
        operators = [item for item in paths if item[1].kind == "operator"]
        if prefer_operators and operators and self.random.random() < 0.9:
            return operators
        return paths

    def crossover(self, first, second):
        """Intercambio de subárboles entre el dominante (menor error) y el recesivo."""
        dominant, recessive = (first, second) if (first.mse, first.tree.size) <= (second.mse, second.tree.size) else (second, first)
        a, b = dominant.tree, recessive.tree
        for _ in range(20):
            path_a, branch_a = self.random.choice(self._paths(a))
            room_a = self.max_height - len(path_a)        # altura disponible en el punto de corte de a
            options = self._paths(b, room_a)
            if not options:
                continue
            path_b, branch_b = self.random.choice(options)
            if len(path_b) + branch_a.height > self.max_height:
                continue
            child = a.replace(path_a, branch_b, self.max_height)
            reciprocal = b.replace(path_b, branch_a, self.max_height)
            self.crossovers += 1
            self.last_crossover = CrossoverRecord(dominant.gene, recessive.gene, child.to_expression(), reciprocal.to_expression())
            return child, reciprocal
        return a, b

    def mutate(self, tree):
        """Aplica uno de los tipos de mutación activos; si no procede, prueba otro."""
        # Las constantes se afinan exclusivamente cambiando hojas.
        kinds = list(self.mutations)
        preferred = self.random.choices(kinds, weights=[4 if name == "hoja" else 1 for name in kinds])[0]
        self.random.shuffle(kinds)
        kinds.remove(preferred)
        kinds.insert(0, preferred)
        for kind in kinds:
            mutated = getattr(self, f"_mutate_{kind}")(tree)
            if mutated is not None and mutated != tree:
                self.mutation_counts[kind] += 1
                return mutated
        return tree

    def _mutate_subarbol(self, tree):
        path, _ = self.random.choice(list(tree.walk()))
        room = self.max_height - len(path)
        for _ in range(10):
            try:
                result = tree.replace(path, self.factory.generate(self.random.randint(1, min(room, 4))), self.max_height)
            except ValueError:
                continue
            if result != tree:
                return result
        return None

    def _mutate_hoja(self, tree):
        path, node = self.random.choice([(p, n) for p, n in tree.walk() if n.kind != "operator"])
        if node.kind == "number" and self.random.random() < 0.8:
            value = complex(node.value).real
            step = self.random.choice((0.02, 0.1, 0.5, 2.0)) * max(1, abs(value))
            replacement = Node("number", round(value + self.random.gauss(0, step), 5))
        else:
            replacement = self.factory.leaf()
        if replacement == node:
            replacement = Node("number", round(self.random.uniform(-12, 12), 5))
        return tree.replace(path, replacement, self.max_height)

    def _mutate_operador(self, tree):
        options = [(p, n) for p, n in tree.walk() if n.kind == "operator" and any(
            OPERATORS[op].arity == len(n.children) and op != n.value for op in self.factory.operators)]
        if not options:
            return None
        path, node = self.random.choice(options)
        same = [op for op in self.factory.operators if OPERATORS[op].arity == len(node.children) and op != node.value]
        return tree.replace(path, Node("operator", self.random.choice(same), node.children), self.max_height)

    def _mutate_intercambio(self, tree):
        binary = [(p, n) for p, n in tree.walk() if n.kind == "operator" and len(n.children) == 2 and n.children[0] != n.children[1]]
        useful = [(p, n) for p, n in binary if n.value in NON_COMMUTATIVE]
        options = useful or binary
        if not options:
            return None
        path, node = self.random.choice(options)
        left, right = node.children
        return tree.replace(path, Node("operator", node.value, (right, left)), self.max_height)

    def _add(self, offspring, index, tree, origin, retries=3):
        """Agrega un hijo si su curva es nueva; si repite la de otro, gana el de menor error y el otro se muta."""
        for attempt in range(retries + 1):
            individual = self._make(tree, origin)
            holder = index.get(individual.signature)
            if holder is None:
                index[individual.signature] = len(offspring)
                offspring.append(individual)
                return True
            self.duplicates += 1
            if individual.mse < offspring[holder].mse:
                offspring[holder] = individual    # misma forma pero mejor ajuste: lo sustituye
                return False
            if attempt < retries:
                tree = self.mutate(tree)
                origin = origin if "mutación" in origin else origin + " + mutación"
        return False

    def step(self):
        """Una generación completa: élite + selección, cruza, mutación, inmigrantes y ajuste fino."""
        if not self.population:
            return self.initialize()
        ranked = self.ranking(unique=True)
        self.generation += 1
        offspring, index = [], {}
        for leader in ranked[:self.elitism]:
            elite = Individual(leader.tree, leader.mse, leader.generation, "élite", leader.signature)
            index[elite.signature] = len(offspring)
            offspring.append(elite)
        if self.generation - self.last_improvement >= self.stagnation:
            # Estancamiento: se conserva la élite y el resto se reemplaza por individuos nuevos.
            self.restarts += 1
            self.last_improvement = self.generation
            guard = 0
            while len(offspring) < self.population_size:
                guard += 1
                if not self._add(offspring, index, self._random_tree(len(offspring)), "reinicio", retries=1) and guard > self.population_size * 5:
                    offspring.append(self._make(self._random_tree(), "reinicio"))
        else:
            immigrants = int(round(self.immigrants * self.population_size))
            guard = 0
            # Tope de intentos: si casi todo sale repetido, el resto se completa con inmigrantes.
            while len(offspring) < self.population_size - immigrants and guard < self.population_size * 2:
                guard += 1
                first, second = self.select(), self.select()
                if self.random.random() < self.crossover_rate:
                    children = zip(self.crossover(first, second), ("cruza", "recíproco"))
                else:
                    children = ((first.tree, "copia"), (second.tree, "copia"))
                for tree, origin in children:
                    if len(offspring) >= self.population_size - immigrants:
                        break
                    if self.random.random() < self.mutation_rate:
                        tree, origin = self.mutate(tree), origin + " + mutación"
                    self._add(offspring, index, tree, origin, retries=1)
            while len(offspring) < self.population_size:
                if not self._add(offspring, index, self._random_tree(), "inmigrante", retries=0):
                    guard += 1
                    if guard > self.population_size * 5:
                        offspring.append(self._make(self._random_tree(), "inmigrante"))
        self.population = offspring
        self._record()
        return self.population

    def run(self, generations, target_mse=0.0):
        """Ejecuta varias generaciones; se detiene antes si se alcanza target_mse."""
        if not self.population:
            self.initialize()
        for _ in range(generations):
            if self.best and self.best.mse <= target_mse:
                break
            self.step()
        return self.best
