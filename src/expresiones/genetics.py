"""Generación, mutación, cruce y fitness para futura programación genética."""
import math
import random
from .tree import Node, MAX_HEIGHT, MAX_NODES, validate_size
from .operators import OPERATORS
from .evaluation import evaluate

DEFAULT_OPERATORS = ("+", "-", "*", "/", "**", "sin", "cos", "sqrt", "log")


class TreeFactory:
    def __init__(self, operators=DEFAULT_OPERATORS, seed=None, constants=("i", "pi", "e")):
        self.operators = tuple(operators)
        self.constants = tuple(constants)
        if not self.operators or any(op not in OPERATORS for op in self.operators):
            raise ValueError("Selecciona al menos un operador válido.")
        self.random = random.Random(seed)

    def generate(self, max_height=5):
        validate_size(Node("variable", "x"), max_height)
        budget = MAX_NODES
        def build(height, allowance, root=False):
            if height == 1 or allowance < 3 or (not root and self.random.random() < 0.28):
                return self.leaf()
            op = self.random.choice(self.operators)
            arity = OPERATORS[op].arity
            if arity == 1:
                children = (build(height - 1, allowance - 1),)
            else:
                left_budget = (allowance - 1) // 2
                children = (build(height - 1, left_budget), build(height - 1, allowance - 1 - left_budget))
            return Node("operator", op, children)
        result = build(max_height, budget, True)
        validate_size(result, max_height)
        return result

    def leaf(self):
        """Hoja aleatoria: x, un entero 0-9 o una de las constantes permitidas."""
        options = [Node("variable", "x"), Node("number", self.random.randint(0, 9))]
        if self.constants:
            options.append(Node("constant", self.random.choice(self.constants)))
        return self.random.choice(options)

    def mutate(self, tree, max_height=MAX_HEIGHT):
        validate_size(tree, max_height)
        paths = [path for path, _ in tree.walk()]
        for _ in range(30):
            path = self.random.choice(paths)
            replacement = self.generate(max_height - len(path))
            try:
                return tree.replace(path, replacement, max_height)
            except ValueError:
                continue
        return tree

    def crossover(self, first, second, max_height=MAX_HEIGHT):
        validate_size(first, max_height)
        validate_size(second, max_height)
        a_paths, b_paths = list(first.walk()), list(second.walk())
        for _ in range(50):
            path_a, subtree_a = self.random.choice(a_paths)
            path_b, subtree_b = self.random.choice(b_paths)
            try:
                return first.replace(path_a, subtree_b, max_height), second.replace(path_b, subtree_a, max_height)
            except ValueError:
                continue
        return first, second


def mean_squared_error(tree, points, targets, invalid_penalty=1e12):
    """Fitness real. Penaliza complejos e indefinidos de forma explícita."""
    points, targets = list(points), list(targets)
    if not points or len(points) != len(targets):
        raise ValueError("Se necesitan muestras y objetivos de igual tamaño, no vacíos.")
    if not math.isfinite(invalid_penalty) or invalid_penalty <= 0:
        raise ValueError("La penalización debe ser positiva y finita.")
    errors = []
    for x, target in zip(points, targets):
        if not math.isfinite(target):
            raise ValueError("Los objetivos deben ser reales finitos.")
        result = evaluate(tree, x)
        if not result.finite or result.value.imag != 0:
            errors.append(invalid_penalty)
        else:
            try:
                errors.append(min(invalid_penalty, (result.value.real - target) ** 2))
            except OverflowError:
                errors.append(invalid_penalty)
    return sum(e / len(errors) for e in errors)

