"""Trabajo aislado en proceso: el solver puede cancelarse sin bloquear Tk."""
def compute(queue, expression, interval, solution_domain, reference=None):
    try:
        # Los exponentes anidados pueden consumir mucha memoria al simplificarse.
        # Linux: limita la memoria adicional del proceso; la UI vive fuera de él.
        import sys
        if sys.platform.startswith("linux"):
            import os
            import resource
            with open("/proc/self/statm", encoding="ascii") as file:
                current = int(file.read().split()[0]) * os.sysconf("SC_PAGE_SIZE")
            _, hard = resource.getrlimit(resource.RLIMIT_AS)
            limit = current + 512 * 1024 * 1024
            if hard != resource.RLIM_INFINITY:
                limit = min(limit, hard)
            resource.setrlimit(resource.RLIMIT_AS, (limit, hard))
        from .sampling import sample
        samples = sample(expression.residual, interval)
        queue.put(("samples", samples))
        if reference is not None:
            from .metrics import compare_samples
            reference_samples = sample(reference.residual, interval)
            queue.put(("comparison", (reference_samples, compare_samples(samples, reference_samples))))
        from .symbolic import analyze, limits
        analysis = analyze(expression, interval.start, interval.end, solution_domain)
        queue.put(("analysis", analysis))
        queue.put(("limits", limits(expression, analysis.points)))
    except MemoryError:
        queue.put(("error", "El cálculo excede el límite de memoria. Reduce la complejidad de la expresión."))
    except Exception as exc:
        queue.put(("error", f"{type(exc).__name__}: {exc}"))

