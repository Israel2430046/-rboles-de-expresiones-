"""Evaluación compleja sin simplificar ni ocultar operaciones indefinidas."""
from dataclasses import dataclass
from enum import Enum
import cmath
import math
from .operators import OPERATORS, CONSTANTS
from .tree import Node


class Status(str, Enum):
    REAL = "real"
    COMPLEX = "complejo"
    UNDEFINED = "indefinido"
    INDETERMINATE = "indeterminado"
    OVERFLOW = "desbordamiento"


@dataclass(frozen=True)
class Result:
    status: Status
    value: complex | None = None
    detail: str = ""

    @property
    def finite(self):
        return self.status in (Status.REAL, Status.COMPLEX)

    def display(self):
        if not self.finite:
            return f"{self.status.value}: {self.detail}"
        z = self.value
        if z.imag == 0:
            return f"{z.real:.10g}"
        return f"{z.real:.10g} {z.imag:+.10g}i"


def numeric_result(value):
    value = complex(value)
    if not (math.isfinite(value.real) and math.isfinite(value.imag)):
        return Result(Status.OVERFLOW, detail="El resultado excede la precisión numérica; no prueba un infinito matemático.")
    # Quita el cero imaginario con signo para elegir siempre el borde superior
    # del corte principal en un argumento real negativo (log y sqrt).
    if value.imag == 0:
        value = complex(value.real, 0.0)
    return Result(Status.REAL if value.imag == 0 else Status.COMPLEX, value)


def evaluate(node: Node, x: complex = 0) -> Result:
    if node.kind == "number":
        return numeric_result(node.value)
    if node.kind == "variable":
        return numeric_result(x)
    if node.kind == "constant":
        return numeric_result(CONSTANTS[node.value])
    results = [evaluate(child, x) for child in node.children]
    for result in results:
        if not result.finite:
            return result
    values = [r.value for r in results]
    op = node.value
    a = values[0]
    if op in ("/", "%") and values[1] == 0:
        return Result(Status.INDETERMINATE if a == 0 else Status.UNDEFINED, detail="0/0 o 0%0" if a == 0 else "División entre cero; el valor en este punto no existe.")
    if op == "%" and any(v.imag != 0 for v in values):
        return Result(Status.UNDEFINED, detail="El resto % solo se define aquí para números reales.")
    if op == "**" and a == 0:
        if values[1] == 0:
            return Result(Status.INDETERMINATE, detail="0^0 se considera indeterminado en este intérprete.")
        if values[1].real < 0 or values[1].imag != 0:
            return Result(Status.UNDEFINED, detail="Potencia de cero con exponente negativo o complejo.")
    if op in ("log", "log10") and a == 0:
        return Result(Status.UNDEFINED, detail="El logaritmo de cero no tiene un valor finito.")
    try:
        if op == "tan" and abs(cmath.cos(a)) < 1e-14:
            return Result(Status.UNDEFINED, detail="Polo de la tangente (tolerancia numérica 1e-14).")
        return numeric_result(OPERATORS[op].function(*values))
    except OverflowError:
        return Result(Status.OVERFLOW, detail="Se excedió el rango de punto flotante.")
    except (ValueError, ZeroDivisionError) as exc:
        return Result(Status.UNDEFINED, detail=f"Operación {op} fuera de dominio: {exc}")



def evaluate_nodes(tree: Node, x: complex = 0) -> dict:
    """Resultado de cada subárbol, indexado por su ruta; útil para colorear el árbol."""
    return {path: evaluate(node, x) for path, node in tree.walk()}
