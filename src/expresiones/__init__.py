"""Motor independiente de Tkinter para árboles y programación genética."""
from .tree import Node
from .parser import Expression, parse
from .evaluation import Result, Status, evaluate
from .operators import OPERATORS

__all__ = ["Node", "Expression", "parse", "Result", "Status", "evaluate", "OPERATORS"]
