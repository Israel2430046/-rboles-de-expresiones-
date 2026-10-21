"""Catálogo compartido por el parser, la interfaz y los operadores genéticos."""
from dataclasses import dataclass
from types import MappingProxyType
import cmath
import math
import operator


@dataclass(frozen=True)
class Operator:
    arity: int
    description: str
    example: str
    function: object


OPERATORS = MappingProxyType({
    "+": Operator(2, "Suma", "x + 2", operator.add),
    "-": Operator(2, "Resta", "x - 2", operator.sub),
    "*": Operator(2, "Multiplicación", "2 * x", operator.mul),
    "/": Operator(2, "División; denominador distinto de cero", "1 / x", operator.truediv),
    "**": Operator(2, "Potencia principal compleja; también ^", "x^2", operator.pow),
    "%": Operator(2, "Resto; solamente operandos reales", "x % 3", lambda a, b: a.real % b.real),
    "neg": Operator(1, "Cambio de signo", "-x", operator.neg),
    "sin": Operator(1, "Seno (radianes)", "sin(x)", cmath.sin),
    "cos": Operator(1, "Coseno (radianes)", "cos(x)", cmath.cos),
    "tan": Operator(1, "Tangente (radianes)", "tan(x)", cmath.tan),
    "asin": Operator(1, "Arcoseno principal", "asin(x)", cmath.asin),
    "acos": Operator(1, "Arcocoseno principal", "acos(x)", cmath.acos),
    "atan": Operator(1, "Arcotangente principal", "atan(x)", cmath.atan),
    "sinh": Operator(1, "Seno hiperbólico", "sinh(x)", cmath.sinh),
    "cosh": Operator(1, "Coseno hiperbólico", "cosh(x)", cmath.cosh),
    "tanh": Operator(1, "Tangente hiperbólica", "tanh(x)", cmath.tanh),
    "sqrt": Operator(1, "Raíz cuadrada principal, admite negativos", "sqrt(-4)", cmath.sqrt),
    "cbrt": Operator(1, "Raíz cúbica real para reales", "cbrt(-8)", lambda z: complex(math.cbrt(z.real)) if z.imag == 0 else z ** (1 / 3)),
    "log": Operator(1, "Logaritmo natural principal; también ln", "log(x)", cmath.log),
    "log10": Operator(1, "Logaritmo principal en base 10", "log10(x)", cmath.log10),
    "exp": Operator(1, "Exponencial", "exp(x)", cmath.exp),
    "abs": Operator(1, "Valor absoluto o módulo complejo", "abs(x + i)", abs),
    "re": Operator(1, "Parte real", "re(x + i)", lambda z: z.real),
    "im": Operator(1, "Parte imaginaria", "im(x + i)", lambda z: z.imag),
    "conj": Operator(1, "Conjugado", "conj(x + i)", lambda z: z.conjugate()),
})
CONSTANTS = MappingProxyType({"pi": complex(math.pi), "e": complex(math.e), "i": 1j})
ALIASES = {"ln": "log", "sen": "sin", "j": "i"}

