"""Adaptador SymPy. Solo recibe árboles previamente validados, nunca cadenas."""
from dataclasses import dataclass, field
import sympy as sp
from sympy.calculus.util import continuous_domain


def to_sympy(node, symbol):
    if node.kind == "variable":
        return symbol
    if node.kind == "constant":
        return {"pi": sp.pi, "e": sp.E, "i": sp.I}[node.value]
    if node.kind == "number":
        if isinstance(node.value, complex):
            return sp.Rational(str(node.value.real)) + sp.I * sp.Rational(str(node.value.imag))
        return sp.Rational(str(node.value))
    args = [to_sympy(child, symbol) for child in node.children]
    op = node.value
    if op == "+":
        return sp.Add(*args, evaluate=False)
    if op in ("-", "neg"):
        negative = sp.Mul(-1, args[-1], evaluate=False)
        return sp.Add(args[0], negative, evaluate=False) if op == "-" else negative
    if op == "*":
        return sp.Mul(*args, evaluate=False)
    if op == "/":
        return sp.Mul(args[0], sp.Pow(args[1], -1, evaluate=False), evaluate=False)
    if op == "**":
        return sp.Pow(*args, evaluate=False)
    if op == "sqrt":
        return sp.Pow(args[0], sp.Rational(1, 2), evaluate=False)
    if op == "cbrt":
        return sp.real_root(args[0], 3)
    if op == "log10":
        return sp.Mul(sp.log(args[0], evaluate=False), 1 / sp.log(10), evaluate=False)
    fn = {"%": sp.Mod, "abs": sp.Abs, "conj": sp.conjugate}.get(op) or getattr(sp, op)
    return fn(*args, evaluate=False)


def defined_domain(tree, symbol, domain):
    """Conserva restricciones de TODOS los subárboles, incluso si se cancelan."""
    valid = domain
    for _, node in tree.walk():
        if node.kind != "operator":
            continue
        op = node.value
        args = [to_sympy(c, symbol) for c in node.children]
        forbidden = []
        if op in ("/", "%"):
            forbidden.append(args[1])
        if op in ("log", "log10"):
            forbidden.append(args[0])
        if op in ("tan", "tanh"):
            forbidden.append((sp.cos if op == "tan" else sp.cosh)(args[0]))
        if op == "atan":
            forbidden.append(args[0] ** 2 + 1)
        if op == "**":
            base, exponent = args
            zeros = sp.solveset(base, symbol, domain=domain)
            if zeros != sp.S.EmptySet:
                positive_real = sp.And(sp.Eq(sp.im(exponent), 0), sp.re(exponent) > 0)
                condition = sp.Not(positive_real)
                if symbol.is_real and condition.free_symbols <= {symbol}:
                    try:
                        bad = condition.as_set().intersect(zeros)
                    except (NotImplementedError, AttributeError):
                        bad = sp.ConditionSet(symbol, condition, zeros)
                else:
                    bad = sp.ConditionSet(symbol, condition, zeros)
                valid = valid - bad
        if op == "%":
            valid = sp.ConditionSet(symbol, sp.And(*(sp.Eq(sp.im(a), 0) for a in args)), valid)
        for expr in forbidden:
            valid = valid - sp.solveset(expr, symbol, domain=domain)
    return valid


def _solution_label(solutions):
    if solutions == sp.S.EmptySet:
        return "Sin soluciones"
    if solutions.has(sp.ConditionSet):
        return "Solución pendiente de resolver (conjunto condicionado)"
    if solutions.is_finite_set is True:
        return f"{len(solutions)} solución(es)" if isinstance(solutions, sp.FiniteSet) else "Conjunto finito"
    if solutions.is_finite_set is False or _known_infinite(solutions):
        return "Infinitas soluciones"
    return "Conjunto de soluciones; cardinalidad no determinada"


def _known_infinite(solutions):
    if isinstance(solutions, sp.Union):
        return any(_known_infinite(part) for part in solutions.args)
    if isinstance(solutions, sp.ImageSet) and solutions.base_set == sp.S.Integers:
        variable, = solutions.lamda.variables
        formula = solutions.lamda.expr
        return formula.is_polynomial(variable) and sp.degree(formula, variable) >= 1
    return solutions.is_finite_set is False


def _simplify_on_valid_domain(expression):
    # En los puntos válidos, 0**z solo admite exponentes reales positivos.
    expression = expression.replace(lambda n: n.is_Pow and n.base.is_zero is True, lambda n: sp.S.Zero)
    return sp.simplify(expression)


@dataclass
class Analysis:
    domain: str = "No calculado"
    solutions: str = ""
    solution_kind: str = ""
    singularities: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    points: list = field(default_factory=list)  # singularidades exactas de SymPy, para los límites


def analyze(expression, start, end, solution_domain="real"):
    """Ejecutar en un proceso cancelable: el cálculo simbólico puede ser costoso."""
    report = Analysis()
    tree = expression.residual
    x = sp.Symbol("x", real=True)
    interval = sp.Interval(sp.Rational(str(start)), sp.Rational(str(end)))
    try:
        symbolic = _simplify_on_valid_domain(to_sympy(tree, x))
        valid = defined_domain(tree, x, interval)
        holes = interval - valid
        if isinstance(holes, sp.FiniteSet):
            report.points = sorted((p for p in holes if p.is_real and p.is_finite), key=float)
            report.singularities = [float(p) for p in report.points]
        if not expression.is_equation and not symbolic.has(x):
            report.notes.append(f"La expresión no depende de x: es constante e igual a {symbolic} en su dominio (identidad).")
        real_domain = continuous_domain(symbolic, x, interval).intersect(valid)
        if not symbolic.has(x) and sp.im(symbolic).is_zero is False:
            real_domain = sp.S.EmptySet
        elif symbolic.has(sp.I):
            real_domain = real_domain.intersect(sp.solveset(sp.im(symbolic), x, domain=interval))
        report.domain = str(real_domain)
    except Exception as exc:
        report.domain = "No determinado simbólicamente"
        report.notes.append(f"Dominio: {type(exc).__name__}. Consulta los estados de las muestras.")
    if expression.is_equation:
        try:
            domain = sp.S.Reals if solution_domain == "real" else sp.S.Complexes
            symbol = x if solution_domain == "real" else sp.Symbol("x")
            # cbrt usa una convención real por tramos que el solver complejo no representa.
            if solution_domain == "complex" and any(n.value == "cbrt" for _, n in tree.walk()):
                raise NotImplementedError("cbrt tiene una convención por tramos; usa potencias para raíces complejas principales")
            symbolic = to_sympy(tree, symbol)
            valid = defined_domain(tree, symbol, domain)
            if valid == sp.S.EmptySet:
                report.solutions = "No hay puntos donde la ecuación original esté definida."
                report.solution_kind = "Ecuación indefinida"
            else:
                symbolic = _simplify_on_valid_domain(symbolic)
                solutions = sp.solveset(symbolic, symbol, domain=domain).intersect(valid)
                report.solutions = str(solutions)
                report.solution_kind = _solution_label(solutions)
        except Exception as exc:
            report.solutions = f"No resuelta: {exc}"
            report.solution_kind = "Análisis no concluyente"
    report.notes.append("Las soluciones se buscan en todo ℝ o ℂ; el intervalo limita la gráfica y el dominio mostrado.")
    return report



def _show(value):
    if isinstance(value, sp.AccumBounds):
        return f"no existe, oscila en [{_show(value.min)}, {_show(value.max)}]"
    return str(value).replace("zoo", "∞ complejo").replace("oo", "∞")


def _classify(left, right):
    infinite = (sp.oo, -sp.oo, sp.zoo)
    finite = lambda v: v.is_finite is True and not v.has(sp.AccumBounds)
    if left == right and finite(left):
        return f"discontinuidad evitable (forma indeterminada); el límite existe y vale {_show(left)}"
    if left in infinite or right in infinite:
        return f"asíntota vertical (polo): lím⁻ = {_show(left)}, lím⁺ = {_show(right)}"
    if finite(left) and finite(right):
        return f"salto finito: lím⁻ = {_show(left)}, lím⁺ = {_show(right)}"
    return f"el límite no existe o es oscilante: lím⁻ = {_show(left)}, lím⁺ = {_show(right)}"


def limits(expression, points, max_points=8):
    """Límites laterales en las singularidades y comportamiento en ±∞.

    Va en un mensaje aparte del análisis: sp.limit puede tardar y no debe
    retrasar el dominio ni las soluciones.
    """
    x = sp.Symbol("x", real=True)
    lines = []
    try:
        function = _simplify_on_valid_domain(to_sympy(expression.residual, x))
    except Exception as exc:
        return [f"Límites no calculados: {type(exc).__name__}"]
    from .evaluation import evaluate, Status
    def complex_side(value):
        # El solver usa x real; un lado con valores complejos no tiene límite real.
        return evaluate(expression.residual, value).status == Status.COMPLEX
    for point in points[:max_points]:
        try:
            left, right = (sp.limit(function, x, point, side) for side in "-+")
            if complex_side(float(point) - 1e-7):
                left = "complejo (fuera de ℝ)"
            if complex_side(float(point) + 1e-7):
                right = "complejo (fuera de ℝ)"
            if isinstance(left, str) or isinstance(right, str):
                lines.append(f"x = {point}: frontera del dominio real: lím⁻ = {_show(left)}, lím⁺ = {_show(right)}")
                continue
            lines.append(f"x = {point}: " + _classify(left, right))
        except Exception:
            lines.append(f"x = {point}: límite no determinado simbólicamente")
    if len(points) > max_points:
        lines.append(f"… y {len(points) - max_points} singularidades más en el intervalo.")
    for label, target in (("x → −∞", -sp.oo), ("x → +∞", sp.oo)):
        try:
            if complex_side(1e6 if target == sp.oo else -1e6):
                lines.append(f"{label}: valores complejos (fuera de ℝ)")
                continue
            lines.append(f"{label}: {_show(sp.limit(function, x, target))}")
        except Exception:
            lines.append(f"{label}: no determinado")
    return lines
