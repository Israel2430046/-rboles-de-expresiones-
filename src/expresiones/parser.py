"""Parser con lista permitida de AST. Nunca ejecuta la entrada del usuario."""
import ast
from dataclasses import dataclass
from .tree import Node, MAX_HEIGHT, MAX_NODES, validate_size
from .operators import OPERATORS, CONSTANTS, ALIASES


@dataclass(frozen=True)
class Expression:
    left: Node
    right: Node | None = None

    @property
    def is_equation(self):
        return self.right is not None

    @property
    def residual(self):
        return Node("operator", "-", (self.left, self.right)) if self.is_equation else self.left

    @property
    def height(self):
        return 1 + max(self.left.height, self.right.height) if self.is_equation else self.left.height

    @property
    def size(self):
        return 1 + self.left.size + self.right.size if self.is_equation else self.left.size

    def to_expression(self):
        return self.left.to_expression() + (" = " + self.right.to_expression() if self.is_equation else "")


BINOPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "**", ast.Mod: "%"}


def parse(text: str, max_height: int = MAX_HEIGHT) -> Expression:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Escribe una expresión, por ejemplo sqrt(x) + sin(x).")
    if len(text) > 4000:
        raise ValueError("La expresión no puede superar 4000 caracteres.")
    text = text.strip().replace("^", "**").replace("π", "pi").replace("×", "*").replace("÷", "/").replace("−", "-")
    parts = text.split("=")
    if len(parts) > 2 or any(not part.strip() for part in parts):
        raise ValueError("Usa una expresión o una ecuación con un solo signo =.")
    count = 0
    def convert(item, depth=1):
        nonlocal count
        count += 1
        if count > MAX_NODES or depth > MAX_HEIGHT:
            raise ValueError("Expresión demasiado grande: máximo 255 nodos y altura 12.")
        if isinstance(item, ast.Constant) and type(item.value) in (int, float, complex):
            if abs(item.value) > 1e100:
                raise ValueError("Constante demasiado grande (máximo 1e100).")
            return Node("number", item.value)
        if isinstance(item, ast.Name):
            name = ALIASES.get(item.id, item.id)
            if name == "x":
                return Node("variable", "x")
            if name in CONSTANTS:
                return Node("constant", name)
            raise ValueError(f"Nombre desconocido: {item.id}. Usa x, pi, e o i.")
        if isinstance(item, ast.BinOp) and type(item.op) in BINOPS:
            return Node("operator", BINOPS[type(item.op)], (convert(item.left, depth + 1), convert(item.right, depth + 1)))
        if isinstance(item, ast.UnaryOp) and isinstance(item.op, (ast.UAdd, ast.USub)):
            child = convert(item.operand, depth + 1)
            if isinstance(item.op, ast.UAdd):
                return child
            if child.kind == "number":
                return Node("number", -child.value)
            return Node("operator", "neg", (child,))
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
            name = ALIASES.get(item.func.id, item.func.id)
            if name in OPERATORS and name != "neg" and OPERATORS[name].arity == 1:
                if len(item.args) != 1 or item.keywords:
                    raise ValueError(f"{name} requiere exactamente un argumento.")
                return Node("operator", name, (convert(item.args[0], depth + 1),))
        raise ValueError("Sintaxis no permitida. Usa operadores del catálogo y multiplicación explícita: 2*x.")
    try:
        nodes = [convert(ast.parse(part.strip(), mode="eval").body) for part in parts]
        result = Expression(*nodes)
        validate_size(result.residual, max_height)
        return result
    except (SyntaxError, RecursionError, OverflowError) as exc:
        raise ValueError("Revisa los paréntesis, los números y los operadores de la expresión.") from exc

