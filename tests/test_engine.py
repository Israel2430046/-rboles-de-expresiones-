import json
import math
from pathlib import Path
import tempfile
import unittest

from expresiones import Node, parse, evaluate, Status, OPERATORS
from expresiones.genetics import TreeFactory, mean_squared_error
from expresiones.sampling import Interval, sample
from expresiones.symbolic import analyze
from expresiones.cases import generate_cases


class ParserTests(unittest.TestCase):
    def test_precedence_and_equation(self):
        self.assertEqual(evaluate(parse('-2^2 + 3*(4+1)').left).value, 11)
        self.assertEqual(evaluate(parse('2^3^2').left).value, 512)
        self.assertEqual(parse('x^2=4').height, 3)
        self.assertEqual(evaluate(parse('x^2=4').residual, 2).value, 0)

    def test_aliases(self):
        self.assertAlmostEqual(evaluate(parse('sen(π/2)+ln(e)').left).value.real, 2)
        self.assertEqual(evaluate(parse('2*j').left).value, 2j)

    def test_rejects_code_and_invalid_input(self):
        for text in ['', '(x+1', '2x', 'y+1', 'x==1', 'x=', 'a=b=c',
                     '__import__("os").system("echo bad")', 'x.__class__',
                     '[x for x in range(3)]', 'lambda: 1', 'sin(x,2)',
                     'sin(x=2)', 'True', '1e309', '1e101', 'x[0]', 'x//2']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse(text)

    def test_height_limits(self):
        parse('x', 1)
        with self.assertRaises(ValueError):
            parse('x+1', 1)
        with self.assertRaises(ValueError):
            parse('x=x', 1)
        for height in [0, 13, 1.5]:
            with self.assertRaises(ValueError):
                parse('x', height)
        with self.assertRaises(ValueError):
            parse('sin(' * 15 + 'x' + ')' * 15)


class EvaluationTests(unittest.TestCase):
    def test_complex_and_real_roots(self):
        self.assertEqual(evaluate(parse('sqrt(-4)').left).value, 2j)
        self.assertAlmostEqual(evaluate(parse('cbrt(-8)').left).value.real, -2)
        self.assertAlmostEqual(evaluate(parse('log(-1)').left).value.imag, math.pi)
        self.assertEqual(evaluate(parse('abs(3+4*i)').left).value, 5)
        self.assertEqual(evaluate(parse('sqrt(-1)*sqrt(-1)').left).value, -1)

    def test_invalid_values_are_distinct(self):
        cases = {'1/0': Status.UNDEFINED, '0/0': Status.INDETERMINATE,
                 '0^0': Status.INDETERMINATE, '0^-2': Status.UNDEFINED,
                 'log(0)': Status.UNDEFINED, 'i%2': Status.UNDEFINED,
                 'exp(1000)': Status.OVERFLOW, 'tan(pi/2)': Status.UNDEFINED,
                 '0*(1/0)': Status.UNDEFINED, '1/(1/0)': Status.UNDEFINED,
                 'sqrt(-4)': Status.COMPLEX, '1e-100': Status.REAL}
        for text, status in cases.items():
            with self.subTest(text=text):
                self.assertEqual(evaluate(parse(text).left).status, status)

    def test_catalog_can_evaluate(self):
        for name, spec in OPERATORS.items():
            with self.subTest(name=name):
                self.assertIsInstance(evaluate(parse(spec.example).left, 0.5).status, Status)


class SamplingTests(unittest.TestCase):
    def test_interval_and_endpoint(self):
        points = Interval(0, 1, 0.3).points()
        self.assertEqual(points[0], 0)
        self.assertEqual(points[-1], 1)
        self.assertEqual(len(points), 5)
        for interval in [Interval(1, 0, 1), Interval(0, 1, 0), Interval(0, 1, -1),
                         Interval(0, 1, 1e-9), Interval(0, math.inf, 1),
                         Interval(1e20, 2e20, 1)]:
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                interval.points()

    def test_complex_not_plotted_as_real(self):
        samples = sample(parse('sqrt(x)').left, Interval(-1, 1, 1))
        xs, real, imaginary = samples.plot_values('real')
        self.assertTrue(math.isnan(real[0]))
        xs, real, imaginary = samples.plot_values('complex')
        self.assertEqual(imaginary[0], 1)
        self.assertEqual(samples.counts, {'complejo': 1, 'real': 2})

    def test_poles_between_samples(self):
        samples = sample(parse('1/(x-0.25)').left, Interval(0, 1, 0.5))
        self.assertTrue(samples.breaks[1])
        samples = sample(parse('1/(x-0.25)^2').left, Interval(0, 1, 0.5))
        report = analyze(parse('1/(x-0.25)^2'), 0, 1)
        self.assertEqual(report.singularities, [0.25])
        xs, _, _ = samples.plot_values(singularities=report.singularities)
        self.assertTrue(any(math.isnan(x) for x in xs))

    def test_tangent_and_modulo_jumps(self):
        self.assertTrue(sample(parse('tan(x)').left, Interval(1, 2, 1)).breaks[1])
        self.assertTrue(sample(parse('x%1').left, Interval(0.8, 1.2, 0.4)).breaks[1])
        self.assertEqual(len(sample(parse('x%1e-100').left, Interval(0, 1, 0.5)).xs), 3)

    def test_complex_gap_between_real_endpoints(self):
        samples = sample(parse('sqrt((x-0.25)^2-0.01)').left, Interval(0, 0.5, 0.5))
        self.assertTrue(all(r.status == Status.REAL for r in samples.results))
        self.assertTrue(samples.breaks[1])


class SymbolicTests(unittest.TestCase):
    def test_solutions_real_and_complex(self):
        self.assertEqual(analyze(parse('x^2+1=0'), -2, 2).solution_kind, 'Sin soluciones')
        result = analyze(parse('x^2+1=0'), -2, 2, 'complex')
        self.assertEqual(result.solutions, '{-I, I}')
        self.assertEqual(result.solution_kind, '2 solución(es)')
        self.assertEqual(analyze(parse('x+1=x'), -2, 2).solution_kind, 'Sin soluciones')

    def test_infinite_solutions_preserve_holes(self):
        for expression in ['x/x=1', '0*(1/x)=0']:
            result = analyze(parse(expression), -2, 2)
            self.assertEqual(result.solution_kind, 'Infinitas soluciones')
            self.assertEqual(result.singularities, [0])
            self.assertEqual(result.solutions, 'Union(Interval.open(-oo, 0), Interval.open(0, oo))')
        self.assertEqual(analyze(parse('x=x'), -2, 2).solutions, 'Reals')
        self.assertEqual(analyze(parse('sin(x)=0'), -2, 2).solution_kind, 'Infinitas soluciones')

    def test_invalid_equations_and_zero_power(self):
        for expression in ['0/0=0', '1/0=1/0', '0^0=1']:
            self.assertEqual(analyze(parse(expression), -1, 1).solution_kind, 'Ecuación indefinida')
        result = analyze(parse('0^x=0'), -1, 1)
        self.assertEqual(result.solutions, 'Interval.open(0, oo)')

    def test_domain_and_complex_cancellation(self):
        self.assertEqual(analyze(parse('sqrt(x)'), -2, 2).domain, 'Interval(0, 2)')
        self.assertEqual(analyze(parse('sqrt(-4)'), -2, 2).domain, 'EmptySet')
        self.assertEqual(analyze(parse('sqrt(-1)*sqrt(-1)'), -2, 2).domain, 'Interval(-2, 2)')
        self.assertEqual(len(analyze(parse('tan(x)'), -10, 10).singularities), 6)


class GeneticTests(unittest.TestCase):
    def test_reproducibility_limits_and_round_trip(self):
        first = TreeFactory(tuple(OPERATORS), seed=10)
        second = TreeFactory(tuple(OPERATORS), seed=10)
        for height in range(1, 13):
            for _ in range(12):
                tree = first.generate(height)
                self.assertEqual(tree, second.generate(height))
                self.assertLessEqual(tree.height, height)
                self.assertLessEqual(tree.size, 255)
                copy = Node.from_dict(json.loads(json.dumps(tree.to_dict())))
                self.assertEqual(tree, copy)
                parsed = parse(tree.to_expression(), height)
                a, b = evaluate(tree, 0.5), evaluate(parsed.left, 0.5)
                self.assertEqual(a.status, b.status)
                if a.finite:
                    self.assertAlmostEqual(a.value, b.value)

    def test_mutation_crossover_and_fitness(self):
        factory = TreeFactory(seed=42)
        tree = parse('x*x+1').left
        for _ in range(40):
            mutated = factory.mutate(tree, 6)
            self.assertLessEqual(mutated.height, 6)
            a, b = factory.crossover(tree, mutated, 6)
            self.assertLessEqual(a.height, 6)
            self.assertLessEqual(b.height, 6)
        self.assertEqual(mean_squared_error(tree, [0, 1, 2], [1, 2, 5]), 0)
        self.assertEqual(mean_squared_error(parse('1/0').left, [0], [0]), 1e12)
        self.assertEqual(tree.to_expression(), '((x * x) + 1)')

    def test_exported_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = generate_cases(directory, count=12, max_height=4, seed=5)
            data = json.loads(paths[0].read_text())
            self.assertEqual(len(data['random_cases']), 12)
            self.assertTrue(paths[1].exists())
            for case in data['random_cases'] + data['edge_cases']:
                self.assertLessEqual(parse(case['expression']).height, 4)
            self.assertEqual(len(list(Path(directory).iterdir())), 2)


class IntegrationTests(unittest.TestCase):
    def test_worker_delivers_samples_and_analysis(self):
        import multiprocessing as mp
        from expresiones.jobs import compute
        context = mp.get_context('spawn')
        messages = context.Queue()
        worker = context.Process(target=compute, args=(messages, parse('x/x=1'), Interval(-1, 1, 0.1), 'real'))
        worker.start()
        try:
            kind, samples = messages.get(timeout=10)
            self.assertEqual(kind, 'samples')
            self.assertEqual(len(samples.xs), 21)
            kind, analysis = messages.get(timeout=10)
            self.assertEqual(kind, 'analysis')
            self.assertEqual(analysis.solution_kind, 'Infinitas soluciones')
            kind, lines = messages.get(timeout=10)
            self.assertEqual(kind, 'limits')
            self.assertTrue(any('evitable' in line for line in lines))
            worker.join(timeout=3)
            self.assertEqual(worker.exitcode, 0)
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=3)
            messages.close()

    def test_render_without_display(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from expresiones.plotting import draw_function
        figure = Figure()
        canvas = FigureCanvasAgg(figure)
        samples = sample(parse('sqrt(x)').left, Interval(-2, 2, 0.1))
        draw_function(figure, samples, 'complex')
        canvas.draw()
        self.assertEqual(len(figure.axes), 1)
        self.assertEqual(figure.axes[0].lines[0].get_label(), 'Re(f(x))')

    def test_extreme_finite_values_can_render(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from expresiones.plotting import draw_function
        figure = Figure()
        canvas = FigureCanvasAgg(figure)
        samples = sample(parse('(1e100)^3 * 1e8 * x').left, Interval(-1, 1, 0.1))
        draw_function(figure, samples)
        canvas.draw()
        self.assertIn('1e+308', figure.axes[0].get_ylabel())

    def test_fit_plot_contains_csv_and_full_predicted_curve(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from expresiones.plotting import draw_fit
        figure = Figure()
        canvas = FigureCanvasAgg(figure)
        ax = draw_fit(figure, [0, 1], [1, 2], curve=([0, 0.5, 1], [1, 8, 2]))
        canvas.draw()
        self.assertEqual(len(ax.collections[0].get_offsets()), 2)
        self.assertGreater(ax.get_ylim()[1], 8)



class ImprovementTests(unittest.TestCase):
    def test_limits_classify_singularities(self):
        from expresiones.symbolic import analyze, limits
        def report(text):
            expression = parse(text)
            return limits(expression, analyze(expression, -3, 3).points)
        self.assertIn('evitable', report('sin(x)/x')[0])
        self.assertIn('vale 1', report('sin(x)/x')[0])
        self.assertIn('asíntota', report('1/x')[0])
        self.assertIn('salto', report('abs(x)/x')[0])
        self.assertIn('complejo', report('log(x)')[0])
        self.assertIn('oscila', report('sin(1/x)')[0])

    def test_constant_expression_is_reported(self):
        from expresiones.symbolic import analyze
        self.assertTrue(any('constante' in note for note in analyze(parse('x - x'), -1, 1).notes))

    def test_status_ranges_and_node_results(self):
        from expresiones.evaluation import evaluate_nodes
        samples = sample(parse('sqrt(x)').left, Interval(-1, 1, 0.5))
        self.assertEqual([(s.value, a, b, n) for s, a, b, n in samples.status_ranges()],
                         [('complejo', -1, -0.5, 2), ('real', 0, 1, 3)])
        results = evaluate_nodes(parse('1/x + sqrt(-4)').left, 0)
        self.assertEqual(results[(0,)].status, Status.UNDEFINED)
        self.assertEqual(results[(1,)].value, 2j)

    def test_batch_records_special_cases(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            json_path, _ = generate_cases(directory, 5, 4, 7)
            data = json.loads(Path(json_path).read_text(encoding='utf-8'))
        for case in data['random_cases']:
            self.assertEqual(sum(case['special_cases'].values()), 41)
            self.assertLessEqual(case['height'], 4)



class RegressionTests(unittest.TestCase):
    def test_load_points_formats(self):
        from expresiones.regression import load_points
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / 'a.csv'
            plain.write_text('# comentario\nx,y\n0,1\n1,3\n2,\n', encoding='utf-8')
            self.assertEqual(load_points(plain), ([0.0, 1.0], [1.0, 3.0], 1))
            european = Path(directory) / 'b.csv'
            european.write_text('x;y\n1,5;2,25\n2;4\n', encoding='utf-8')
            self.assertEqual(load_points(european)[:2], ([1.5, 2.0], [2.25, 4.0]))
            exported = Path(directory) / 'c.csv'
            exported.write_text('funcion,tipo,x,real,imaginaria\nf,funcion,0,5,0\nf,funcion,1,6,0\n', encoding='utf-8')
            self.assertEqual(load_points(exported)[:2], ([0.0, 1.0], [5.0, 6.0]))
            headless = Path(directory) / 'd.csv'
            headless.write_text('0 ,2\n1, 4\n', encoding='utf-8')
            self.assertEqual(load_points(headless)[:2], ([0.0, 1.0], [2.0, 4.0]))
            bad = Path(directory) / 'e.csv'
            bad.write_text('x,y\n1,a\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_points(bad)

    def test_random_search_improves_and_respects_limits(self):
        from expresiones.regression import RandomSearch, make_dataset, squared_error
        formula, xs, ys = make_dataset(seed=3, count=30, noise=0, formula='x^2 + 1')
        self.assertEqual(formula, '((x ** 2) + 1)')
        search = RandomSearch(xs, ys, ('+', '*', '-'), max_height=4, seed=1, keep=5)
        search.step(3000)
        ranking = search.ranking
        self.assertLessEqual(len(ranking), 5)
        self.assertEqual([c.mse for c in ranking], sorted(c.mse for c in ranking))
        self.assertTrue(all(c.tree.height <= 4 for c in ranking))
        self.assertEqual(len({c.expression for c in ranking}), len(ranking))
        self.assertAlmostEqual(ranking[0].mse, squared_error(ranking[0].tree, xs, ys))
        errors = [e for _, e in search.history]
        self.assertEqual(errors, sorted(errors, reverse=True))
        # El ajuste aleatorio mejora claramente a predecir la media.
        self.assertLess(ranking[0].mse, search.variance / 10)

    def test_invalid_predictions_are_discarded(self):
        from expresiones.regression import squared_error
        self.assertIsNone(squared_error(parse('sqrt(x)').left, [-1, 1], [0, 1]))
        self.assertIsNone(squared_error(parse('1/x').left, [0, 1], [0, 1]))
        self.assertEqual(squared_error(parse('x').left, [1, 2], [1, 4]), 2.0)

    def test_fit_csv_has_y_hat_and_metrics(self):
        import csv as csv_module
        from expresiones.regression import Candidate, write_fit_csv
        tree = parse('2*x').left
        with tempfile.TemporaryDirectory() as directory:
            path = write_fit_csv(Path(directory) / 'fit.csv', [0, 1, 2], [0, 2, 5], Candidate(1 / 3, '2*x', tree, 1))
            with path.open(encoding='utf-8') as file:
                rows = list(csv_module.DictReader(file))
        self.assertEqual([float(r['y_gorro']) for r in rows], [0, 2, 4])
        self.assertAlmostEqual(float(rows[0]['MSC_MSE']), 1 / 3)
        self.assertAlmostEqual(float(rows[0]['RMSE']), math.sqrt(1 / 3))

    def test_presets_are_written(self):
        from expresiones.regression import write_presets, write_test_points, load_points, PRESETS
        with tempfile.TemporaryDirectory() as directory:
            paths = write_presets(directory, count=20)
            self.assertEqual(len(paths), len(PRESETS) + 1)
            self.assertTrue(all(len(load_points(p)[0]) == 20 for p in paths))
            test_path = write_test_points(directory)
            xs, ys, skipped = load_points(test_path)
            self.assertEqual((len(xs), skipped), (81, 0))
            expected = [evaluate(parse('6.87 + 11*cos(7.23*x^3)').left, x).value.real for x in xs]
            self.assertTrue(all(abs(a - b) < 1e-12 for a, b in zip(ys, expected)))



class GeneticProgrammingTests(unittest.TestCase):
    def setUp(self):
        from expresiones.regression import make_dataset
        _, self.xs, self.ys = make_dataset(seed=1, count=25, noise=0, formula='x^2 - 2*x')

    def make(self, **options):
        from expresiones.gp import GeneticProgramming
        settings = dict(max_height=5, seed=3)
        settings.update(options)
        return GeneticProgramming(self.xs, self.ys, ('+', '-', '*', '/', 'sin', 'cos'), **settings)

    def test_step_1_and_2_population_and_evaluation(self):
        gp = self.make()
        population = gp.initialize()
        self.assertEqual(len(population), 100)
        self.assertTrue(all(i.tree.height <= 5 for i in population))
        self.assertEqual({i.tree.height for i in population} >= {2, 3}, True)   # alturas escalonadas
        self.assertGreater(len({i.expression for i in population}), 90)
        from expresiones.regression import squared_error
        # La aptitud es el MSE del fenotipo completo ŷ = a + b·f(x).
        for individual in population[:10]:
            expected = squared_error(individual.model, self.xs, self.ys)
            if expected is None:
                self.assertEqual(individual.mse, math.inf)
            else:
                self.assertAlmostEqual(individual.mse, expected, places=9)
        self.assertEqual(gp.history[0].generation, 0)
        self.assertEqual(len({i.signature for i in population}), 100)   # curvas distintas

    def test_step_3_keeps_height_and_improves(self):
        gp = self.make(max_height=4)
        gp.initialize()
        initial = gp.best.mse
        gp.run(25, target_mse=-1)        # sin parada temprana aunque encuentre error 0
        self.assertEqual(gp.generation, 25)
        self.assertTrue(all(i.tree.height <= 4 for i in gp.population))
        self.assertEqual(len(gp.population), 100)
        bests = [h.best for h in gp.history]
        self.assertEqual(bests, sorted(bests, reverse=True))   # con élite nunca empeora
        self.assertLess(gp.best.mse, initial)
        self.assertLess(gp.best.mse / gp.variance, 0.05)

    def test_tree_is_the_whole_model_and_random_seed(self):
        from expresiones.gp import GeneticProgramming
        tree = parse('x^2 - 2*x').left
        gp = self.make()
        mse = gp.fitness(parse('(x^2 - 2*x) / 7 + 3').left)
        self.assertGreater(mse, 0)  # no hay regresión que absorba escala/desplazamiento
        self.assertEqual(gp.fitness(tree), 0)
        seeds = {GeneticProgramming(self.xs, self.ys, ('+', '*')).seed for _ in range(5)}
        self.assertGreater(len(seeds), 1)                # sin semilla, cada ejecución es distinta
        first, second = self.make(seed=11), self.make(seed=11)
        first.run(3)
        second.run(3)
        self.assertEqual(first.best.expression, second.best.expression)   # con semilla, reproducible

    def test_diverse_ranking_and_stagnation_restart(self):
        gp = self.make(stagnation=2)
        gp.run(12)
        shown = gp.diverse_ranking(10)
        self.assertEqual(len({i.expression for i in shown}), len(shown))
        self.assertEqual([i.mse for i in shown], sorted(i.mse for i in shown))
        self.assertGreater(gp.restarts, 0)
        self.assertTrue(any('inmigrante' in i.origin or 'reinicio' in i.origin for i in gp.population))

    def test_selection_does_not_modify(self):
        gp = self.make()
        gp.initialize()
        before = [(i.expression, i.mse) for i in gp.population]
        self.assertEqual([i.mse for i in gp.population], sorted(i.mse for i in gp.population))
        for _ in range(100):
            self.assertIn(gp.select(), gp.population[:50])  # corte izquierdo
        gp.selection = 'torneo'
        self.assertIn(gp.select(), gp.population[:50])
        self.assertEqual(before, [(i.expression, i.mse) for i in gp.population])

    def test_crossover_dominant_and_reciprocal(self):
        from expresiones.gp import Individual
        gp = self.make()
        good = Individual(parse('(x * x) - x').left, 1.0)
        bad = Individual(parse('sin(x) + 3').left, 9.0)
        child, reciprocal = gp.crossover(bad, good)
        record = gp.last_crossover
        self.assertEqual(record.dominant, good.expression)     # el de menor error domina
        self.assertEqual(record.recessive, bad.expression)
        self.assertEqual((record.child, record.reciprocal), (child.to_expression(), reciprocal.to_expression()))
        self.assertTrue(child.height <= 5 and reciprocal.height <= 5)
        # Los nodos totales se conservan: solo se intercambian ramas.
        self.assertEqual(child.size + reciprocal.size, good.tree.size + bad.tree.size)

    def test_each_mutation_type(self):
        gp = self.make()
        tree = parse('(x - 3) / sin(x)').left
        switched = gp._mutate_intercambio(tree)
        self.assertIn(switched.to_expression(), ('(sin(x) / (x - 3))', '((3 - x) / sin(x))'))
        leaf = gp._mutate_hoja(tree)
        operator = gp._mutate_operador(tree)
        for point in (leaf, operator):
            self.assertEqual(point.size, tree.size)
            self.assertEqual([len(n.children) for _, n in point.walk()], [len(n.children) for _, n in tree.walk()])
        for _ in range(30):
            self.assertLessEqual(gp._mutate_subarbol(tree).height, 5)
        self.assertIsNone(gp._mutate_intercambio(parse('sin(x)').left))   # el hijo único es el izquierdo

    def test_mutation_limits_and_validation(self):
        from expresiones.gp import MUTATIONS
        self.assertEqual(set(self.make(mutations=tuple(MUTATIONS)).mutations), set(MUTATIONS))
        with self.assertRaises(ValueError):
            self.make(mutations=())
        with self.assertRaises(ValueError):
            self.make(max_height=1)
        gp = self.make(mutations=('intercambio',), mutation_rate=1.0, crossover_rate=0.0)
        gp.initialize()
        gp.step()
        self.assertEqual(set(gp.mutation_counts), {'intercambio'})

    def test_cosine_csv_is_recovered_by_tree_evolution(self):
        from expresiones.gp import GeneticProgramming
        from expresiones.regression import load_points, squared_error
        xs, ys, skipped = load_points(Path(__file__).resolve().parents[1] / 'datos_csv' / 'objetivo_coseno.csv')
        self.assertEqual(skipped, 0)
        gp = GeneticProgramming(xs, ys, ('+', '-', '*', '/', '**', 'sin', 'cos'),
                                max_height=6, population_size=100, seed=1, stagnation=100)
        best = gp.run(60)
        self.assertLess(best.mse, 0.001)
        self.assertAlmostEqual(best.mse, squared_error(best.tree, xs, ys), places=10)
        self.assertLessEqual(best.tree.height, 6)
        self.assertIn('cos', best.expression)

    def test_complex_predictions_are_penalized(self):
        gp = self.make()
        self.assertEqual(gp.fitness(parse('sqrt(-x)').left), math.inf)
        self.assertEqual(gp.fitness(parse('(-x)^0.5').left), math.inf)


if __name__ == '__main__':
    unittest.main()
