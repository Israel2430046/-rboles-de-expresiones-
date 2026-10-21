"""Árbol inmutable, serializable y con sustitución de subárboles."""
from dataclasses import dataclass
import math
from .operators import OPERATORS, CONSTANTS

MAX_HEIGHT = 12
MAX_NODES = 255


@dataclass(frozen=True)
class Node:
    kind: str
    value: str | float | complex
    children: tuple["Node", ...] = ()

    def __post_init__(self):
        if not isinstance(self.children, tuple) or not all(isinstance(n, Node) for n in self.children):
            raise ValueError("Los hijos deben ser una tupla de nodos.")
        if self.kind == "operator":
            if self.value not in OPERATORS or len(self.children) != OPERATORS[self.value].arity:
                raise ValueError("Operador o número de argumentos inválido.")
        elif self.kind == "number":
            if type(self.value) not in (int, float, complex) or not all(math.isfinite(v) for v in (complex(self.value).real, complex(self.value).imag)):
                raise ValueError("Se requieren constantes numéricas finitas.")
        elif self.kind == "variable":
            if self.value != "x":
                raise ValueError("La variable admitida es x.")
        elif self.kind == "constant":
            if self.value not in CONSTANTS:
                raise ValueError("Constante desconocida.")
        else:
            raise ValueError("Tipo de nodo desconocido.")
        if self.kind != "operator" and self.children:
            raise ValueError("Una hoja no puede tener hijos.")

    @property
    def height(self):
        """Una hoja tiene altura 1."""
        return 1 + max((child.height for child in self.children), default=0)

    @property
    def size(self):
        return 1 + sum(child.size for child in self.children)

    def walk(self, path=()):
        yield path, self
        for index, child in enumerate(self.children):
            yield from child.walk(path + (index,))

    def at(self, path):
        node = self
        for index in path:
            if type(index) is not int or index < 0 or index >= len(node.children):
                raise ValueError("Ruta de subárbol inválida.")
            node = node.children[index]
        return node

    def replace(self, path, subtree, max_height=MAX_HEIGHT):
        self.at(path)
        def visit(node, remaining):
            if not remaining:
                return subtree
            children = list(node.children)
            children[remaining[0]] = visit(children[remaining[0]], remaining[1:])
            return Node(node.kind, node.value, tuple(children))
        result = visit(self, path)
        validate_size(result, max_height)
        return result

    def to_expression(self):
        if self.kind != "operator":
            return str(self.value)
        args = [n.to_expression() for n in self.children]
        if self.value == "neg":
            return f"(-{args[0]})"
        if len(args) == 2:
            return f"({args[0]} {self.value} {args[1]})"
        return f"{self.value}({args[0]})"

    def to_dict(self):
        value = self.value
        if isinstance(value, complex):
            value = {"real": value.real, "imag": value.imag}
        return {"kind": self.kind, "value": value, "children": [n.to_dict() for n in self.children]}

    @classmethod
    def from_dict(cls, data):
        count = 0
        def build(item, depth):
            nonlocal count
            count += 1
            if depth > MAX_HEIGHT or count > MAX_NODES:
                raise ValueError("El árbol serializado excede los límites.")
            value = item["value"]
            if isinstance(value, dict):
                value = complex(value["real"], value["imag"])
            return cls(item["kind"], value, tuple(build(n, depth + 1) for n in item.get("children", [])))
        return build(data, 1)


def validate_size(tree, max_height=MAX_HEIGHT):
    if type(max_height) is not int or not 1 <= max_height <= MAX_HEIGHT:
        raise ValueError(f"La altura máxima debe ser un entero entre 1 y {MAX_HEIGHT}.")
    if tree.height > max_height:
        raise ValueError(f"El árbol tiene altura {tree.height}; el máximo elegido es {max_height}.")
    if tree.size > MAX_NODES:
        raise ValueError(f"Se permiten como máximo {MAX_NODES} nodos.")

