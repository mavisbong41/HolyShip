from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _req_markers(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    markers: set[str] = set()
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or len(decorator.args) != 1:
            continue
        target = decorator.func
        if (
            isinstance(target, ast.Attribute)
            and target.attr == "req"
            and isinstance(target.value, ast.Attribute)
            and target.value.attr == "mark"
            and isinstance(decorator.args[0], ast.Constant)
            and isinstance(decorator.args[0].value, str)
        ):
            markers.add(decorator.args[0].value)
    return markers


@pytest.mark.req("SEC-04")
def test_backend_logger_calls_do_not_receive_document_content_values():
    forbidden_names = {
        "body",
        "content",
        "content_base64",
        "document",
        "document_text",
        "raw_value",
        "text",
    }
    logger_calls: list[tuple[Path, ast.Call]] = []
    violations: list[str] = []

    for path in (ROOT / "backend" / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "logger":
                continue
            logger_calls.append((path, node))
            for argument in node.args[1:]:
                referenced = {
                    child.id
                    for child in ast.walk(argument)
                    if isinstance(child, ast.Name)
                }
                referenced.update(
                    child.attr
                    for child in ast.walk(argument)
                    if isinstance(child, ast.Attribute)
                )
                unsafe = sorted(referenced & forbidden_names)
                if unsafe:
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:{','.join(unsafe)}")

    assert logger_calls, "audit must inspect real backend logger calls"
    assert violations == []


@pytest.mark.req("UI-01")
def test_official_clients_are_api_consumers_with_root_validation():
    decision = (ROOT / "docs" / "scope_decisions" / "2026-09-21-ui-human-review.md").read_text(encoding="utf-8")
    dashboard = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    addin_config = (ROOT / "outlook-addin" / "src" / "lib" / "config.ts").read_text(encoding="utf-8")
    backend_config = (ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "Dashboard" in decision and "Outlook Add-in" in decision and "Human Review" in decision
    assert "?email=" in addin_config
    assert 'params.get("email")' in dashboard
    assert "https://localhost:3200" in backend_config
    assert "frontend-check" in makefile
    assert "addin-check" in makefile


@pytest.mark.req("SCP-06")
def test_required_behavior_categories_have_req_marked_assertive_tests():
    required_prefixes = {
        "ingestion": "ING-",
        "classification": "CLS-",
        "attachment routing": "DOC-",
        "extraction": "EXT-",
        "comparison": "CMP-",
    }
    coverage = {category: [] for category in required_prefixes}

    for path in (ROOT / "backend" / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            markers = _req_markers(node)
            has_assertion = any(isinstance(child, ast.Assert) for child in ast.walk(node))
            for category, prefix in required_prefixes.items():
                if has_assertion and any(marker.startswith(prefix) for marker in markers):
                    coverage[category].append(f"{path.name}::{node.name}")

    assert all(coverage.values()), coverage
