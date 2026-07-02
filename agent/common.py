from __future__ import annotations

import ast
import re
from pathlib import Path

try:
    from .constants import STOPWORDS
except ImportError:  # pragma: no cover - manifest loader imports modules outside a package
    from constants import STOPWORDS


def dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def keywords(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOPWORDS and not token.isdigit()
    }


def relative_to_output(path: Path, output_dir: Path) -> str:
    return str(path.resolve().relative_to(output_dir.resolve()))


def format_number(value: float) -> str:
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    return f"{value:.6f}".rstrip("0").rstrip(".")


class ArithmeticEvaluator(ast.NodeVisitor):
    def visit_Expression(self, node: ast.Expression) -> float:
        return self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp) -> float:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        raise ValueError("unsupported arithmetic operator")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError("unsupported unary operator")

    def visit_Constant(self, node: ast.Constant) -> float:
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise ValueError("unsupported constant")

    def visit_Num(self, node: ast.Num) -> float:  # pragma: no cover - compatibility path
        return float(node.n)

    def generic_visit(self, node: ast.AST) -> float:
        raise ValueError(f"unsupported arithmetic syntax: {type(node).__name__}")
