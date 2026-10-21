"""Regresión simbólica por búsqueda aleatoria sobre puntos (x, y) de un CSV.

Cada candidato es un árbol aleatorio f; su predicción ŷᵢ = f(xᵢ) se compara con
yᵢ mediante MSE. No se garantiza encontrar la función original: se conservan
las mejores ecuaciones encontradas al azar. Independiente de la interfaz, para
reutilizarse después con algoritmos genéticos (mismo fitness).
"""
from dataclasses import dataclass, field
from pathlib import Path
import csv
import heapq
import math
import random
from .evaluation import evaluate
from .genetics import TreeFactory
from .metrics import regression_metrics
from .parser import parse

MAX_POINTS = 5000
X_NAMES = ("x",)
Y_NAMES = ("y", "real", "valor", "f(x)", "f")


def _number(text):
    """Número real finito; admite coma decimal (CSV separados por ;)."""
    text = str(text).strip()
    for candidate in (text, text.replace(",", ".")):
        try:
            value = float(candidate)
        except ValueError:
            continue
        return value if math.isfinite(value) else None
    return None


def load_points(path):
    """Lee pares (x, y) reales y finitos.

    Acepta cabecera con columnas x/y (o el CSV exportado por la aplicación, que
    usa x/real) o, sin cabecera, las dos primeras columnas numéricas. Las filas
    con valores vacíos o no numéricos se omiten y se cuentan.
    """
    path = Path(path)
    if path.stat().st_size > 20_000_000:
        raise ValueError("El CSV supera 20 MB.")
    text = path.read_text(encoding="utf-8-sig")
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise ValueError("El CSV está vacío.")
    try:
        dialect = csv.Sniffer().sniff(lines[0], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(lines, dialect))
    header = [cell.strip().lower() for cell in rows[0]]
    x_col = y_col = None
    if any(_number(cell) is None for cell in rows[0][:2]):
        x_col = next((header.index(n) for n in X_NAMES if n in header), 0)
        y_col = next((header.index(n) for n in Y_NAMES if n in header and header.index(n) != x_col), 1 if x_col != 1 else 0)
        rows = rows[1:]
    else:
        x_col, y_col = 0, 1
    xs, ys, skipped = [], [], 0
    for row in rows:
        x = _number(row[x_col]) if len(row) > x_col else None
        y = _number(row[y_col]) if len(row) > y_col else None
        if x is None or y is None:
            skipped += 1
            continue
        xs.append(x)
        ys.append(y)
    if len(xs) < 2:
        raise ValueError("Se necesitan al menos 2 filas con x e y numéricos.")
    if len(xs) > MAX_POINTS:
        raise ValueError(f"Se admiten hasta {MAX_POINTS} puntos.")
    return xs, ys, skipped


def make_dataset(seed=None, count=40, noise=0.05, start=-5.0, end=5.0, operators=("+", "-", "*", "/", "sin", "cos"), max_height=4, formula=None):
    """Puntos de una función oculta (aleatoria o dada) con ruido gaussiano relativo.

    Devuelve (fórmula, xs, ys). Con fórmula aleatoria se repite hasta que todos
    los puntos sean reales y finitos y la función no sea constante.
    """
    rng = random.Random(seed)
    if not 2 <= count <= MAX_POINTS:
        raise ValueError(f"La cantidad de puntos debe estar entre 2 y {MAX_POINTS}.")
    xs = [start + (end - start) * i / (count - 1) for i in range(count)]
    factory = TreeFactory(operators, rng.randrange(2**32))
    for _ in range(500):
        tree = parse(formula).left if formula else factory.generate(max_height)
        values = [evaluate(tree, x) for x in xs]
        if all(r.finite and r.value.imag == 0 for r in values):
            clean = [r.value.real for r in values]
            spread = max(clean) - min(clean)
            if spread > 1e-9 and max(abs(v) for v in clean) < 1e6:
                scale = noise * spread
                return tree.to_expression(), xs, [v + rng.gauss(0, scale) for v in clean]
        if formula:
            raise ValueError("La fórmula dada no es real y finita en todos los puntos.")
    raise ValueError("No se encontró una función oculta válida; prueba otra semilla u otros operadores.")


def write_points(path, xs, ys, comment=None):
    with Path(path).open("w", newline="", encoding="utf-8") as file:
        if comment:
            file.write(f"# {comment}\n")
        writer = csv.writer(file)
        writer.writerow(["x", "y"])
        writer.writerows(zip(xs, ys))
    return Path(path)


def squared_error(tree, xs, ys, worst=math.inf):
    """MSE real de ŷ = f(x); None si algún ŷ es complejo, indefinido o desborda.

    Se detiene en cuanto la suma supera `worst`, lo que acelera la búsqueda.
    """
    total = 0.0
    limit = worst * len(xs)
    for x, y in zip(xs, ys):
        result = evaluate(tree, x)
        if not result.finite or result.value.imag != 0:
            return None
        try:
            total += (result.value.real - y) ** 2
        except OverflowError:
            return None
        if total > limit or not math.isfinite(total):
            return math.inf
    return total / len(xs)


@dataclass(order=True)
class Candidate:
    mse: float
    expression: str = field(compare=False)
    tree: object = field(compare=False)
    iteration: int = field(compare=False)

    def metrics(self, xs, ys):
        return regression_metrics(predict(self.tree, xs), ys)


def predict(tree, xs):
    """ŷᵢ = f(xᵢ); None donde la predicción no es real y finita."""
    out = []
    for x in xs:
        result = evaluate(tree, x)
        out.append(result.value.real if result.finite and result.value.imag == 0 else None)
    return out


class RandomSearch:
    """Genera árboles al azar y conserva los `keep` de menor MSE (sin repetir).

    `step(n)` evalúa n candidatos más, para poder avanzar por lotes desde una
    interfaz sin bloquearla.
    """

    def __init__(self, xs, ys, operators, max_height=5, seed=None, keep=10):
        if len(xs) != len(ys) or len(xs) < 2:
            raise ValueError("Se necesitan al menos 2 puntos con x e y.")
        self.xs, self.ys = list(xs), list(ys)
        self.factory = TreeFactory(operators, seed)
        self.max_height = max_height
        self.keep = keep
        self.best = []          # montículo de (-mse) para quitar el peor rápidamente
        self.seen = set()
        self.signatures = {}    # ŷ redondeados → expresión, para no repetir ecuaciones equivalentes
        self.iterations = 0
        self.invalid = 0
        self.history = []       # (iteración, mejor MSE) cada vez que mejora
        mean = sum(self.ys) / len(self.ys)
        self.variance = sum((y - mean) ** 2 for y in self.ys) / len(self.ys)

    @property
    def ranking(self):
        return sorted((c for _, _, c in self.best), key=lambda c: c.mse)

    def _worst(self):
        return -self.best[0][0] if len(self.best) >= self.keep else math.inf

    def step(self, count=50):
        last = None
        for _ in range(count):
            self.iterations += 1
            tree = self.factory.generate(self.max_height)
            last = tree
            expression = tree.to_expression()
            if expression in self.seen:
                continue
            self.seen.add(expression)
            mse = squared_error(tree, self.xs, self.ys, self._worst())
            if mse is None:
                self.invalid += 1
                continue
            if not math.isfinite(mse) or mse >= self._worst():
                continue
            # sin(x)*pi y pi/(1/sin(x)) dan los mismos ŷ: se conserva solo la más corta.
            signature = tuple(round(v, 9) for v in predict(tree, self.xs))
            twin = self.signatures.get(signature)
            if twin is not None:
                if len(expression) >= len(twin.expression) or twin not in self.ranking:
                    continue
                self.best = [entry for entry in self.best if entry[2] is not twin]
                heapq.heapify(self.best)
            previous = self.ranking[0].mse if self.best else math.inf
            candidate = Candidate(mse, expression, tree, self.iterations)
            self.signatures[signature] = candidate
            entry = (-mse, self.iterations, candidate)
            if len(self.best) >= self.keep:
                heapq.heapreplace(self.best, entry)
            else:
                heapq.heappush(self.best, entry)
            if mse < previous:
                self.history.append((self.iterations, mse))
        return last


def write_fit_csv(path, xs, ys, candidate):
    """CSV con x, y, ŷ, error y las métricas del candidato."""
    # Con escalado lineal (programación genética) el modelo completo es a + b·f(x).
    predictions = predict(getattr(candidate, "model", candidate.tree), xs)
    report = regression_metrics(predictions, ys)
    with Path(path).open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["x", "y", "y_gorro", "error", "error_cuadrado", "ecuacion", "MSC_MSE", "RMSE", "NMSE"])
        for x, y, y_hat in zip(xs, ys, predictions):
            error = y - y_hat if y_hat is not None else ""
            writer.writerow([x, y, "" if y_hat is None else y_hat, error, "" if y_hat is None else error ** 2,
                             candidate.expression, report.mse.value, report.rmse.value, report.nmse.value])
    return Path(path)


PRESETS = (
    ("lineal", "2*x + 1"),
    ("cuadratica", "x^2 - 3*x + 1"),
    ("senoidal", "3*sin(x)"),
    ("amortiguada", "exp(-x/4)*cos(2*x)"),
    ("racional", "1/(x^2 + 1)"),
    ("raiz", "sqrt(x + 6)"),
)


def write_presets(directory, count=60, noise=0.03, seed=2026):
    """Crea los CSV precargados y uno con función oculta aleatoria."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, (name, formula) in enumerate(PRESETS):
        _, xs, ys = make_dataset(seed + index, count, noise, formula=formula)
        paths.append(write_points(directory / f"{name}.csv", xs, ys, f"Función original: {formula}; ruido {noise:.0%} del rango"))
    hidden, xs, ys = make_dataset(seed, count, noise)
    paths.append(write_points(directory / "aleatoria.csv", xs, ys, f"Función original aleatoria: {hidden}; ruido {noise:.0%} del rango"))
    return paths


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Genera los CSV de puntos precargados para el ajuste aleatorio.")
    parser.add_argument("--directorio", default="datos_csv")
    parser.add_argument("--puntos", type=int, default=60)
    parser.add_argument("--ruido", type=float, default=0.03)
    parser.add_argument("--semilla", type=int, default=2026)
    args = parser.parse_args()
    for path in write_presets(args.directorio, args.puntos, args.ruido, args.semilla):
        print(path)


if __name__ == "__main__":
    main()
