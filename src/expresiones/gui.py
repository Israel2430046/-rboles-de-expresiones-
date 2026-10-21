"""Ventana de escritorio; el motor matemático no depende de este módulo."""
from pathlib import Path
import json
import math
from datetime import datetime
import multiprocessing as mp
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog
from tkinter.scrolledtext import ScrolledText
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from .parser import parse, Expression
from .tree import Node, validate_size, MAX_HEIGHT
from .evaluation import evaluate, evaluate_nodes, Status
from .sampling import Interval, complex_grid, sample
from .genetics import TreeFactory, DEFAULT_OPERATORS
from .operators import OPERATORS
from .cases import generate_cases
from .plotting import draw_function, draw_surface, draw_fit
from .gp import GeneticProgramming, MUTATIONS, DEFAULT_MUTATIONS
from .regression import RandomSearch, load_points, make_dataset, predict, write_fit_csv, write_points, write_test_points
from .jobs import compute
from .exporting import write_function_csv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "datos_csv"
EXAMPLES = (
    "sin(x) + x/3", "sqrt(x)", "sqrt(-4)", "1/x", "1/(x-0.25)^2",
    "tan(x)", "log(x)", "exp(i*x)", "0/0", "0^0", "exp(1000)",
    "x^2+1 = 0", "x/x = 1", "sin(x) = 0", "x+1 = x",
)
LAYOUTS = ("Árbol y gráfica", "Solo gráfica", "Solo árbol")
VIEWS = ("2D", "3D curva", "3D superficie")
STATUS_COLORS = {Status.COMPLEX: "#9333ea", Status.UNDEFINED: "#dc2626", Status.INDETERMINATE: "#ea580c", Status.OVERFLOW: "#ca8a04"}
KIND_COLORS = {"operator": "#2563eb", "variable": "#0f766e", "constant": "#475569", "number": "#475569"}
KEYPAD = (
    ("+", " + "), ("−", " - "), ("×", "*"), ("÷", "/"), ("^", "^"), ("(", "("), (")", ")"),
    ("x", "x"), ("π", "pi"), ("e", "e"), ("i", "i"), ("=", " = "), ("√", "sqrt()"), ("ln", "log()"),
    ("sin", "sin()"), ("cos", "cos()"), ("tan", "tan()"), ("exp", "exp()"), ("|x|", "abs()"), ("C", None), ("⌫", "back"),
)


def _short(result):
    """Valor compacto para la etiqueta de un nodo."""
    if not result.finite:
        return result.status.value
    z = result.value
    return f"{z.real:.4g}" if z.imag == 0 else f"{z.real:.3g}{z.imag:+.3g}i"


HELP = """ESCRIBIR UNA EXPRESIÓN
Usa x como variable, punto decimal y * para multiplicar: 2*x, sin(x), sqrt(-4).
Potencias: x^2 o x**2. Las funciones llevan paréntesis. Ángulos en radianes.
Constantes: pi (también π), e, i (también j). Alias: ln, sen.
Solo se admiten los operadores del catálogo. No se ejecuta código Python.

ÁRBOLES
Una hoja tiene altura 1; cada operación agrega un nivel. El signo = agrega
un nivel al árbol de una ecuación. La altura máxima se aplica a la entrada,
la importación y la generación, con un límite global de 12 y 255 nodos.
Las funciones tienen un hijo; los operadores binarios tienen dos.

COMPLEJOS, INDEFINIDOS E INFINITOS
sqrt(-4) = 2i. La vista real omite los valores con parte imaginaria distinta
de cero. «Real e imaginaria» dibuja ambas componentes contra un x real.
Las raíces y logaritmos usan la rama principal compleja; cbrt toma la raíz
real si su argumento es real. Para otros índices usa potencias fraccionarias.
1/0 no es un número infinito: es indefinido. 0/0 y 0^0 se marcan como
indeterminados. El análisis calcula los límites laterales en cada singularidad
(evitable, polo, salto u oscilación) y el comportamiento en ±∞; sin(x)/x → 1. Un desbordamiento de máquina tampoco demuestra un infinito.
Las operaciones inválidas de los subárboles se conservan aunque se cancelen.

ECUACIONES Y DOMINIO
Con = se resuelve la igualdad en ℝ o ℂ. La gráfica muestra el residuo
izquierda - derecha; sus ceros corresponden a soluciones donde está definido.
Las soluciones se buscan en todo el conjunto seleccionado, no solo dentro
del intervalo de dibujo. Un conjunto condicionado significa «no resuelto».
El dominio mostrado es el de continuidad real en el intervalo; puede no
incluir puntos reales aislados. El análisis puede ser inconcluyente.

MUESTREO
Inicio < fin; paso > 0; máximo 5000 muestras. Se incluye el extremo final;
el último segmento puede ser menor que el paso. La evaluación usa precisión
de máquina. Se cortan polos conocidos y saltos detectados entre muestras.
Una gráfica muestreada no garantiza descubrir cada discontinuidad u
oscilación. Reduce el paso para explorar un tramo con más detalle.
El trabajo se ejecuta en otro proceso, cancelable, con un límite de 15 s.

PRUEBAS Y PROGRAMACIÓN GENÉTICA
Selecciona operadores para generar árboles aleatorios. La semilla permite
reproducir una secuencia. «Guardar lote» crea JSON y TXT en ecuaciones_prueba/,
incluyendo casos límite que caben en la altura seleccionada. Los casos límite
pueden usar otros operadores. No se descartan expresiones indefinidas.
El módulo genetics ofrece generación, mutación, cruce y fitness; tree ofrece
serialización y sustitución de subárboles sin depender de la interfaz.
"""


class ExpressionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Laboratorio de árboles de expresión")
        self.root.geometry("1300x850")
        self.root.minsize(900, 600)
        self.process = self.messages = None
        self.poll_id = None
        self.samples = self.expression = self.analysis = None
        self.reference = self.reference_samples = self.metrics = None
        self.interval = None
        self.run_signature = None
        self.pending_csv = None
        self.fullscreen = True
        self.controls_visible = True
        self.factory = self.factory_signature = None
        self.expression_text = tk.StringVar(value=EXAMPLES[0])
        self.start = tk.StringVar(value="-10")
        self.end = tk.StringVar(value="10")
        self.step = tk.StringVar(value="0.1")
        self.height = tk.StringVar(value="8")
        self.point = tk.StringVar(value="0")
        self.mode = tk.StringVar(value="Solo reales")
        self.dimension = tk.StringVar(value="2D")
        self.layout = tk.StringVar(value=LAYOUTS[0])
        self.diagnosis = tk.StringVar(value="")
        self.node_info = tk.StringVar(value="Haz clic en un nodo para resaltar su subárbol y ver su valor en el punto x elegido.")
        self.height_info = tk.StringVar(value="")
        self.limit_lines = None
        self.selected_path = None
        self.tree_nodes = {}
        self.reference_text = tk.StringVar(value="sin(x)")
        self.show_reference = tk.BooleanVar(value=True)
        self.metrics_summary = tk.StringVar(value="MSC/MSE: —     RMSE: —     NMSE: —")
        self.metric_values = {name: tk.StringVar(value="—") for name in ("mse", "rmse", "nmse")}
        self.metric_notes = tk.StringVar(value="Define g(x) y analiza para comparar ambas funciones.")
        self.solution_domain = tk.StringVar(value="Reales ℝ")
        self.seed = tk.StringVar(value="42")
        self.count = tk.StringVar(value="30")
        self.status = tk.StringVar(value="Listo. Escribe una expresión o elige un ejemplo.")
        self.stats = tk.StringVar(value="")
        self.point_result = tk.StringVar(value="")
        self.operator_vars = {name: tk.BooleanVar(value=name in DEFAULT_OPERATORS) for name in OPERATORS}
        self._build()
        self.height.trace_add("write", self._height_changed)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Return>", lambda event: self.run())
        self.root.bind("<F11>", lambda event: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda event: self.restore_window())
        self._fill_screen(True)
        self.initial_id = self.root.after(200, self._initial_run)

    def _initial_run(self):
        self.initial_id = None
        self._split_panes()
        self.run()

    def _build(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f1f5f9")
        style.configure("TLabel", background="#f1f5f9", foreground="#0f172a", font=("DejaVu Sans", 10))
        style.configure("TButton", padding=(10, 7), font=("DejaVu Sans", 10))
        style.configure("Accent.TButton", background="#2563eb", foreground="white")
        style.configure("Key.TButton", padding=(1, 4), font=("DejaVu Sans Mono", 10))
        style.map("Accent.TButton", background=[("active", "#1d4ed8")])
        style.configure("TNotebook", background="#f1f5f9", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 9))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#2563eb")])
        style.configure("Treeview", rowheight=28, font=("DejaVu Sans", 10))
        style.configure("Treeview.Heading", font=("DejaVu Sans", 10, "bold"), padding=6)
        style.configure("TLabelframe", background="#f1f5f9")
        style.configure("TLabelframe.Label", background="#f1f5f9", foreground="#475569")
        header = tk.Frame(self.root, background="#0f172a", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(header, text="LABORATORIO / EXPRESIONES", font=("DejaVu Sans", 16, "bold"), foreground="white", background="#0f172a").pack(side="left")
        ttk.Button(header, text="Salir", command=self.close).pack(side="right", padx=(8, 0))
        self.fullscreen_button = ttk.Button(header, text="Ventana · F11", command=self.toggle_fullscreen)
        self.fullscreen_button.pack(side="right")
        self.controls_button = ttk.Button(header, text="Ocultar controles", command=self.toggle_controls)
        self.controls_button.pack(side="right", padx=8)
        self.body = ttk.Frame(self.root)
        self.body.pack(fill="both", expand=True)
        self.sidebar = ttk.Frame(self.body, padding=(10, 10, 0, 8))
        self.sidebar.pack(side="left", fill="y")
        side_canvas = tk.Canvas(self.sidebar, width=295, background="#f1f5f9", highlightthickness=0)
        side_scroll = ttk.Scrollbar(self.sidebar, orient="vertical", command=side_canvas.yview)
        side_canvas.configure(yscrollcommand=side_scroll.set)
        side_scroll.pack(side="right", fill="y")
        side_canvas.pack(side="left", fill="both", expand=True)
        controls = ttk.Frame(side_canvas, padding=(0, 0, 10, 8))
        side_window = side_canvas.create_window(0, 0, anchor="nw", window=controls)
        controls.bind("<Configure>", lambda event: side_canvas.configure(scrollregion=side_canvas.bbox("all")))
        side_canvas.bind("<Configure>", lambda event: side_canvas.itemconfigure(side_window, width=event.width))

        def section(title):
            ttk.Label(controls, text=title, font=("DejaVu Sans", 10, "bold"), foreground="#64748b").pack(anchor="w", pady=(16, 7))

        section("01 / FUNCIÓN")
        ttk.Label(controls, text="f(x) o ecuación").pack(anchor="w")
        self.entry = ttk.Entry(controls, textvariable=self.expression_text, font=("DejaVu Sans Mono", 12))
        self.entry.pack(fill="x", pady=(5, 6))
        keypad = ttk.Frame(controls)
        keypad.pack(fill="x", pady=(0, 8))
        for index, (label, text) in enumerate(KEYPAD):
            ttk.Button(keypad, text=label, width=3, style="Key.TButton", command=lambda t=text: self._insert(t)).grid(row=index // 7, column=index % 7, sticky="ew", padx=1, pady=1)
        for column in range(7):
            keypad.columnconfigure(column, weight=1)
        self.run_button = ttk.Button(controls, text="Analizar y graficar", command=self.run, style="Accent.TButton")
        self.run_button.pack(fill="x")
        self.csv_button = ttk.Button(controls, text="Generar CSV de f(x)", command=self.save_csv)
        self.csv_button.pack(fill="x", pady=6)
        examples = ttk.Combobox(controls, values=EXAMPLES, state="readonly")
        examples.set("Elegir un ejemplo…")
        examples.pack(fill="x", pady=4)
        examples.bind("<<ComboboxSelected>>", lambda event: self._use_example(examples.get()))
        section("02 / MUESTREO Y ÁRBOL")
        fields = ttk.Frame(controls)
        fields.pack(fill="x")
        for row, (label, variable) in enumerate((("Inicio", self.start), ("Fin", self.end), ("Paso", self.step), ("Altura máxima", self.height))):
            ttk.Label(fields, text=label).grid(row=row, column=0, sticky="w", pady=4)
            widget = ttk.Spinbox(fields, from_=1, to=12, textvariable=variable, width=12) if variable is self.height else ttk.Entry(fields, textvariable=variable, width=12)
            widget.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=4)
        fields.columnconfigure(1, weight=1)
        self.height_scale = tk.Scale(controls, from_=1, to=MAX_HEIGHT, resolution=1, orient="horizontal", showvalue=False, background="#f1f5f9",
                                     highlightthickness=0, troughcolor="#cbd5e1", command=lambda value: self.height.set(str(int(float(value)))))
        self.height_scale.set(int(self.height.get()))
        self.height_scale.pack(fill="x")
        ttk.Label(controls, textvariable=self.height_info, wraplength=265, foreground="#64748b", font=("DejaVu Sans", 9)).pack(anchor="w")
        ttk.Label(controls, text="Soluciones de ecuaciones en").pack(anchor="w", pady=(8, 4))
        ttk.Combobox(controls, textvariable=self.solution_domain, values=["Reales ℝ", "Complejos ℂ"], state="readonly").pack(fill="x")
        section("03 / REFERENCIA Y MÉTRICAS")
        ttk.Label(controls, text="g(x) · referencia editable").pack(anchor="w")
        ttk.Entry(controls, textvariable=self.reference_text, font=("DejaVu Sans Mono", 11)).pack(fill="x", pady=5)
        ttk.Checkbutton(controls, text="Mostrar referencia en gráfica", variable=self.show_reference, command=self._plot).pack(anchor="w")
        ttk.Button(controls, text="Comparar / calcular métricas", command=self.run).pack(fill="x", pady=5)
        ttk.Button(controls, text="Generar CSV de g(x)", command=lambda: self.save_csv("reference")).pack(fill="x")
        ttk.Label(controls, text="Deja g(x) vacía para explorar solo f(x).", wraplength=265, foreground="#64748b", font=("DejaVu Sans", 9)).pack(anchor="w", pady=5)
        section("04 / GENERACIÓN ALEATORIA")
        row = ttk.Frame(controls)
        row.pack(fill="x")
        ttk.Label(row, text="Semilla").pack(side="left")
        ttk.Entry(row, textvariable=self.seed, width=7).pack(side="left", padx=7)
        ttk.Label(row, text="Cantidad").pack(side="left")
        ttk.Spinbox(row, from_=1, to=500, textvariable=self.count, width=5).pack(side="left", padx=5)
        ttk.Button(controls, text="Árbol aleatorio", command=self.random_tree).pack(fill="x", pady=(8, 4))
        genetic = ttk.Frame(controls)
        genetic.pack(fill="x", pady=4)
        ttk.Button(genetic, text="Mutar f(x)", command=self.mutate_tree).pack(side="left", expand=True, fill="x")
        ttk.Button(genetic, text="Cruzar f × g", command=self.crossover_trees).pack(side="left", expand=True, fill="x", padx=(4, 0))
        ttk.Button(controls, text="Guardar lote de ecuaciones", command=self.save_batch).pack(fill="x", pady=4)
        ttk.Button(controls, text="Importar árbol JSON", command=self.load_tree).pack(fill="x", pady=(8, 4))
        ttk.Button(controls, text="Exportar árbol JSON", command=self.save_tree).pack(fill="x", pady=4)
        ttk.Button(controls, text="Cancelar cálculo", command=self.cancel).pack(fill="x", pady=8)
        self.workspace = ttk.Frame(self.body, padding=12)
        self.workspace.pack(side="left", fill="both", expand=True)
        ttk.Label(self.workspace, textvariable=self.metrics_summary, foreground="#1d4ed8", font=("DejaVu Sans", 11, "bold"), wraplength=1000).pack(anchor="w")
        ttk.Label(self.workspace, textvariable=self.diagnosis, foreground="#b91c1c", font=("DejaVu Sans", 10), wraplength=1100).pack(anchor="w", pady=(2, 8))
        notebook = ttk.Notebook(self.workspace)
        self.notebook = notebook
        notebook.pack(fill="both", expand=True)
        visual = ttk.Frame(notebook)
        notebook.add(visual, text="Árbol y gráfica")
        plot_controls = ttk.Frame(visual, padding=(8, 8))
        plot_controls.pack(fill="x")
        ttk.Label(plot_controls, text="Mostrar").pack(side="left", padx=(0, 5))
        layout = ttk.Combobox(plot_controls, textvariable=self.layout, values=LAYOUTS, state="readonly", width=15)
        layout.pack(side="left", padx=(0, 12))
        layout.bind("<<ComboboxSelected>>", self._apply_layout)
        ttk.Label(plot_controls, text="Vista").pack(side="left", padx=(0, 5))
        dimension = ttk.Combobox(plot_controls, textvariable=self.dimension, values=VIEWS, state="readonly", width=13)
        dimension.pack(side="left", padx=(0, 8))
        dimension.bind("<<ComboboxSelected>>", lambda event: self._plot())
        self.mode_widget = ttk.Combobox(plot_controls, textvariable=self.mode, values=("Solo reales", "Real e imaginaria"), state="readonly", width=18)
        self.mode_widget.pack(side="left")
        self.mode_widget.bind("<<ComboboxSelected>>", lambda event: self._plot())
        ttk.Button(plot_controls, text="CSV de g(x)", command=lambda: self.save_csv("reference")).pack(side="right", padx=(6, 0))
        ttk.Button(plot_controls, text="CSV de f(x)", command=self.save_csv, style="Accent.TButton").pack(side="right")
        self.plot_hint = tk.StringVar(value="Zoom, desplazamiento y guardado de imagen en la barra inferior.")
        ttk.Label(visual, textvariable=self.plot_hint, foreground="#64748b", font=("DejaVu Sans", 9), wraplength=950).pack(anchor="w", padx=10)
        self.panes = ttk.PanedWindow(visual, orient="horizontal")
        self.panes.pack(fill="both", expand=True)
        tree_frame = ttk.Frame(self.panes, padding=(4, 0, 8, 4))
        graph = ttk.Frame(self.panes)
        self.tree_pane, self.graph_pane = tree_frame, graph
        self.panes.add(tree_frame, weight=2)
        self.panes.add(graph, weight=3)
        self.figure = Figure(figsize=(9, 6), dpi=100)
        self.plot_canvas = FigureCanvasTkAgg(self.figure, master=graph)
        self.toolbar = NavigationToolbar2Tk(self.plot_canvas, graph, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="bottom", fill="x")
        self.plot_canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        legend = ttk.Frame(tree_frame)
        legend.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        point_bar = ttk.Frame(legend)
        point_bar.pack(anchor="w", pady=(0, 4))
        ttk.Label(point_bar, text="Árbol de expresión", font=("DejaVu Sans", 10, "bold")).pack(side="left", padx=(0, 12))
        ttk.Label(point_bar, text="valores en x =").pack(side="left", padx=(0, 5))
        point_entry = ttk.Entry(point_bar, textvariable=self.point, width=8)
        point_entry.pack(side="left")
        point_entry.bind("<Return>", lambda event: (self.evaluate_point(), "break")[1])
        ttk.Button(point_bar, text="Evaluar", command=self.evaluate_point).pack(side="left", padx=4)
        kinds = ttk.Frame(legend)
        kinds.pack(anchor="w")
        for text, color in (("operador", KIND_COLORS["operator"]), ("variable", KIND_COLORS["variable"]), ("constante", KIND_COLORS["number"])):
            tk.Label(kinds, text=f"● {text}", fg=color, bg="#f1f5f9", font=("DejaVu Sans", 9)).pack(side="left", padx=3)
        borders = ttk.Frame(legend)
        borders.pack(anchor="w")
        tk.Label(borders, text="Borde:", fg="#64748b", bg="#f1f5f9", font=("DejaVu Sans", 9)).pack(side="left")
        for status, color in STATUS_COLORS.items():
            tk.Label(borders, text=f"○ {status.value}", fg=color, bg="#f1f5f9", font=("DejaVu Sans", 9, "bold")).pack(side="left", padx=3)
        self.tree_canvas = tk.Canvas(tree_frame, background="#f8fafc", highlightthickness=0)
        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree_canvas.xview)
        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_canvas.yview)
        self.tree_canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.tree_canvas.grid(row=1, column=0, sticky="nsew")
        yscroll.grid(row=1, column=1, sticky="ns")
        xscroll.grid(row=2, column=0, sticky="ew")
        ttk.Label(tree_frame, textvariable=self.node_info, wraplength=480, foreground="#334155", font=("DejaVu Sans", 9)).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        tree_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree_canvas.bind("<Configure>", lambda event: self._draw_tree() if self.expression else None)
        self.tree_canvas.bind("<Button-1>", self._select_node)
        table_frame = ttk.Frame(notebook, padding=8)
        notebook.add(table_frame, text="Datos / CSV")
        table_buttons = ttk.Frame(table_frame)
        table_buttons.pack(anchor="w", pady=(0, 8))
        ttk.Button(table_buttons, text="Generar CSV de f(x)", command=self.save_csv, style="Accent.TButton").pack(side="left")
        ttk.Button(table_buttons, text="Generar CSV de g(x)", command=lambda: self.save_csv("reference")).pack(side="left", padx=6)
        ttk.Label(table_buttons, text="El CSV de f(x) incluye g(x), el error cuadrático de cada punto y MSC/MSE, RMSE y NMSE.", foreground="#64748b").pack(side="left", padx=8)
        table_inner = ttk.Frame(table_frame)
        table_inner.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_inner, columns=("x", "real", "imag", "status", "detail"), show="headings")
        for column, label, width in [("x", "x", 110), ("real", "Parte real", 140), ("imag", "Parte imaginaria", 140), ("status", "Estado", 130), ("detail", "Detalle", 500)]:
            self.table.heading(column, text=label)
            self.table.column(column, width=width)
        scroll = ttk.Scrollbar(table_inner, orient="vertical", command=self.table.yview)
        horizontal = ttk.Scrollbar(table_inner, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_inner.rowconfigure(0, weight=1)
        table_inner.columnconfigure(0, weight=1)
        metric_frame = ttk.Frame(notebook, padding=18)
        notebook.add(metric_frame, text="Métricas")
        cards = ttk.Frame(metric_frame)
        cards.pack(fill="x", pady=(0, 18))
        for column, (name, label) in enumerate((("mse", "MSC / MSE / ECM"), ("rmse", "RMSE"), ("nmse", "NMSE"))):
            card = tk.Frame(cards, bg="white", padx=16, pady=18, highlightbackground="#e2e8f0", highlightthickness=1)
            card.grid(row=0, column=column, sticky="nsew", padx=5)
            cards.columnconfigure(column, weight=1)
            tk.Label(card, text=label, bg="white", fg="#64748b", font=("DejaVu Sans", 10, "bold")).pack(anchor="w")
            tk.Label(card, textvariable=self.metric_values[name], bg="white", fg="#2563eb", font=("DejaVu Sans", 19, "bold")).pack(anchor="w", pady=(10, 0))
        ttk.Label(metric_frame, textvariable=self.metric_notes, wraplength=800, justify="left").pack(anchor="w", pady=8)
        formulas = "MSC = MSE = (1/n) Σ |f(xᵢ) − g(xᵢ)|²\nRMSE = √MSE\nNMSE = MSE / [(1/n) Σ |g(xᵢ) − media(g)|²]\n\nSe usan los mismos puntos x para ambas funciones.\nLos pares indefinidos o desbordados se excluyen y se cuentan.\nPara complejos, |f − g|² = (Re(f − g))² + (Im(f − g))².\nUna referencia constante tiene NMSE no definido (varianza cero).\nLas métricas no cambian al ocultar la referencia o cambiar la vista."
        formula_text = ScrolledText(metric_frame, height=12, wrap="word", font=("DejaVu Sans", 11), padx=14, pady=14, relief="flat")
        formula_text.pack(fill="both", expand=True, pady=12)
        formula_text.insert("1.0", formulas)
        formula_text.configure(state="disabled")
        metric_buttons = ttk.Frame(metric_frame)
        metric_buttons.pack(anchor="w")
        ttk.Button(metric_buttons, text="Generar CSV de f(x) con métricas", command=self.save_csv, style="Accent.TButton").pack(side="left")
        ttk.Button(metric_buttons, text="Generar CSV de g(x)", command=lambda: self.save_csv("reference")).pack(side="left", padx=6)
        analysis_frame = ttk.Frame(notebook, padding=12)
        notebook.add(analysis_frame, text="Análisis")
        point_row = ttk.Frame(analysis_frame)
        point_row.pack(fill="x", pady=(0, 12))
        ttk.Label(point_row, text="Evaluar en x =").pack(side="left", padx=(0, 6))
        ttk.Entry(point_row, textvariable=self.point, width=12).pack(side="left")
        ttk.Button(point_row, text="Evaluar punto", command=self.evaluate_point).pack(side="left", padx=6)
        ttk.Label(analysis_frame, textvariable=self.point_result, wraplength=850).pack(anchor="w", pady=5)
        self.analysis_text = ScrolledText(analysis_frame, wrap="word", font=("DejaVu Sans", 11), padx=12, pady=12, relief="flat")
        self.analysis_text.pack(fill="both", expand=True, pady=8)
        self._analysis_message("El análisis de dominio y soluciones aparecerá aquí.")
        operators = ttk.Frame(notebook, padding=12)
        notebook.add(operators, text="Operadores")
        op_canvas = tk.Canvas(operators, background="#f1f5f9", highlightthickness=0)
        op_scroll = ttk.Scrollbar(operators, orient="vertical", command=op_canvas.yview)
        op_canvas.configure(yscrollcommand=op_scroll.set)
        op_scroll.pack(side="right", fill="y")
        op_canvas.pack(side="left", fill="both", expand=True)
        op_inner = ttk.Frame(op_canvas, padding=8)
        op_canvas.create_window(0, 0, window=op_inner, anchor="nw")
        op_inner.bind("<Configure>", lambda event: op_canvas.configure(scrollregion=op_canvas.bbox("all")))
        ttk.Label(op_inner, text="Biblioteca de operadores válidos", font=("DejaVu Sans", 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(op_inner, text="Todos se aceptan al escribir. Los marcados se usan al generar, mutar y cruzar árboles.", foreground="#64748b").grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 8))
        selection = ttk.Frame(op_inner)
        selection.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 10))
        for text, names in (("Todos", tuple(OPERATORS)), ("Ninguno", ()), ("Por defecto", DEFAULT_OPERATORS)):
            ttk.Button(selection, text=text, command=lambda names=names: self._select_operators(names)).pack(side="left", padx=(0, 6))
        for column, text in enumerate(("Operador", "Tipo", "Descripción · ejemplo")):
            ttk.Label(op_inner, text=text, font=("DejaVu Sans", 10, "bold"), foreground="#475569").grid(row=3, column=column, sticky="w", padx=(0, 18))
        for row, (name, spec) in enumerate(OPERATORS.items(), 4):
            ttk.Checkbutton(op_inner, text="** (^)" if name == "**" else name, variable=self.operator_vars[name]).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=4)
            ttk.Label(op_inner, text="binario" if spec.arity == 2 else "unario").grid(row=row, column=1, sticky="w", padx=(0, 18))
            ttk.Label(op_inner, text=f"{spec.description} · {spec.example}", wraplength=480).grid(row=row, column=2, sticky="w")
        ttk.Label(op_inner, text="Variable: x · Constantes: pi (π), e, i (j) · Alias: ln → log, sen → sin, ^ → **", foreground="#64748b").grid(row=len(OPERATORS) + 4, column=0, columnspan=3, sticky="w", pady=(12, 0))
        self._build_fit_tab(notebook)
        help_frame = ttk.Frame(notebook)
        notebook.add(help_frame, text="Guía")
        help_text = ScrolledText(help_frame, wrap="word", font=("DejaVu Sans", 11), padx=16, pady=12)
        help_text.pack(fill="both", expand=True)
        help_text.insert("1.0", HELP + "\nVISTAS Y EXPORTACIÓN\nLa aplicación inicia a pantalla completa. F11 alterna; Escape restaura.\nOculta los controles para ampliar la gráfica. El árbol y la gráfica se ven juntos;\n«Mostrar» elige ambos o uno solo, y la división central se arrastra.\nCada nodo muestra el valor de su subárbol en el punto x; el borde indica complejo,\nindefinido, indeterminado o desbordamiento. Un clic resalta el subárbol.\nEl teclado bajo f(x) inserta operadores en la posición del cursor.\n«Mutar» y «Cruzar f × g» aplican los operadores genéticos con la altura máxima.\n«3D curva» representa (x, Re(f(x)), Im(f(x))) con x real; gira con el ratón.\nUna función real queda en el plano Im=0.\n«3D superficie» evalúa f en el plano complejo z = a + bi: altura |f(z)| y color\nsegún la fase. Así se ven los polos (picos) y los ceros (valles), también complejos.\nEn niri y otros escritorios en mosaico la ventana ocupa la pantalla completa; F11\nalterna con una ventana más pequeña.\nCada función tiene su botón de CSV: junto a la gráfica, en Datos / CSV y en Métricas.\nGenerar CSV analiza la entrada actual si cambió, y conserva los estados inválidos.\nEl CSV de f(x) incluye comparación y métricas si se definió g(x).\n")
        help_text.configure(state="disabled")
        ttk.Label(self.workspace, textvariable=self.stats, foreground="#475569", wraplength=1100).pack(anchor="w", pady=(8, 4))
        ttk.Label(self.workspace, textvariable=self.status, foreground="#1d4ed8", wraplength=1100).pack(anchor="w")

    def _fill_screen(self, full):
        """Ocupa toda la pantalla, también en compositores en mosaico.

        niri (vía xwayland-satellite) y otros compositores ignoran -fullscreen y
        -zoomed de Tk y dejan la ventana como una columna a media pantalla; fijar
        la geometría al tamaño de la pantalla sí la hace ocupar todo el espacio.
        """
        width, height = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        try:
            self.root.attributes("-fullscreen", full)
        except tk.TclError:
            pass
        if full:
            self.root.geometry(f"{width}x{height}+0+0")
        else:
            self.root.geometry(f"{int(width * 0.75)}x{int(height * 0.8)}+{width // 8}+{height // 10}")

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self._fill_screen(self.fullscreen)
        self.fullscreen_button.configure(text="Ventana · F11" if self.fullscreen else "Pantalla completa · F11")
        return "break"

    def restore_window(self):
        if self.fullscreen:
            self.toggle_fullscreen()
        return "break"

    def toggle_controls(self):
        self.controls_visible = not self.controls_visible
        if self.controls_visible:
            self.sidebar.pack(side="left", fill="y", before=self.workspace)
        else:
            self.sidebar.pack_forget()
        self.controls_button.configure(text="Ocultar controles" if self.controls_visible else "Mostrar controles")

    def _insert(self, text):
        """Teclado de la barra lateral: inserta en el cursor del campo f(x)."""
        entry = self.entry
        if text is None:
            entry.delete(0, "end")
        elif text == "back":
            position = entry.index("insert")
            if position:
                entry.delete(position - 1)
        else:
            entry.insert("insert", text)
            if text.endswith("()"):
                entry.icursor(entry.index("insert") - 1)
        entry.focus_set()

    def _height_changed(self, *_):
        try:
            value = int(self.height.get())
        except ValueError:
            self.height_info.set(f"La altura debe ser un entero entre 1 y {MAX_HEIGHT}.")
            return
        if 1 <= value <= MAX_HEIGHT and int(self.height_scale.get()) != value:
            self.height_scale.set(value)
        if self.expression is None:
            self.height_info.set(f"Máximo {value} niveles (una hoja tiene altura 1).")
        elif self.expression.height > value:
            self.height_info.set(f"El árbol actual tiene altura {self.expression.height} y supera el máximo {value}: no se aceptará al analizar.")
        else:
            self.height_info.set(f"Árbol actual: altura {self.expression.height} de {value} permitidos.")

    def _apply_layout(self, event=None):
        for pane in self.panes.panes():
            self.panes.forget(pane)
        if self.layout.get() != "Solo gráfica":
            self.panes.add(self.tree_pane, weight=2)
        if self.layout.get() != "Solo árbol":
            self.panes.add(self.graph_pane, weight=3)
        self.root.after(50, self._split_panes)
        if self.expression is not None:
            self.root.after_idle(self._draw_tree)

    def _split_panes(self):
        if len(self.panes.panes()) == 2 and self.panes.winfo_width() > 1:
            self.panes.sashpos(0, int(self.panes.winfo_width() * 0.45))

    def _select_operators(self, names):
        for name, variable in self.operator_vars.items():
            variable.set(name in names)

    def _signature(self):
        return tuple(v.get() for v in (self.expression_text, self.start, self.end, self.step, self.height, self.solution_domain, self.reference_text))

    def _show_metrics(self):
        if self.metrics is None:
            for variable in self.metric_values.values():
                variable.set("—")
            self.metrics_summary.set("MSC/MSE: —     RMSE: —     NMSE: —")
            self.metric_notes.set("Calculando comparación…" if self.reference else "Define g(x) y analiza para comparar ambas funciones.")
            return
        report = self.metrics
        for name in self.metric_values:
            self.metric_values[name].set(getattr(report, name).display())
        self.metrics_summary.set(f"MSC/MSE: {report.mse.display()}     RMSE: {report.rmse.display()}     NMSE: {report.nmse.display()}")
        details = [f"f(x): {self.expression.to_expression()}", f"g(x): {self.reference.to_expression()}",
                   f"Pares válidos: {report.valid_pairs} · Excluidos: {report.excluded_pairs}", f"NMSE: {report.normalization}."]
        details += [f"{name.upper()}: {getattr(report, name).detail}" for name in self.metric_values if getattr(report, name).detail]
        self.metric_notes.set("\n".join(details))

    def _height(self):
        try:
            value = int(self.height.get())
        except ValueError:
            raise ValueError("La altura debe ser un entero entre 1 y 12.")
        validate_size(Node("variable", "x"), value)
        return value

    def _operators(self):
        return tuple(name for name, selected in self.operator_vars.items() if selected.get())

    def _seed(self):
        return int(self.seed.get()) if self.seed.get().strip() else None

    def _use_example(self, expression):
        self.expression_text.set(expression)
        self.run()

    def _analysis_message(self, message):
        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        self.analysis_text.insert("1.0", message)
        self.analysis_text.configure(state="disabled")

    def _show_analysis(self):
        lines = []
        if self.analysis is not None:
            lines.append(f"Dominio de continuidad real en el intervalo: {self.analysis.domain}")
            if self.expression.is_equation:
                lines.append(f"{self.analysis.solution_kind}: {self.analysis.solutions}")
            lines.extend(self.analysis.notes)
        if self.samples is not None:
            special = [r for r in self.samples.status_ranges() if r[0] != Status.REAL]
            lines.append("")
            lines.append("CASOS ESPECIALES EN LAS MUESTRAS")
            if not special:
                lines.append("Todas las muestras son reales y finitas.")
            for status, first, last, count in special[:20]:
                where = f"x = {first:.6g}" if count == 1 else f"x ∈ [{first:.6g}, {last:.6g}]"
                lines.append(f"• {status.value}: {where} ({count} muestra{'s' if count > 1 else ''})")
            if len(special) > 20:
                lines.append(f"… y {len(special) - 20} tramos más; consulta la pestaña Datos / CSV.")
        if self.limit_lines is not None:
            lines.append("")
            lines.append("LÍMITES EN SINGULARIDADES Y COMPORTAMIENTO EN ±∞")
            lines.extend(self.limit_lines)
        elif self.analysis is not None:
            lines.append("\nCalculando límites laterales…")
        else:
            lines.append("\nCalculando dominio y soluciones…")
        self._analysis_message("\n".join(lines).strip())

    def _show_diagnosis(self):
        if self.samples is None:
            return
        special = [r for r in self.samples.status_ranges() if r[0] != Status.REAL]
        poles = self.analysis.singularities if self.analysis else []
        if not special and not poles:
            self.diagnosis.set("✓ Todas las muestras son reales y finitas.")
            return
        parts = []
        if poles:
            # El muestreo puede saltarse un punto aislado; el análisis simbólico no.
            shown = ", ".join(f"{p:.4g}" for p in poles[:4]) + ("…" if len(poles) > 4 else "")
            parts.append(f"singularidad en x = {shown} (ver límites en Análisis)")
        for status, first, last, count in special[:4]:
            parts.append(f"{status.value} en x = {first:.4g}" if count == 1 else f"{status.value} en [{first:.4g}, {last:.4g}]")
        more = f" · +{len(special) - 4} tramos (ver Análisis)" if len(special) > 4 else ""
        self.diagnosis.set("⚠ " + " · ".join(parts) + more)

    def run(self, export_csv=None):
        self._stop_job()
        self.pending_csv = export_csv
        try:
            expression = parse(self.expression_text.get(), self._height())
            reference = parse(self.reference_text.get(), self._height()) if self.reference_text.get().strip() else None
            if reference is not None and reference.is_equation:
                raise ValueError("La referencia g(x) debe ser una función, sin signo =.")
            interval = Interval(float(self.start.get()), float(self.end.get()), float(self.step.get()))
            interval.points()
        except ValueError as exc:
            self.pending_csv = None
            self.status.set(f"Entrada inválida: {exc}")
            return
        self.expression = expression
        self.reference = reference
        self.interval = interval
        self.run_signature = self._signature()
        self.samples = self.analysis = None
        self.reference_samples = self.metrics = None
        self.limit_lines = self.selected_path = None
        self.diagnosis.set("")
        self._show_metrics()
        self._height_changed()
        self.stats.set(f"Altura: {expression.height} / {self.height.get()} · Nodos: {expression.size}")
        self.figure.clear()
        self.plot_canvas.draw_idle()
        self.table.delete(*self.table.get_children())
        self.evaluate_point()
        self.status.set("Evaluando muestras… Puedes cancelar el cálculo.")
        self._show_analysis()
        context = mp.get_context("spawn")
        self.messages = context.Queue()
        self.process = context.Process(target=compute, args=(self.messages, expression, interval, "real" if self.solution_domain.get().startswith("Reales") else "complex", reference), daemon=True)
        self.process.start()
        self.started = time.monotonic()
        self.poll_id = self.root.after(80, self._poll)

    def _poll(self):
        self.poll_id = None
        if self.process is None:
            return
        finished = False
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "samples":
                    self.samples = payload
                    self._plot()
                    self._fill_table()
                    counts = " · ".join(f"{k}: {v}" for k, v in payload.counts.items())
                    self.stats.set(f"Altura: {self.expression.height} · Nodos: {self.expression.size} · Muestras: {len(payload.xs)} · {counts}")
                    self._show_diagnosis()
                    self._show_analysis()
                    self.status.set("Gráfica disponible. Analizando dominio y soluciones…")
                elif kind == "comparison":
                    self.reference_samples, self.metrics = payload
                    self._show_metrics()
                    self._plot()
                elif kind == "analysis":
                    self.analysis = payload
                    self._show_analysis()
                    self._show_diagnosis()
                    self._plot()
                    self.status.set("Dominio y soluciones listos. Calculando límites en las singularidades…")
                elif kind == "limits":
                    self.limit_lines = payload
                    self._show_analysis()
                    self.status.set("Análisis terminado. La gráfica es un muestreo; consulta la guía para sus límites.")
                    finished = True
                elif kind == "error":
                    self.pending_csv = None
                    self.status.set(f"No se pudo completar el análisis: {payload}")
                    self._analysis_message(payload)
                    finished = True
        except queue.Empty:
            pass
        if self.pending_csv and self.samples is not None and (self.reference is None or self.reference_samples is not None):
            target = self.pending_csv
            self.pending_csv = None
            self.root.after_idle(lambda: self.save_csv(target))
        if finished:
            self._stop_job()
        elif time.monotonic() - self.started > 15:
            self.pending_csv = None
            self._stop_job()
            self.status.set("Se alcanzó el límite de 15 segundos; el análisis quedó incompleto.")
            if self.analysis is not None:
                self.limit_lines = ["Límites no calculados: se alcanzó el límite de 15 segundos."]
                self._show_analysis()
            else:
                self._analysis_message("Cálculo interrumpido por tiempo. Las muestras disponibles se conservan; reduce el árbol o el número de muestras.")
        elif self.process.exitcode is not None:
            self._stop_job()
            self.status.set("El proceso terminó sin completar el análisis.")
        else:
            self.poll_id = self.root.after(80, self._poll)

    def _stop_job(self):
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=0.3)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=0.3)
            self.process.close()
            self.process = None
        if self.messages is not None:
            self.messages.close()
            self.messages = None

    def cancel(self):
        self.pending_csv = None
        if self.process is not None:
            self._stop_job()
            self.status.set("Cálculo cancelado. Puedes editar la expresión y volver a analizar.")
            self._analysis_message("Análisis cancelado por el usuario.")

    def _plot(self):
        view = self.dimension.get()
        self.mode_widget.configure(state="readonly" if view == "2D" else "disabled")
        self.plot_hint.set({
            "3D curva": "3D curva: (x, Re f(x), Im f(x)) con x real. Arrastra para girar; una función real queda en el plano Im = 0.",
            "3D superficie": "3D superficie: altura |f(a+bi)| y color = fase de f, con a en el intervalo y b del mismo ancho. Los polos son picos; los ceros, valles.",
        }.get(view, "Zoom, desplazamiento y guardado de imagen en la barra inferior. Las métricas f vs g aparecen en la esquina."))
        if self.samples is None:
            return
        title = self.expression.to_expression()
        if self.expression.is_equation:
            title = "Residuo (izquierda − derecha): " + title
        if view == "3D superficie":
            key = (title, self.interval)
            if getattr(self, "grid_key", None) != key:
                self.grid = complex_grid(self.expression.residual, self.interval)
                self.grid_key = key
            draw_surface(self.figure, self.grid, title)
        else:
            mode = "real" if self.mode.get() == "Solo reales" else "complex"
            poles = self.analysis.singularities if self.analysis else ()
            reference = self.reference_samples if self.show_reference.get() else None
            ax = draw_function(self.figure, self.samples, mode, poles, title, "3d" if view == "3D curva" else "2d", reference)
            if self.metrics is not None and view == "2D":
                m = self.metrics
                ax.text(0.01, 0.99, f"MSC/MSE = {m.mse.display()}\nRMSE = {m.rmse.display()}\nNMSE = {m.nmse.display()}", transform=ax.transAxes,
                        va="top", ha="left", fontsize=9, family="monospace", bbox={"boxstyle": "round", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.9})
        self.toolbar.update()
        self.plot_canvas.draw_idle()

    def _point_value(self):
        text = self.point.get()
        point_tree = parse(text).left
        if any(n.kind == "variable" for _, n in point_tree.walk()) or "=" in text:
            raise ValueError("El punto debe ser una constante real o compleja, por ejemplo 2 o 1+i.")
        point = evaluate(point_tree)
        if not point.finite:
            raise ValueError(point.display())
        return point.value

    def _draw_tree(self):
        """Dibuja el árbol; cada nodo muestra el valor de su subárbol en el punto x."""
        canvas = self.tree_canvas
        canvas.delete("all")
        root = self.expression.residual
        try:
            point = self._point_value()
        except ValueError:
            point = 0
        results = evaluate_nodes(root, point)
        positions = {}
        leaf = 0
        leaves = sum(1 for _, node in root.walk() if not node.children)
        # Se ajusta al panel cuando cabe; si no, mínimo 66 px y barra de desplazamiento.
        spacing = max(66, min(95, (canvas.winfo_width() - 40) / max(leaves, 1)))
        def layout(node, path=(), depth=0):
            nonlocal leaf
            children = [layout(child, path + (index,), depth + 1) for index, child in enumerate(node.children)]
            if children:
                x = sum(children) / len(children)
            else:
                x = 50 + leaf * spacing
                leaf += 1
            positions[path] = (x, 45 + depth * 90, node)
            return x
        layout(root)
        width = max(leaf * spacing + 30, canvas.winfo_width())
        offset = max(0, (width - leaf * spacing) / 2 - 15)
        selected = self.selected_path
        def in_selection(path):
            return selected is not None and path[:len(selected)] == selected
        for path, (x, y, node) in positions.items():
            if path:
                parent_x, parent_y, _ = positions[path[:-1]]
                highlight = in_selection(path) and path != selected
                canvas.create_line(parent_x + offset, parent_y + 40, x + offset, y - 21, fill="#f59e0b" if highlight else "#94a3b8", width=3 if highlight else 2, arrow="last")
        self.tree_nodes = {}
        for index, (path, (x, y, node)) in enumerate(positions.items()):
            result = results[path]
            tag = f"node{index}"
            self.tree_nodes[tag] = (path, node, result)
            status_color = STATUS_COLORS.get(result.status)
            outline = "#f59e0b" if path == selected else (status_color or "")
            canvas.create_oval(x + offset - 29, y - 21, x + offset + 29, y + 21, fill=KIND_COLORS[node.kind], outline=outline, width=4 if outline else 0, tags=(tag,))
            label = "=" if not path and self.expression.is_equation else str(node.value)
            canvas.create_text(x + offset, y, text=label[:12], fill="white", font=("DejaVu Sans Mono", 10, "bold"), tags=(tag,))
            canvas.create_text(x + offset, y + 32, text=_short(result)[:14], fill=status_color or "#475569", font=("DejaVu Sans Mono", 8), tags=(tag,))
        canvas.configure(scrollregion=(0, 0, width, max(root.height * 90 + 20, canvas.winfo_height())))
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

    def _select_node(self, event):
        canvas = self.tree_canvas
        item = canvas.find_closest(canvas.canvasx(event.x), canvas.canvasy(event.y), halo=4)
        tags = [t for t in canvas.gettags(item[0]) if t in self.tree_nodes] if item else []
        if not tags:
            self.selected_path = None
            self._draw_tree()
            return
        path, node, result = self.tree_nodes[tags[0]]
        self.selected_path = path
        self._draw_tree()
        try:
            point = self._point_value()
        except ValueError:
            point = 0
        shown = f"{point.real:g}" if complex(point).imag == 0 else str(point)
        role = "raíz" if not path else f"nivel {len(path) + 1}"
        self.node_info.set(f"Subárbol ({role}): {node.to_expression()} · altura {node.height} · nodos {node.size} · "
                           f"en x = {shown}: {result.display()} [{result.status.value}]")

    def _fill_table(self):
        self.table.delete(*self.table.get_children())
        for x, result in zip(self.samples.xs, self.samples.results):
            self.table.insert("", "end", values=(f"{x:.10g}", f"{result.value.real:.10g}" if result.finite else "—", f"{result.value.imag:.10g}" if result.finite else "—", result.status.value, result.detail))

    def evaluate_point(self):
        try:
            expression = parse(self.expression_text.get(), self._height())
            result = evaluate(expression.residual, self._point_value())
            prefix = "Residuo" if expression.is_equation else "f(x)"
            self.point_result.set(f"{prefix}: {result.display()} [{result.status.value}] · el árbol muestra el valor de cada subárbol en este punto")
        except ValueError as exc:
            self.point_result.set(str(exc))
        if self.expression is not None:
            self._draw_tree()

    def _factory(self):
        signature = (self._operators(), self._seed())
        if signature != self.factory_signature:
            self.factory = TreeFactory(*signature)
            self.factory_signature = signature
        return self.factory

    def _function_tree(self, text, name):
        if not text.strip():
            raise ValueError(f"Escribe {name} primero.")
        expression = parse(text, self._height())
        if expression.is_equation:
            raise ValueError(f"{name} debe ser una función sin signo = para usar operadores genéticos.")
        return expression.left

    def mutate_tree(self):
        try:
            tree = self._factory().mutate(self._function_tree(self.expression_text.get(), "f(x)"), self._height())
        except ValueError as exc:
            self.status.set(f"No se pudo mutar: {exc}")
            return
        self.expression_text.set(tree.to_expression())
        self.run()

    def crossover_trees(self):
        try:
            first = self._function_tree(self.expression_text.get(), "f(x)")
            second = self._function_tree(self.reference_text.get(), "g(x)")
            first, second = self._factory().crossover(first, second, self._height())
        except ValueError as exc:
            self.status.set(f"No se pudo cruzar: {exc}")
            return
        self.expression_text.set(first.to_expression())
        self.reference_text.set(second.to_expression())
        self.run()

    def random_tree(self):
        try:
            tree = self._factory().generate(self._height())
            self.expression_text.set(tree.to_expression())
            self.run()
        except ValueError as exc:
            self.status.set(f"No se pudo generar: {exc}")

    def save_batch(self):
        try:
            paths = generate_cases(PROJECT_ROOT / "ecuaciones_prueba", int(self.count.get()), self._height(), self._seed(), self._operators())
            self.status.set(f"Lote guardado: {paths[0].name} y TXT en {paths[0].parent}")
        except (ValueError, OSError) as exc:
            self.status.set(f"No se pudo guardar el lote: {exc}")

    def save_tree(self):
        try:
            expression = parse(self.expression_text.get(), self._height())
            filename = filedialog.asksaveasfilename(title="Exportar árbol", defaultextension=".json", filetypes=[("Árbol JSON", "*.json")])
            if filename:
                data = {"format": "expression-tree-v1", "expression": expression.to_expression(), "left": expression.left.to_dict(), "right": expression.right.to_dict() if expression.right else None}
                Path(filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                self.status.set(f"Árbol exportado a {filename}")
        except (ValueError, OSError) as exc:
            self.status.set(f"No se pudo exportar: {exc}")

    def load_tree(self):
        filename = filedialog.askopenfilename(title="Importar árbol", filetypes=[("Árbol JSON", "*.json")])
        if not filename:
            return
        try:
            if Path(filename).stat().st_size > 1_000_000:
                raise ValueError("El archivo supera 1 MB.")
            data = json.loads(Path(filename).read_text(encoding="utf-8"))
            if data.get("format") != "expression-tree-v1":
                raise ValueError("Formato de árbol desconocido; usa un JSON exportado por la aplicación.")
            expression = Expression(Node.from_dict(data["left"]), Node.from_dict(data["right"]) if data.get("right") else None)
            validate_size(expression.residual, self._height())
            parse(expression.to_expression(), self._height())
            self.expression_text.set(expression.to_expression())
            self.run()
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError, OSError) as exc:
            self.status.set(f"No se pudo importar: {exc}")

    def save_csv(self, target="function"):
        if target == "reference" and not self.reference_text.get().strip():
            self.status.set("Escribe una referencia g(x) para generar su CSV.")
            return
        if self.run_signature != self._signature() or self.samples is None or (self.reference is not None and self.reference_samples is None):
            self.run(export_csv=target)
            return
        prefix = "referencia" if target == "reference" else "funcion"
        default_name = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filename = filedialog.asksaveasfilename(title=f"Generar CSV de {'g(x)' if target == 'reference' else 'f(x)'}", initialfile=default_name, defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not filename:
            return
        try:
            if target == "reference":
                write_function_csv(filename, self.reference, self.reference_samples, self.interval)
            else:
                write_function_csv(filename, self.expression, self.samples, self.interval, self.reference, self.reference_samples)
            self.status.set(f"CSV de {'g(x)' if target == 'reference' else 'f(x)'} guardado: {filename}")
        except (OSError, ValueError) as exc:
            self.status.set(f"No se pudo exportar: {exc}")

    # ------------------------------------------------------------------
    # Ajuste aleatorio a puntos de un CSV (regresión simbólica al azar)

    def _build_fit_tab(self, notebook):
        self.fit_xs = self.fit_ys = None
        self.fit_search = self.fit_job = self.fit_selected = self.fit_last = None
        self.fit_drawn = 0.0
        self.fit_source = tk.StringVar(value="Sin datos. Carga un CSV, elige uno precargado o genera uno aleatorio.")
        self.fit_status = tk.StringVar(value="")
        self.fit_target = tk.StringVar(value="5000")
        self.fit_points = tk.StringVar(value="40")
        self.fit_noise = tk.StringVar(value="3")
        self.fit_method = tk.StringVar(value="Programación genética")
        self.fit_genes = tk.StringVar(value="")
        self.fit_signature = None
        self.gp_params = {name: tk.StringVar(value=value) for name, value in
                          (("population", "100"), ("generations", "60"), ("tournament", "3"), ("crossover", "90"), ("mutation", "50"), ("elitism", "2"),
                           ("immigrants", "10"), ("stagnation", "100"))}
        self.fit_seed = tk.StringVar(value="")
        self.gp_selection = tk.StringVar(value="ruleta")
        self.gp_mutations = {name: tk.BooleanVar(value=name in DEFAULT_MUTATIONS) for name in MUTATIONS}
        frame = ttk.Frame(notebook, padding=10)
        notebook.insert(1, frame, text="Ajuste CSV")
        self.fit_tab = frame
        ttk.Label(frame, text="Cada punto del CSV es un dato (xᵢ, yᵢ). Cada ecuación candidata calcula ŷᵢ = f(xᵢ) («y gorro», el valor estimado) y su error "
                  "MSE = (1/n) Σ (yᵢ − ŷᵢ)². Programación genética: individuo = un gen (el árbol, genotipo) → ecuación (fenotipo) → aptitud (MSE). "
                  "Paso 1: población inicial · Paso 2: evaluación · Paso 3: ruleta o torneo, cruza de subárboles y mutación, siempre dentro de la altura máxima.",
                  wraplength=1500, foreground="#475569").pack(anchor="w", pady=(0, 8))
        data_row = ttk.Frame(frame)
        data_row.pack(fill="x", pady=2)
        ttk.Label(data_row, text="Datos", font=("DejaVu Sans", 10, "bold")).pack(side="left", padx=(0, 8))
        ttk.Button(data_row, text="Cargar CSV…", command=self.fit_load, style="Accent.TButton").pack(side="left")
        ttk.Label(data_row, text="Precargado").pack(side="left", padx=(14, 5))
        self.fit_preset = ttk.Combobox(data_row, values=self._presets(), state="readonly", width=16)
        self.fit_preset.pack(side="left")
        self.fit_preset.bind("<<ComboboxSelected>>", lambda event: self.fit_load(DATA_DIR / self.fit_preset.get()))
        ttk.Label(data_row, text="Puntos").pack(side="left", padx=(14, 5))
        ttk.Spinbox(data_row, from_=2, to=5000, textvariable=self.fit_points, width=6).pack(side="left")
        ttk.Label(data_row, text="Ruido %").pack(side="left", padx=(10, 5))
        ttk.Spinbox(data_row, from_=0, to=100, textvariable=self.fit_noise, width=5).pack(side="left")
        ttk.Button(data_row, text="CSV aleatorio", command=self.fit_random_data).pack(side="left", padx=8)
        ttk.Button(data_row, text="CSV función de prueba", command=self.fit_test_data).pack(side="left", padx=4)
        ttk.Label(data_row, textvariable=self.fit_source, foreground="#334155").pack(side="left", padx=8)
        search_row = ttk.Frame(frame)
        search_row.pack(fill="x", pady=(6, 4))
        ttk.Label(search_row, text="Método", font=("DejaVu Sans", 10, "bold")).pack(side="left", padx=(0, 8))
        method = ttk.Combobox(search_row, textvariable=self.fit_method, values=("Programación genética", "Búsqueda aleatoria"), state="readonly", width=21)
        method.pack(side="left")
        method.bind("<<ComboboxSelected>>", self._fit_method_changed)
        self.fit_random_box = ttk.Frame(search_row)
        ttk.Label(self.fit_random_box, text="Candidatos").pack(side="left", padx=(10, 5))
        ttk.Spinbox(self.fit_random_box, from_=100, to=1_000_000, increment=1000, textvariable=self.fit_target, width=9).pack(side="left")
        self.fit_go = ttk.Button(search_row, text="▶ Evolucionar", command=self.fit_start, style="Accent.TButton")
        self.fit_go.pack(side="left", padx=(10, 4))
        ttk.Button(search_row, text="■ Detener", command=self.fit_stop).pack(side="left", padx=4)
        ttk.Button(search_row, text="Usar como f(x)", command=self.fit_use).pack(side="left", padx=4)
        ttk.Button(search_row, text="CSV de x, y, ŷ", command=self.fit_save).pack(side="left", padx=4)
        ttk.Label(search_row, text="Operadores y altura: barra lateral y pestaña Operadores · semilla: Generación aleatoria", foreground="#64748b").pack(side="left", padx=10)
        self.gp_box = ttk.Frame(frame)
        self.gp_box.pack(fill="x", pady=(2, 2))
        ttk.Label(self.gp_box, text="Genético", font=("DejaVu Sans", 10, "bold")).pack(side="left", padx=(0, 8))
        for name, label, low, high, width in (("population", "Población", 4, 5000, 6), ("generations", "Generaciones", 1, 100000, 7), ("tournament", "Torneo k", 2, 50, 4),
                                              ("crossover", "Cruza %", 0, 100, 4), ("mutation", "Mutación %", 0, 100, 4), ("elitism", "Élite", 0, 100, 4)):
            ttk.Label(self.gp_box, text=label).pack(side="left", padx=(8, 4))
            ttk.Spinbox(self.gp_box, from_=low, to=high, textvariable=self.gp_params[name], width=width).pack(side="left")
        ttk.Label(self.gp_box, text="Mutaciones:").pack(side="left", padx=(16, 4))
        for name, description in MUTATIONS.items():
            ttk.Checkbutton(self.gp_box, text=description.split(":")[0], variable=self.gp_mutations[name], command=lambda n=name: self._limit_mutations(n)).pack(side="left", padx=3)
        self.gp_box2 = ttk.Frame(frame)
        self.gp_box2.pack(fill="x", pady=(2, 2))
        ttk.Label(self.gp_box2, text="Diversidad", font=("DejaVu Sans", 10, "bold")).pack(side="left", padx=(0, 8))
        ttk.Label(self.gp_box2, text="Inmigrantes %").pack(side="left", padx=(8, 4))
        ttk.Spinbox(self.gp_box2, from_=0, to=90, textvariable=self.gp_params["immigrants"], width=4).pack(side="left")
        ttk.Label(self.gp_box2, text="Reiniciar tras").pack(side="left", padx=(12, 4))
        ttk.Spinbox(self.gp_box2, from_=1, to=10000, textvariable=self.gp_params["stagnation"], width=5).pack(side="left")
        ttk.Label(self.gp_box2, text="generaciones sin mejora").pack(side="left", padx=(4, 0))
        ttk.Label(self.gp_box2, text="Selección").pack(side="left", padx=(12, 4))
        ttk.Combobox(self.gp_box2, textvariable=self.gp_selection, values=("ruleta", "torneo"), state="readonly", width=8).pack(side="left")
        ttk.Label(self.gp_box2, text="Semilla (vacía = aleatoria)").pack(side="left", padx=(16, 4))
        ttk.Entry(self.gp_box2, textvariable=self.fit_seed, width=11).pack(side="left")
        ttk.Label(frame, textvariable=self.fit_genes, foreground="#7c3aed", wraplength=1500).pack(anchor="w")
        ttk.Label(frame, textvariable=self.fit_status, foreground="#1d4ed8", font=("DejaVu Sans", 10, "bold")).pack(anchor="w", pady=(2, 6))
        panes = ttk.PanedWindow(frame, orient="horizontal")
        panes.pack(fill="both", expand=True)
        graph = ttk.Frame(panes)
        ranking = ttk.Frame(panes, padding=(8, 0, 0, 0))
        panes.add(graph, weight=3)
        panes.add(ranking, weight=2)
        self.fit_figure = Figure(figsize=(8, 6), dpi=100)
        self.fit_canvas = FigureCanvasTkAgg(self.fit_figure, master=graph)
        fit_toolbar = NavigationToolbar2Tk(self.fit_canvas, graph, pack_toolbar=False)
        fit_toolbar.update()
        fit_toolbar.pack(side="bottom", fill="x")
        self.fit_canvas.get_tk_widget().pack(fill="both", expand=True)
        ttk.Label(ranking, text="Mejores ecuaciones encontradas (clic para verla)", font=("DejaVu Sans", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self.fit_table = ttk.Treeview(ranking, columns=("rank", "mse", "rmse", "nmse", "height", "iteration", "origin", "expression"), show="headings")
        for column, label, width in [("rank", "#", 36), ("mse", "MSC/MSE", 95), ("rmse", "RMSE", 85), ("nmse", "NMSE", 80),
                                     ("height", "Altura", 60), ("iteration", "Generación", 95), ("origin", "Origen", 150), ("expression", "Ecuación ŷ = f(x)", 380)]:
            self.fit_table.heading(column, text=label)
            self.fit_table.column(column, width=width, stretch=column == "expression")
        self.fit_table.pack(fill="both", expand=True)
        self.fit_table.bind("<<TreeviewSelect>>", self._fit_select)
        self._fit_method_changed()
        self._fit_draw()

    def _fit_is_gp(self):
        return isinstance(self.fit_search, GeneticProgramming)

    def _fit_method_changed(self, event=None):
        genetic = self.fit_method.get() == "Programación genética"
        if genetic:
            self.fit_random_box.pack_forget()
        else:
            self.fit_random_box.pack(side="left", before=self.fit_go)
        for child in self.gp_box.winfo_children() + self.gp_box2.winfo_children():
            try:
                child.configure(state="normal" if genetic else "disabled")
            except tk.TclError:
                pass
        self.fit_go.configure(text="▶ Evolucionar" if genetic else "▶ Buscar ecuaciones")
        self.fit_table.heading("iteration", text="Generación" if genetic else "Candidato nº")

    def _limit_mutations(self, changed):
        chosen = [n for n, v in self.gp_mutations.items() if v.get()]
        if not chosen:
            self.gp_mutations[changed].set(True)
            self.fit_status.set("Debe quedar al menos un tipo de mutación activo.")

    def _fit_ranking(self, limit=10):
        if self.fit_search is None:
            return []
        if not self._fit_is_gp():
            return self.fit_search.ranking
        ranked = self.fit_search.diverse_ranking(limit)
        best = self.fit_search.best
        if best is not None and all(i.expression != best.expression for i in ranked):
            ranked = [best] + ranked[:limit - 1]   # sin élite, el mejor histórico puede haber salido
        return ranked

    def _presets(self):
        return sorted(p.name for p in DATA_DIR.glob("*.csv")) if DATA_DIR.is_dir() else []

    def _fit_set_data(self, xs, ys, source):
        self.fit_stop()
        self.fit_xs, self.fit_ys = xs, ys
        self.fit_search = self.fit_selected = self.fit_last = None
        self.fit_source.set(source)
        self.fit_status.set(f"{len(xs)} puntos listos, x ∈ [{min(xs):.4g}, {max(xs):.4g}]. Pulsa «Evolucionar».")
        self._fit_fill_table()
        self._fit_draw()

    def fit_load(self, filename=None):
        filename = filename or filedialog.askopenfilename(title="Cargar puntos (x, y)", initialdir=DATA_DIR if DATA_DIR.is_dir() else None,
                                                          filetypes=[("CSV", "*.csv"), ("Todos", "*")])
        if not filename:
            return
        try:
            xs, ys, skipped = load_points(filename)
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            self.fit_status.set(f"No se pudo leer el CSV: {exc}")
            return
        note = f" · {skipped} filas omitidas" if skipped else ""
        self.fit_preset.set(Path(filename).name if Path(filename).parent == DATA_DIR else "")
        self._fit_set_data(xs, ys, f"{Path(filename).name}: {len(xs)} puntos{note}")

    def fit_random_data(self):
        """Puntos de una función oculta aleatoria con ruido; se guardan en datos_csv/."""
        try:
            count, noise = int(self.fit_points.get()), float(self.fit_noise.get()) / 100
            start, end = float(self.start.get()), float(self.end.get())
            formula, xs, ys = make_dataset(self._seed_or_random(), count, noise, start, end, self._operators() or DEFAULT_OPERATORS, min(self._height(), 4))
            DATA_DIR.mkdir(exist_ok=True)
            path = write_points(DATA_DIR / f"aleatoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", xs, ys, f"Función original aleatoria: {formula}; ruido {noise:.0%} del rango")
        except (ValueError, OSError) as exc:
            self.fit_status.set(f"No se pudo generar el CSV: {exc}")
            return
        self.fit_preset.configure(values=self._presets())
        self._fit_set_data(xs, ys, f"{path.name}: {count} puntos (función oculta guardada como comentario en el CSV)")

    def fit_test_data(self):
        """Genera y carga el caso 6.87 + 11*cos(7.23*x^3), sin ruido."""
        try:
            path = write_test_points(DATA_DIR)
            xs, ys, _ = load_points(path)
        except (ValueError, OSError) as exc:
            self.fit_status.set(f"No se pudo generar el CSV: {exc}")
            return
        self.fit_preset.configure(values=self._presets())
        self._fit_set_data(xs, ys, f"{path.name}: 81 puntos de la función de prueba")

    def _seed_or_random(self):
        # Sin semilla escrita, cada CSV aleatorio es distinto.
        return self._seed() if self.seed.get().strip() else None

    def fit_start(self):
        if self.fit_xs is None:
            self.fit_status.set("Primero carga o genera un CSV de puntos.")
            return
        try:
            if self.fit_method.get() == "Programación genética":
                p = {name: int(var.get()) for name, var in self.gp_params.items()}
                mutations = tuple(n for n, v in self.gp_mutations.items() if v.get())
                seed = int(self.fit_seed.get()) if self.fit_seed.get().strip() else None
                signature = ("gp", self._operators(), self._height(), mutations, self.gp_selection.get(), self.fit_seed.get().strip(),
                             *(p[k] for k in ("population", "tournament", "crossover", "mutation", "elitism", "immigrants", "stagnation")))
                if self.fit_search is None or signature != self.fit_signature:
                    self.fit_search = GeneticProgramming(self.fit_xs, self.fit_ys, self._operators(), self._height(), p["population"], p["tournament"],
                                                         p["crossover"] / 100, p["mutation"] / 100, mutations, p["elitism"], seed,
                                                         selection=self.gp_selection.get(), immigrants=p["immigrants"] / 100, stagnation=p["stagnation"])
                    self.fit_signature = signature
                if p["generations"] < 1:
                    raise ValueError("Las generaciones deben ser positivas.")
                self.fit_goal = self.fit_search.generation + p["generations"]
            else:
                target = int(self.fit_target.get())
                if target < 1:
                    raise ValueError("La cantidad de candidatos debe ser positiva.")
                signature = ("azar", self._operators(), self._height())
                if self.fit_search is None or signature != self.fit_signature:
                    self.fit_search = RandomSearch(self.fit_xs, self.fit_ys, self._operators(), self._height(), self._seed())
                    self.fit_signature = signature
                self.fit_goal = self.fit_search.iterations + target
        except ValueError as exc:
            self.fit_status.set(f"No se pudo iniciar: {exc}")
            return
        if self.fit_job is None:
            self.fit_job = self.root.after(1, self._fit_tick)

    def _fit_tick(self):
        """Evalúa candidatos durante ~60 ms y redibuja como máximo 4 veces por segundo."""
        self.fit_job = None
        search = self.fit_search
        deadline = time.monotonic() + 0.06
        if self._fit_is_gp():
            if not search.population:
                search.initialize()
            while search.generation < self.fit_goal and time.monotonic() < deadline:
                search.step()
            self.fit_last = search.random.choice(search.population).tree
            done = search.generation >= self.fit_goal
        else:
            while search.iterations < self.fit_goal and time.monotonic() < deadline:
                self.fit_last = search.step(min(25, self.fit_goal - search.iterations))
            done = search.iterations >= self.fit_goal
        if done or time.monotonic() - self.fit_drawn > 0.25:
            self._fit_report(done)
        if not done:
            self.fit_job = self.root.after(1, self._fit_tick)

    def fit_stop(self):
        if self.fit_job is not None:
            self.root.after_cancel(self.fit_job)
            self.fit_job = None
            self._fit_report(True, "Búsqueda detenida")

    def _fit_report(self, done, verb=None):
        search = self.fit_search
        ranking = self._fit_ranking()
        best = ranking[0] if ranking and math.isfinite(ranking[0].mse) else None
        if self._fit_is_gp():
            state = verb or ("Evolución terminada" if done else "Evolucionando…")
            stats = search.history[-1]
            summary = (f"{state} · semilla {search.seed} · generación {search.generation} · población {len(search.population)} · "
                       f"válidos {stats.valid} · curvas distintas {stats.unique}")
            counts = ", ".join(f"{name} {count}" for name, count in search.mutation_counts.items())
            genes = (f"Cruzas: {search.crossovers} · mutaciones: {counts} · "
                     f"hijos repetidos rechazados: {search.duplicates} · reinicios por estancamiento: {search.restarts}")
            if search.last_crossover:
                c = search.last_crossover
                genes += (f"\nÚltima cruza de genes · dominante (menor error): {c.dominant}  ×  recesivo: {c.recessive}"
                          f"\n   → hijo (dominante + rama del recesivo): {c.child}\n   → recíproco (recesivo + rama del dominante): {c.reciprocal}")
            self.fit_genes.set(genes)
        else:
            state = verb or ("Búsqueda terminada" if done else "Buscando…")
            summary = f"{state} · candidatos: {search.iterations} · descartados por ŷ complejo/indefinido: {search.invalid}"
            self.fit_genes.set("")
        if best:
            nmse = best.mse / search.variance if search.variance else math.nan
            summary += f" · mejor MSE = {best.mse:.6g} · RMSE = {math.sqrt(best.mse):.6g} · NMSE = {nmse:.4g}"
        self.fit_status.set(summary)
        self._fit_fill_table()
        self._fit_draw(show_current=not done)
        self.fit_drawn = time.monotonic()

    def _fit_fill_table(self):
        self.fit_table.delete(*self.fit_table.get_children())
        self.fit_rows = {}
        if self.fit_search is None:
            return
        for rank, candidate in enumerate(self._fit_ranking(), 1):
            if not math.isfinite(candidate.mse):
                continue
            nmse = candidate.mse / self.fit_search.variance if self.fit_search.variance else math.nan
            item = self.fit_table.insert("", "end", values=(rank, f"{candidate.mse:.6g}", f"{math.sqrt(candidate.mse):.6g}", f"{nmse:.4g}",
                                                           candidate.tree.height, candidate.iteration, getattr(candidate, "origin", "aleatorio"),
                                                           candidate.expression))
            self.fit_rows[item] = candidate
            if self.fit_selected is not None and candidate.expression == self.fit_selected.expression:
                self.fit_table.selection_set(item)

    def _fit_select(self, event=None):
        selection = self.fit_table.selection()
        if selection and selection[0] in self.fit_rows:
            self.fit_selected = self.fit_rows[selection[0]]
            if self.fit_job is None:
                self._fit_draw()

    def _fit_candidate(self):
        if self.fit_selected is not None:
            return self.fit_selected
        ranking = [c for c in self._fit_ranking() if math.isfinite(c.mse)]
        return ranking[0] if ranking else None

    def _fit_draw(self, show_current=False):
        if self.fit_xs is None:
            self.fit_figure.clear()
            self.fit_figure.text(0.5, 0.5, "Carga un CSV con columnas x, y, elige uno precargado o genera uno aleatorio.", ha="center", color="#64748b")
            self.fit_canvas.draw_idle()
            return
        low, high = min(self.fit_xs), max(self.fit_xs)
        subdivisions = max(600, min(3000, len(self.fit_xs) * 20))
        dense = [low + (high - low) * i / subdivisions for i in range(subdivisions + 1)]
        def curve(tree, detect_breaks=False):
            if detect_breaks and low < high:
                samples = sample(tree, Interval(low, high, (high - low) / subdivisions))
                x_values, y_values, _ = samples.plot_values("real")
                return x_values, y_values
            return dense, [math.nan if v is None else v for v in predict(tree, dense)]
        candidate = self._fit_candidate()
        title = f"Mejor: ŷ = {candidate.expression}" if candidate else "Datos del CSV"
        if candidate is not None and candidate is self.fit_selected:
            title = f"Seleccionada: ŷ = {candidate.expression}"
        gp = self._fit_is_gp()
        if gp:
            history = [(h.generation, h.best) for h in self.fit_search.history if math.isfinite(h.best)]
            median, total, xlabel = [(h.generation, h.median) for h in self.fit_search.history], self.fit_search.generation, "generación"
        else:
            history = self.fit_search.history if self.fit_search else ()
            median, total, xlabel = (), self.fit_search.iterations if self.fit_search else None, "candidatos probados"
        draw_fit(self.fit_figure, self.fit_xs, self.fit_ys,
                 curve(getattr(candidate, "model", candidate.tree), detect_breaks=True) if candidate else None,
                 predict(getattr(candidate, "model", candidate.tree), self.fit_xs) if candidate else None,
                 curve(self.fit_last) if show_current and self.fit_last is not None else None,
                 history, title, total, xlabel, median, "individuo de la población actual" if gp else "candidato aleatorio actual")
        self.fit_canvas.draw_idle()

    def fit_use(self):
        candidate = self._fit_candidate()
        if candidate is None:
            self.fit_status.set("Todavía no hay una ecuación encontrada.")
            return
        self.fit_stop()
        model = getattr(candidate, "model", candidate.tree)
        if model.height > self._height():
            self.height.set(str(min(MAX_HEIGHT, model.height)))
        self.expression_text.set(model.to_expression())
        self.start.set(f"{min(self.fit_xs):g}")
        self.end.set(f"{max(self.fit_xs):g}")
        self.notebook.select(0)
        self.run()

    def fit_save(self):
        candidate = self._fit_candidate()
        if candidate is None:
            self.fit_status.set("Busca una ecuación antes de exportar ŷ.")
            return
        filename = filedialog.asksaveasfilename(title="Guardar x, y, ŷ", initialfile=f"ajuste_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                                defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not filename:
            return
        try:
            write_fit_csv(filename, self.fit_xs, self.fit_ys, candidate)
            self.fit_status.set(f"CSV guardado: {filename} (x, y, ŷ, error, error², MSC/MSE, RMSE, NMSE)")
        except (OSError, ValueError) as exc:
            self.fit_status.set(f"No se pudo guardar: {exc}")

    def close(self):
        if self.fit_job is not None:
            self.root.after_cancel(self.fit_job)
        if self.initial_id is not None:
            self.root.after_cancel(self.initial_id)
        self._stop_job()
        self.root.destroy()


def main():
    mp.freeze_support()
    root = tk.Tk()
    ExpressionApp(root)
    root.mainloop()
