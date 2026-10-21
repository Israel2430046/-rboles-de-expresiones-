"""Exportación de ecuaciones de prueba reproducibles, sin sobrescribir lotes."""
from datetime import datetime, timezone
from pathlib import Path
import json
from .genetics import TreeFactory, DEFAULT_OPERATORS
from .parser import parse
from .evaluation import evaluate

PROBE_POINTS = [i / 4 for i in range(-20, 21)]


def special_cases(tree, points=PROBE_POINTS):
    """Cuenta los estados de evaluación en una rejilla de prueba (incluye x = 0)."""
    counts = {}
    for x in points:
        status = evaluate(tree, x).status.value
        counts[status] = counts.get(status, 0) + 1
    return counts

EDGE_CASES = [
    ("sqrt(-4)", "Raíz compleja: 2i"),
    ("1/0", "División indefinida; no equivale a un valor infinito"),
    ("0/0", "Indeterminado"),
    ("0^0", "Indeterminado por convención"),
    ("log(0)", "Indefinido"),
    ("exp(1000)", "Desbordamiento numérico"),
    ("1/(x-0.25)", "Polo entre muestras"),
    ("1/(x-0.25)^2", "Polo de orden par"),
    ("tan(x)", "Polos periódicos"),
    ("sqrt(x)", "Complejos para x < 0"),
    ("cbrt(-8)", "Raíz cúbica real: -2"),
    ("x/x = 1", "Infinitas soluciones excepto x=0"),
    ("x = x", "Todos los valores del dominio"),
    ("x+1 = x", "Sin soluciones"),
    ("x^2+1 = 0", "Sin soluciones reales; soluciones complejas ±i"),
    ("sin(x) = 0", "Infinitas soluciones discretas"),
    ("0*(1/x) = 0", "No perder la exclusión de x=0"),
]


def generate_cases(directory, count=30, max_height=5, seed=42, operators=DEFAULT_OPERATORS):
    if type(count) is not int or not 1 <= count <= 500:
        raise ValueError("El lote debe contener entre 1 y 500 expresiones aleatorias.")
    factory = TreeFactory(operators, seed)
    random_cases = []
    for _ in range(count):
        tree = factory.generate(max_height)
        random_cases.append({"expression": tree.to_expression(), "height": tree.height, "nodes": tree.size,
                             "special_cases": special_cases(tree), "tree": tree.to_dict()})
    edges = []
    for expression, expected in EDGE_CASES:
        item = parse(expression)
        if item.height <= max_height:
            edges.append({"expression": expression, "expected": expected, "height": item.height})
    data = {"seed": seed, "probe_interval": {"start": -5, "end": 5, "step": 0.25}, "max_height": max_height, "operators": list(factory.operators), "random_cases": random_cases, "edge_cases": edges}
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("lote_%Y%m%d_%H%M%S_%f")
    json_path = directory / f"{name}.json"
    with json_path.open("x", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    text_path = directory / f"{name}.txt"
    with text_path.open("x", encoding="utf-8") as file:
        file.write("# Expresiones aleatorias\n")
        file.write("# Estados en x ∈ [-5, 5] con paso 0.25\n")
        file.write("\n".join(c["expression"] + "  # " + ", ".join(f"{k}: {v}" for k, v in c["special_cases"].items()) for c in random_cases))
        file.write("\n\n# Casos límite compatibles con la altura elegida\n")
        file.write("\n".join(c["expression"] + "  # " + c["expected"] for c in edges) + "\n")
    return json_path, text_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directorio", default="ecuaciones_prueba")
    parser.add_argument("--cantidad", type=int, default=30)
    parser.add_argument("--altura", type=int, default=5)
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()
    for path in generate_cases(args.directorio, args.cantidad, args.altura, args.semilla):
        print(path)


if __name__ == "__main__":
    main()
