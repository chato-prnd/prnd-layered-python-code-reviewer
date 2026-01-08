from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ImportViolation:
    file_path: Path
    file_layer: str
    imported_module: str
    imported_layer: str
    lineno: int
    col_offset: int
    reason: str


def _iter_python_files(root_dir: Path, include_tests: bool) -> Iterable[Path]:
    for path in root_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if not include_tests and "tests" in path.parts:
            continue
        yield path


def _parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_forbid_entries(entries: list[str]) -> dict[str, set[str]]:
    forbid: dict[str, set[str]] = {}
    for entry in entries:
        if ":" not in entry:
            raise ValueError(f"Invalid --forbid entry (expected 'from:to1,to2'): {entry}")
        src, dst_csv = entry.split(":", 1)
        src = src.strip()
        if not src:
            raise ValueError(f"Invalid --forbid entry (empty source layer): {entry}")
        destinations = set(_parse_csv(dst_csv))
        if not destinations:
            raise ValueError(f"Invalid --forbid entry (empty destinations): {entry}")
        forbid.setdefault(src, set()).update(destinations)
    return forbid


def _file_layer(root_dir: Path, file_path: Path, layer_names: set[str]) -> str:
    relative = file_path.relative_to(root_dir)
    if len(relative.parts) == 1:
        return "root"
    top = relative.parts[0]
    if top in layer_names:
        return top
    return "other"


def _imported_layer(imported_module: str, package_name: str, layer_names: set[str]) -> str:
    if not imported_module:
        return "other"
    if imported_module == package_name:
        return "root"
    prefix = f"{package_name}."
    if not imported_module.startswith(prefix):
        return "other"
    remainder = imported_module.removeprefix(prefix)
    first = remainder.split(".", 1)[0]
    if first in layer_names:
        return first
    return "root"


def _iter_imports(tree: ast.AST) -> Iterable[tuple[str, int, int]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno, node.col_offset
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            yield node.module, node.lineno, node.col_offset


def _violations_for_file(
    *,
    root_dir: Path,
    file_path: Path,
    package_name: str,
    layer_names: set[str],
    forbid: dict[str, set[str]],
) -> list[ImportViolation]:
    layer = _file_layer(root_dir, file_path, layer_names=layer_names)
    if layer in {"root", "other"}:
        return []

    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    except SyntaxError as exc:
        lineno = exc.lineno or 1
        col = exc.offset or 0
        return [
            ImportViolation(
                file_path=file_path,
                file_layer=layer,
                imported_module="(parse error)",
                imported_layer="other",
                lineno=lineno,
                col_offset=col,
                reason=f"SyntaxError: {exc.msg}",
            )
        ]

    violations: list[ImportViolation] = []
    for imported_module, lineno, col_offset in _iter_imports(tree):
        imported_layer = _imported_layer(
            imported_module,
            package_name=package_name,
            layer_names=layer_names,
        )
        if imported_layer in {"root", "other"}:
            continue

        forbidden_targets = forbid.get(layer)
        if not forbidden_targets:
            continue
        if imported_layer in forbidden_targets:
            violations.append(
                ImportViolation(
                    file_path=file_path,
                    file_layer=layer,
                    imported_module=imported_module,
                    imported_layer=imported_layer,
                    lineno=lineno,
                    col_offset=col_offset,
                    reason="Forbidden import direction by configured layer rules.",
                )
            )

    return violations


def _format_violation(violation: ImportViolation) -> str:
    location = f"{violation.file_path}:{violation.lineno}:{violation.col_offset + 1}"
    return (
        f"{location} [{violation.file_layer} -> {violation.imported_layer}] "
        f"{violation.imported_module} :: {violation.reason}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check layered-architecture import direction for a Python package.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Package root directory to scan (e.g. src/my_pkg or my_pkg).",
    )
    parser.add_argument(
        "--package-name",
        type=str,
        default="",
        help="Top-level package name (default: basename of --root).",
    )
    parser.add_argument(
        "--layers",
        type=str,
        default="domain,dataset,adaptor,service",
        help="Comma-separated layer directory names under --root.",
    )
    parser.add_argument(
        "--forbid",
        action="append",
        default=[],
        help="Forbid layer-to-layer imports: 'from:to1,to2'. Repeatable.",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in scanning (default: false).",
    )
    args = parser.parse_args()

    root_dir: Path = args.root
    if not root_dir.exists() or not root_dir.is_dir():
        raise SystemExit(f"--root must be an existing directory: {root_dir}")

    package_name = args.package_name.strip() or root_dir.name
    layer_names = set(_parse_csv(args.layers))
    forbid = _parse_forbid_entries(list(args.forbid))

    if not forbid:
        forbid = {
            "domain": {"dataset", "adaptor", "service"},
            "dataset": {"adaptor", "service"},
            "adaptor": {"dataset", "service"},
        }

    all_violations: list[ImportViolation] = []
    for file_path in _iter_python_files(root_dir=root_dir, include_tests=args.include_tests):
        all_violations.extend(
            _violations_for_file(
                root_dir=root_dir,
                file_path=file_path,
                package_name=package_name,
                layer_names=layer_names,
                forbid=forbid,
            )
        )

    if not all_violations:
        print("OK: no layered-import violations found.")
        return 0

    print("Layered-import violations:")
    for violation in sorted(all_violations, key=lambda v: (str(v.file_path), v.lineno, v.col_offset)):
        print(f"- {_format_violation(violation)}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

