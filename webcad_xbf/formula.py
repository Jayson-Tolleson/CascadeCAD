"""Safe engineering formula evaluator used by numeric CAD fields."""
from __future__ import annotations

import ast
import math
import operator
import re
from typing import Callable

from .units import to_mm

_ALLOWED_FUNCS: dict[str, Callable[..., float]] = {
    "sqrt": math.sqrt, "pow": pow, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan, "round": round,
    "floor": math.floor, "ceil": math.ceil, "abs": abs, "min": min, "max": max,
}
_ALLOWED_CONSTANTS = {"pi": math.pi, "e": math.e}
_BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_UNIT_PATTERN = re.compile(r"(?P<value>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(?P<unit>ft-in|feet\s*\+\s*inches|inches|inch|in|\"|feet|foot|ft|'|yards|yard|yd|millimeters|millimetres|mm|centimeters|centimetres|cm|meters|metres|m)(?![A-Za-z0-9_])")


class FormulaError(ValueError):
    """Raised when an engineering formula is invalid or unsafe."""


def _replace_unit_literal(match: re.Match[str]) -> str:
    value = float(match.group("value"))
    unit = match.group("unit")
    return str(to_mm(value, unit))


def _prepare(expression: str) -> str:
    text = str(expression).strip()
    if not text:
        raise FormulaError("empty formula")
    text = text.replace("^", "**")
    return _UNIT_PATTERN.sub(_replace_unit_literal, text)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in _ALLOWED_CONSTANTS:
        return float(_ALLOWED_CONSTANTS[node.id])
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return float(_BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right)))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return float(_UNARY_OPS[type(node.op)](_eval_node(node.operand)))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCS:
        if node.keywords:
            raise FormulaError("keyword arguments are not supported")
        return float(_ALLOWED_FUNCS[node.func.id](*[_eval_node(arg) for arg in node.args]))
    raise FormulaError(f"unsupported formula element: {node.__class__.__name__}")


def evaluate_formula(expression: str, *, default_unit: str = "mm") -> float:
    """Evaluate a numeric expression and return millimetres for unit literals.

    Plain numbers are interpreted in ``default_unit``. Unit-suffixed numbers such
    as ``6' + 25 mm`` are converted to millimetres before evaluation.
    """
    prepared = _prepare(expression)
    try:
        tree = ast.parse(prepared, mode="eval")
    except SyntaxError as exc:
        raise FormulaError("invalid formula syntax") from exc
    value = _eval_node(tree)
    has_explicit_unit = bool(_UNIT_PATTERN.search(str(expression)))
    return value if has_explicit_unit else to_mm(value, default_unit)
