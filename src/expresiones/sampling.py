"""Muestreo acotado y separación de tramos para la gráfica."""
from collections import Counter
from dataclasses import dataclass
import math
from .evaluation import evaluate, Status

MAX_SAMPLES = 5000


@dataclass(frozen=True)
class Interval:
    start: float = -10
    end: float = 10
    step: float = 0.1

    def points(self):
        if not all(math.isfinite(v) for v in (self.start, self.end, self.step)):
            raise ValueError("El intervalo y el paso deben ser finitos.")
        if self.start >= self.end or self.step <= 0:
            raise ValueError("Se requiere inicio < fin y paso > 0.")
        if self.start + self.step == self.start or self.end - self.step == self.end:
            raise ValueError("El paso es demasiado pequeño para la precisión de este intervalo.")
        ratio = (self.end - self.start) / self.step
        if not math.isfinite(ratio) or math.ceil(ratio) + 1 > MAX_SAMPLES:
            raise ValueError(f"Elige un paso mayor: se permiten hasta {MAX_SAMPLES} muestras.")
        points = [self.start + i * self.step for i in range(math.floor(ratio) + 1)]
        if math.isclose(points[-1], self.end, rel_tol=0, abs_tol=self.step * 1e-10):
            points[-1] = self.end
        else:
            points.append(self.end)
        return points


def _barriers(tree, x):
    """Vigila denominadores, polos y saltos de resto entre muestras."""
    result = []
    for _, node in tree.walk():
        if node.kind != "operator":
            continue
        if node.value in ("/", "%"):
            r = evaluate(node.children[1], x)
            result.append(r.value.real if r.finite and r.value.imag == 0 else math.nan)
            if node.value == "%":
                a = evaluate(node.children[0], x)
                quotient = a.value.real / r.value.real if a.finite and r.finite and a.value.imag == r.value.imag == 0 and r.value != 0 else math.nan
                result.append(("bucket", math.floor(quotient) if math.isfinite(quotient) else None))
        elif node.value == "tan":
            from .tree import Node
            r = evaluate(Node("operator", "cos", node.children), x)
            result.append(r.value.real if r.finite and r.value.imag == 0 else math.nan)
    return result


def _barrier_crossed(left, right):
    for a, b in zip(left, right):
        if isinstance(a, tuple):
            if a != b:
                return True
        elif math.isfinite(a) and math.isfinite(b) and (a == 0 or b == 0 or (a < 0) != (b < 0)):
            return True
    return False


@dataclass
class Samples:
    xs: list
    results: list
    breaks: list

    @property
    def counts(self):
        return Counter(r.status.value for r in self.results)

    def status_ranges(self):
        """Tramos consecutivos con el mismo estado: [(estado, x_inicial, x_final, muestras)]."""
        ranges = []
        for x, result in zip(self.xs, self.results):
            if ranges and ranges[-1][0] == result.status:
                status, first, _, count = ranges[-1]
                ranges[-1] = (status, first, x, count + 1)
            else:
                ranges.append((result.status, x, x, 1))
        return ranges

    def plot_values(self, mode="real", singularities=()):
        """Inserta NaN; nunca une deliberadamente polos conocidos."""
        xs, real, imag = [], [], []
        for index, (x, result) in enumerate(zip(self.xs, self.results)):
            cut = index > 0 and (self.breaks[index] or any(self.xs[index - 1] <= p <= x for p in singularities))
            if cut:
                xs.append(math.nan)
                real.append(math.nan)
                imag.append(math.nan)
            xs.append(x)
            allowed = result.finite and (mode != "real" or result.status == Status.REAL)
            real.append(result.value.real if allowed else math.nan)
            imag.append(result.value.imag if allowed else math.nan)
        return xs, real, imag


def sample(tree, interval):
    xs = interval.points()
    results = [evaluate(tree, x) for x in xs]
    barriers = [_barriers(tree, x) for x in xs]
    breaks = [False] * len(xs)
    for index in range(1, len(xs)):
        a, b = results[index - 1:index + 1]
        mid = (xs[index - 1] + xs[index]) / 2
        m = evaluate(tree, mid)
        breaks[index] = not (a.finite and b.finite and m.finite) or _barrier_crossed(barriers[index - 1], barriers[index])
        if a.finite and b.finite and m.finite:
            if a.status == b.status == Status.REAL and m.status == Status.COMPLEX:
                breaks[index] = True
            # Precaución frente a polos no encontrados simbólicamente.
            curvature = abs(m.value - (a.value + b.value) / 2)
            scale = max(1, abs(a.value), abs(b.value))
            breaks[index] |= curvature > 2 * scale
    return Samples(xs, results, breaks)



def complex_grid(tree, interval, size=51):
    """Evalúa f(z) en z = a + bi; a recorre el intervalo y b el mismo ancho centrado en 0.

    Devuelve tres matrices (a, b, f) para la superficie 3D; los valores no
    finitos (indefinidos, indeterminados, desbordados) quedan como NaN.
    """
    import numpy as np
    if not (math.isfinite(interval.start) and math.isfinite(interval.end) and interval.start < interval.end):
        raise ValueError("Se requiere un intervalo finito con inicio < fin.")
    if type(size) is not int or not 5 <= size <= 121:
        raise ValueError("La rejilla debe tener entre 5 y 121 puntos por eje.")
    half = (interval.end - interval.start) / 2
    real, imag = np.meshgrid(np.linspace(interval.start, interval.end, size), np.linspace(-half, half, size))
    values = np.full(real.shape, complex(math.nan, math.nan))
    for index in np.ndindex(real.shape):
        result = evaluate(tree, complex(real[index], imag[index]))
        if result.finite:
            values[index] = result.value
    return real, imag, values
