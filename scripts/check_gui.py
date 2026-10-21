"""Prueba de integración de la ventana; requiere una sesión gráfica."""
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


def parse_height(text):
    from expresiones.parser import parse
    return parse(text).height


def main():
    import tkinter as tk
    from expresiones.gui import ExpressionApp
    root = tk.Tk()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    app = ExpressionApp(root)

    def wait_for_analysis():
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            root.update()
            if app.initial_id is None and app.process is None:
                assert app.analysis is not None, app.status.get()
                assert not errors, errors
                return
            time.sleep(0.02)
        raise AssertionError('La interfaz no terminó en el tiempo esperado')

    try:
        wait_for_analysis()
        first_tree = app.tree_canvas.find_all()
        assert len(app.samples.xs) == 201
        assert len(app.table.get_children()) == 201
        app.expression_text.set('sqrt(x)')
        app.run()
        wait_for_analysis()
        assert first_tree != app.tree_canvas.find_all()
        assert app.samples.counts['complejo'] > 0
        app.mode.set('Real e imaginaria')
        app._plot()
        assert len(app.figure.axes[0].lines) >= 2
        app.expression_text.set('x^2+1=0')
        app.solution_domain.set('Complejos ℂ')
        app.run()
        wait_for_analysis()
        assert app.analysis.solutions == '{-I, I}'
        app.point.set('i')
        app.evaluate_point()
        assert 'Residuo: 0' in app.point_result.get()
        with tempfile.TemporaryDirectory() as directory:
            tree_path = str(Path(directory) / 'tree.json')
            csv_path = str(Path(directory) / 'samples.csv')
            with patch('expresiones.gui.filedialog.asksaveasfilename', return_value=tree_path):
                app.save_tree()
            assert Path(tree_path).exists()
            with patch('expresiones.gui.filedialog.asksaveasfilename', return_value=csv_path):
                app.save_csv()
            assert len(Path(csv_path).read_text().splitlines()) == 202
            app.expression_text.set('x')
            with patch('expresiones.gui.filedialog.askopenfilename', return_value=tree_path):
                app.load_tree()
            wait_for_analysis()
            assert app.analysis.solutions == '{-I, I}'
        app.expression_text.set('sin(')
        app.run()
        assert app.process is None
        assert 'inválida' in app.status.get()
        app.expression_text.set('x*x')
        app.height.set('1')
        app.run()
        assert 'altura' in app.status.get()
        app.height.set('5')
        app.random_tree()
        assert app.expression.height <= 5
        app.cancel()
        assert app.process is None
        assert 'cancelado' in app.status.get()
        app.expression_text.set('1/(x-0.25)^2')
        app.start.set('-2')
        app.end.set('2')
        app.step.set('0.1')
        app.mode.set('Solo reales')
        app.run()
        wait_for_analysis()
        assert app.analysis.singularities == [0.25]
        assert any('asíntota' in line for line in app.limit_lines), app.limit_lines
        assert 'singularidad en x = 0.25' in app.diagnosis.get(), app.diagnosis.get()
        # Nodo indefinido en x = 0.25: el borde y la etiqueta lo señalan.
        app.point.set('0.25')
        app.evaluate_point()
        assert any(result.status.value == 'indefinido' for _, _, result in app.tree_nodes.values())
        app.tree_canvas.update()
        tag = next(t for t, (path, _, _) in app.tree_nodes.items() if path == ())
        x0, y0, x1, y1 = app.tree_canvas.bbox(tag)
        app._select_node(type('E', (), {'x': (x0 + x1) / 2, 'y': (y0 + y1) / 2})())
        assert app.selected_path == () and 'Subárbol (raíz)' in app.node_info.get()
        # Vista combinada: árbol y gráfica a la vez, o uno solo.
        assert len(app.panes.panes()) == 2
        app.layout.set('Solo gráfica')
        app._apply_layout()
        assert len(app.panes.panes()) == 1
        app.layout.set('Árbol y gráfica')
        app._apply_layout()
        # Teclado, deslizador de altura y operadores genéticos.
        app.expression_text.set('')
        app._insert('sqrt()')
        app._insert('x')
        assert app.expression_text.get() == 'sqrt(x)'
        app.height_scale.set(4)
        root.update()
        assert app.height.get() == '4'
        app.expression_text.set('sin(x)/x')
        app.reference_text.set('x^2 + 1')
        app.mutate_tree()
        assert app.expression.height <= 4
        app.crossover_trees()
        assert app.expression.height <= 4 and parse_height(app.reference_text.get()) <= 4
        wait_for_analysis()
        app.expression_text.set('sin(x)/x')
        app.run()
        wait_for_analysis()
        assert any('evitable' in line and 'vale 1' in line for line in app.limit_lines), app.limit_lines
        # Métricas sobre la gráfica 2D, vistas 3D y CSV de cada función.
        app.reference_text.set('sin(x)')
        app.run()
        wait_for_analysis()
        assert any('NMSE' in t.get_text() for t in app.figure.axes[0].texts)
        app.dimension.set('3D curva')
        app._plot()
        assert app.figure.axes[0].name == '3d'
        app.dimension.set('3D superficie')
        app._plot()
        assert app.figure.axes[0].name == '3d' and app.figure.axes[0].collections
        app.dimension.set('2D')
        with tempfile.TemporaryDirectory() as directory:
            f_csv, g_csv = Path(directory) / 'f.csv', Path(directory) / 'g.csv'
            with patch('expresiones.gui.filedialog.asksaveasfilename', return_value=str(f_csv)):
                app.save_csv()
            with patch('expresiones.gui.filedialog.asksaveasfilename', return_value=str(g_csv)):
                app.save_csv('reference')
            header = f_csv.read_text(encoding='utf-8').splitlines()[0]
            assert all(name in header for name in ('MSC_MSE', 'RMSE', 'NMSE', 'error_cuadrado')), header
            assert 'sin(x)' in g_csv.read_text(encoding='utf-8').splitlines()[1]
        # Ajuste aleatorio a puntos de un CSV: ŷ, ranking, CSV y paso a f(x).
        app.fit_load(Path(__file__).resolve().parents[1] / 'datos_csv' / 'cuadratica.csv')
        assert len(app.fit_xs) == 60
        app.fit_method.set('Búsqueda aleatoria')
        app._fit_method_changed()
        app.fit_target.set('1500')
        app.height.set('4')
        app.fit_start()
        deadline = time.monotonic() + 30
        while app.fit_job is not None and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert app.fit_job is None and app.fit_search.iterations == 1500, app.fit_status.get()
        assert app.fit_search.best and len(app.fit_table.get_children()) == len(app.fit_search.best)
        assert 'mejor MSE' in app.fit_status.get()
        first = app.fit_table.get_children()[0]
        app.fit_table.selection_set(first)
        root.update()
        assert app.fit_selected is app.fit_rows[first]
        with tempfile.TemporaryDirectory() as directory:
            fit_csv = Path(directory) / 'fit.csv'
            with patch('expresiones.gui.filedialog.asksaveasfilename', return_value=str(fit_csv)):
                app.fit_save()
            assert fit_csv.read_text(encoding='utf-8').startswith('x,y,y_gorro')
        # Programación genética: 3 pasos, cruza dominante/recíproca y mutaciones.
        app.fit_selected = None
        app.fit_method.set('Programación genética')
        app._fit_method_changed()
        app.gp_params['generations'].set('15')
        app.fit_seed.set('7')
        app.fit_start()
        deadline = time.monotonic() + 60
        while app.fit_job is not None and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert app.fit_search.generation == 15 and len(app.fit_search.population) == 100, app.fit_status.get()
        assert 'Evolución terminada' in app.fit_status.get() and 'dominante' in app.fit_genes.get(), app.fit_genes.get()
        assert app.fit_table.heading('iteration')['text'] == 'Generación'
        for name in ('subarbol', 'hoja', 'operador', 'intercambio'):
            app.gp_mutations[name].set(True)
        assert all(variable.get() for variable in app.gp_mutations.values())
        app.fit_start()                       # continúa la misma población
        while app.fit_job is not None and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert app.fit_search.generation == 30
        app.fit_table.selection_set(app.fit_table.get_children()[0])
        root.update()
        app.fit_use()
        assert app.expression_text.get() == app.fit_selected.model.to_expression() if hasattr(app.fit_selected, 'model') else app.fit_selected.expression
        wait_for_analysis()
        app.seed.set('5')
        before = set(p.name for p in (Path(__file__).resolve().parents[1] / 'datos_csv').glob('aleatoria_*.csv'))
        app.fit_random_data()
        created = set(p.name for p in (Path(__file__).resolve().parents[1] / 'datos_csv').glob('aleatoria_*.csv')) - before
        assert len(created) == 1 and app.fit_xs is not None
        for name in created:
            (Path(__file__).resolve().parents[1] / 'datos_csv' / name).unlink()
        # Ventana a pantalla completa por geometría (niri ignora -fullscreen en Xwayland).
        assert app.root.winfo_width() >= app.root.winfo_screenwidth() * 0.9, app.root.winfo_width()
        root.update()
        assert not errors, errors
        print('GUI OK: cambio de expresión, árbol, gráfica, complejos, solver, exportación/importación, errores, altura, cancelación,'
              ' límites, estados por nodo, vista combinada, teclado, deslizador de altura, mutación, cruce,'
              ' métricas en la gráfica, 3D curva y superficie, CSV de f y g, ventana a pantalla completa, ajuste aleatorio y genético a CSV.')
    finally:
        app.close()


if __name__ == '__main__':
    main()
