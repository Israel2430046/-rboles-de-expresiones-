"""Inicia el laboratorio de árboles de expresión desde la raíz del proyecto."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

if __name__ == "__main__":
    from expresiones.gui import main
    main()

