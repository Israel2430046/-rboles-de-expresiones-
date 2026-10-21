"""Gráficas 2D y curvas 3D embebibles, independientes de Tkinter."""
import math


def _scale(values):
    largest = max((abs(v) for v in values if math.isfinite(v)), default=0)
    return 10.0 ** math.floor(math.log10(largest)) if largest > 1e150 else 1


def draw_function(figure, samples, mode="real", singularities=(), title="f(x)", dimension="2d", reference=None):
    """3D representa (x, Re(f(x)), Im(f(x))), con x real y cortes conservados."""
    if dimension not in ("2d", "3d"):
        raise ValueError("La dimensión debe ser 2d o 3d.")
    figure.clear()
    figure.set_facecolor("#ffffff")
    ax = figure.add_subplot(111, projection="3d" if dimension == "3d" else None)
    plot_mode = "complex" if dimension == "3d" else mode
    series = [("f", samples.plot_values(plot_mode, singularities), "#2563eb", "#db2777")]
    if reference is not None:
        series.append(("g", reference.plot_values(plot_mode), "#059669", "#d97706"))
    x_scale = _scale([x for _, (xs, _, _), _, _ in series for x in xs])
    y_scale = _scale([v for _, (_, real, imag), _, _ in series for v in real + imag])
    for name, (xs, real, imag), color, imaginary_color in series:
        xs = [v / x_scale for v in xs]
        real = [v / y_scale for v in real]
        imag = [v / y_scale for v in imag]
        if dimension == "3d":
            ax.plot(xs, real, imag, color=color, linewidth=2, label=f"{name}(x)", linestyle="-" if name == "f" else "--")
        else:
            ax.plot(xs, real, color=color, linewidth=1.8, label=f"Re({name}(x))" if mode != "real" else f"{name}(x) real", linestyle="-" if name == "f" else "--")
            if mode != "real":
                ax.plot(xs, imag, color=imaginary_color, linewidth=1.5, linestyle=":", label=f"Im({name}(x))")
    x_label = "x (real)" if x_scale == 1 else f"x / {x_scale:.0e} (real)"
    if dimension == "3d":
        suffix = "" if y_scale == 1 else f" / {y_scale:.0e}"
        ax.set_xlabel(x_label, labelpad=10)
        ax.set_ylabel("Parte real" + suffix, labelpad=10)
        ax.set_zlabel("Parte imaginaria" + suffix, labelpad=10)
        ax.view_init(elev=25, azim=-60)
        ax.set_box_aspect((1.5, 1, 1))
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.pane.set_facecolor("#f1f5f9")
        figure.subplots_adjust(left=0.03, right=0.92, bottom=0.06, top=0.91)
    else:
        for point in singularities:
            ax.axvline(point / x_scale, color="#dc2626", alpha=0.35, linestyle=":")
        ax.axhline(0, color="#94a3b8", linewidth=0.7)
        ax.axvline(0, color="#94a3b8", linewidth=0.7)
        ax.set_xlabel(x_label)
        ax.set_ylabel("Valor" if y_scale == 1 else f"Valor / {y_scale:.0e}")
        ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(title[:90] + ("…" if len(title) > 90 else ""), fontsize=10, pad=14)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=9)
    ax.tick_params(labelsize=9)
    if dimension == "2d":
        figure.tight_layout(pad=2)
    return ax


def draw_surface(figure, grid, title="f(z)"):
    """Superficie |f(a+bi)| coloreada por el argumento (fase) de f.

    La altura se recorta en el percentil 95 para que los polos no aplasten el
    resto; los puntos sin valor finito quedan transparentes.
    """
    import numpy as np
    from matplotlib.colors import hsv_to_rgb
    real, imag, values = grid
    figure.clear()
    figure.set_facecolor("#ffffff")
    ax = figure.add_subplot(111, projection="3d")
    modulus = np.abs(values)
    finite = np.isfinite(modulus)
    ax.set_title(title[:90] + ("…" if len(title) > 90 else ""), fontsize=10, pad=14)
    if not finite.any():
        ax.text2D(0.5, 0.5, "Sin valores finitos en esta región", transform=ax.transAxes, ha="center")
        return ax
    cap = float(np.percentile(modulus[finite], 95)) or 1.0
    height = np.where(finite, np.minimum(modulus, cap), 0.0)
    hue = (np.angle(np.where(finite, values, 0)) + np.pi) / (2 * np.pi)
    rgb = hsv_to_rgb(np.dstack([hue, np.full(hue.shape, 0.75), np.full(hue.shape, 0.95)]))
    colors = np.dstack([rgb, np.where(finite, 1.0, 0.0)])
    ax.plot_surface(real, imag, height, facecolors=colors, rstride=1, cstride=1, linewidth=0, antialiased=False, shade=False)
    ax.set_xlabel("Re(z)", labelpad=10)
    ax.set_ylabel("Im(z)", labelpad=10)
    ax.set_zlabel(f"|f(z)| (recortado en {cap:.3g})", labelpad=10)
    ax.set_zlim(0, cap)
    ax.view_init(elev=30, azim=-60)
    ax.set_box_aspect((1.3, 1.3, 0.9))
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor("#f1f5f9")
    ax.tick_params(labelsize=9)
    figure.subplots_adjust(left=0.03, right=0.95, bottom=0.06, top=0.91)
    return ax


def draw_fit(figure, xs, ys, curve=None, fitted=None, current=None, history=(), title="Ajuste aleatorio", total=None,
             xlabel="candidatos probados", median=(), current_label="candidato aleatorio actual"):
    """Puntos (x, y) del CSV, curva ŷ = f(x) del candidato y convergencia del MSE.

    curve: (xs_densos, ŷ_densos) del mejor candidato; fitted: ŷ en cada x del CSV;
    current: (xs_densos, ŷ_densos) del último candidato aleatorio probado.
    """
    figure.clear()
    figure.set_facecolor("#ffffff")
    grid = figure.add_gridspec(2, 1, height_ratios=(3, 1), hspace=0.35)
    ax = figure.add_subplot(grid[0])
    if current is not None:
        ax.plot(*current, color="#94a3b8", linewidth=1, linestyle="--", alpha=0.7, label=current_label)
    if fitted is not None:
        for x, y, y_hat in zip(xs, ys, fitted):
            if y_hat is not None:
                ax.plot((x, x), (y, y_hat), color="#f59e0b", linewidth=0.8, alpha=0.6)
    ax.scatter(xs, ys, s=18, color="#0f172a", zorder=3, label="datos y (CSV)")
    if curve is not None:
        ax.plot(*curve, color="#2563eb", linewidth=2.2, zorder=4, label=r"mejor $\hat{y} = f(x)$")
    if fitted is not None:
        valid = [(x, v) for x, v in zip(xs, fitted) if v is not None]
        if valid:
            ax.scatter(*zip(*valid), s=22, facecolors="none", edgecolors="#2563eb", zorder=5, label=r"$\hat{y}_i$ en cada $x_i$")
    finite = [y for y in ys if math.isfinite(y)]
    if finite:
        low, high = min(finite), max(finite)
        margin = (high - low) * 0.25 or 1
        ax.set_ylim(low - margin, high + margin)
    ax.set_title(title[:110] + ("…" if len(title) > 110 else ""), fontsize=10)
    ax.set_xlabel("x")
    ax.set_ylabel(r"y  /  $\hat{y}$")
    ax.grid(alpha=0.2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="best", fontsize=8)
    conv = figure.add_subplot(grid[1])
    if history:
        history = list(history)
        if total and total > history[-1][0]:
            history.append((total, history[-1][1]))  # la meseta llega hasta el último candidato probado
        steps, errors = zip(*history)
        conv.step(steps, errors, where="post", color="#db2777")
        conv.scatter(steps, errors, s=10, color="#db2777", label="mejor MSE")
        finite_median = [(g, m) for g, m in median if math.isfinite(m)]
        if finite_median:
            conv.plot(*zip(*finite_median), color="#94a3b8", linewidth=1, label="mediana de la población")
            conv.legend(loc="upper right", fontsize=7)
        if min(errors) > 0:
            conv.set_yscale("log")
    conv.set_xlabel(xlabel)
    conv.set_ylabel("MSE")
    conv.grid(alpha=0.2)
    conv.spines[["top", "right"]].set_visible(False)
    conv.tick_params(labelsize=8)
    figure.subplots_adjust(left=0.08, right=0.97, top=0.93, bottom=0.08)
    return ax
