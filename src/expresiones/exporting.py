"""CSV de una función muestreada con metadatos y comparación opcional."""
import csv
from pathlib import Path
from .metrics import compare_samples, squared_error


def write_function_csv(path, expression, samples, interval, reference_expression=None, reference_samples=None):
    if (reference_expression is None) != (reference_samples is None):
        raise ValueError("La comparación necesita tanto la expresión como las muestras de referencia.")
    metrics = compare_samples(samples, reference_samples) if reference_samples is not None else None
    headers = ["funcion", "tipo", "x", "real", "imaginaria", "estado", "detalle", "inicio", "fin", "paso"]
    if metrics:
        headers += ["referencia", "referencia_real", "referencia_imaginaria", "referencia_estado", "referencia_detalle", "error_cuadrado", "usada_en_metricas", "MSC_MSE", "RMSE", "NMSE", "detalle_MSE", "detalle_RMSE", "detalle_NMSE", "normalizacion_NMSE", "pares_validos", "pares_excluidos"]
    with Path(path).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        for index, (x, result) in enumerate(zip(samples.xs, samples.results)):
            row = {"funcion": expression.to_expression(), "tipo": "residuo izquierda-derecha" if expression.is_equation else "funcion", "x": x,
                   "real": result.value.real if result.finite else "", "imaginaria": result.value.imag if result.finite else "",
                   "estado": result.status.value, "detalle": result.detail, "inicio": interval.start, "fin": interval.end, "paso": interval.step}
            if metrics:
                ref = reference_samples.results[index]
                error = squared_error(result.value if result.finite else None, ref.value if ref.finite else None)
                row.update({"referencia": reference_expression.to_expression(), "referencia_real": ref.value.real if ref.finite else "",
                            "referencia_imaginaria": ref.value.imag if ref.finite else "", "referencia_estado": ref.status.value, "referencia_detalle": ref.detail,
                            "error_cuadrado": str(error) if error is not None else "", "usada_en_metricas": int(error is not None),
                            "MSC_MSE": metrics.mse.value if metrics.mse.value is not None else "", "RMSE": metrics.rmse.value if metrics.rmse.value is not None else "",
                            "NMSE": metrics.nmse.value if metrics.nmse.value is not None else "", "detalle_MSE": metrics.mse.detail,
                            "detalle_RMSE": metrics.rmse.detail, "detalle_NMSE": metrics.nmse.detail, "normalizacion_NMSE": metrics.normalization,
                            "pares_validos": metrics.valid_pairs, "pares_excluidos": metrics.excluded_pairs})
            writer.writerow(row)
    return Path(path)
