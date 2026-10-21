"""Métricas de regresión real o compleja, independientes de la interfaz."""
from dataclasses import dataclass
from decimal import Decimal, localcontext
import math


@dataclass(frozen=True)
class Metric:
    value: float | None
    detail: str = ""

    def display(self):
        return f"{self.value:.8g}" if self.value is not None else "No definido"


@dataclass(frozen=True)
class Metrics:
    mse: Metric
    rmse: Metric
    nmse: Metric
    valid_pairs: int
    excluded_pairs: int
    normalization: str = "Varianza poblacional de la referencia en los pares válidos"


def _finite(value):
    if value is None:
        return False
    z = complex(value)
    return math.isfinite(z.real) and math.isfinite(z.imag)


def _parts(value):
    z = complex(value)
    return Decimal(str(z.real)), Decimal(str(z.imag))


def _metric(value):
    result = float(value)
    if not math.isfinite(result):
        return Metric(None, "Desbordamiento al representar la métrica como float; no es un infinito matemático.")
    if result == 0 and value != 0:
        return Metric(None, "La métrica positiva es menor que la precisión representable como float.")
    return Metric(result)


def squared_error(predicted, target):
    """|predicted-target|²; devuelve None si un operando no es finito."""
    if not (_finite(predicted) and _finite(target)):
        return None
    with localcontext() as context:
        context.prec = 50
        a, b = _parts(predicted), _parts(target)
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def regression_metrics(predicted, targets):
    """MSC/MSE=media(|f-g|²), RMSE=raíz(MSE), NMSE=MSE/Var(g).

    Los pares no finitos se excluyen y se cuentan. Una referencia constante
    tiene varianza cero: NMSE queda indefinido incluso si el ajuste es exacto.
    Decimal evita desbordar los cuadrados antes de calcular RMSE o NMSE.
    """
    predicted, targets = list(predicted), list(targets)
    if not predicted or len(predicted) != len(targets):
        raise ValueError("Se requieren dos secuencias no vacías de igual tamaño.")
    pairs = [(a, b) for a, b in zip(predicted, targets) if _finite(a) and _finite(b)]
    excluded = len(predicted) - len(pairs)
    if not pairs:
        missing = Metric(None, "No hay pares finitos comunes para comparar.")
        return Metrics(missing, missing, missing, 0, excluded)
    with localcontext() as context:
        context.prec = 50
        n = Decimal(len(pairs))
        mse = sum((squared_error(a, b) for a, b in pairs), Decimal(0)) / n
        references = [_parts(b) for _, b in pairs]
        # Centrar antes de promediar evita que una referencia constante genere
        # una varianza artificial por el redondeo de una suma muy grande.
        origin = references[0]
        centered = [(a - origin[0], b - origin[1]) for a, b in references]
        mean_a = sum((a for a, _ in centered), Decimal(0)) / n
        mean_b = sum((b for _, b in centered), Decimal(0)) / n
        variance = sum(((a - mean_a) ** 2 + (b - mean_b) ** 2 for a, b in centered), Decimal(0)) / n
        nmse = _metric(mse / variance) if variance else Metric(None, "La referencia tiene varianza cero en los pares válidos (NMSE divide entre cero).")
        return Metrics(_metric(mse), _metric(mse.sqrt()), nmse, len(pairs), excluded)


def compare_samples(predicted, reference):
    if predicted.xs != reference.xs:
        raise ValueError("La función y la referencia deben usar exactamente los mismos puntos x.")
    return regression_metrics(
        [r.value if r.finite else None for r in predicted.results],
        [r.value if r.finite else None for r in reference.results],
    )
