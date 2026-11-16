"""Shipped code (core/, sidecar/) must not import dev-time packages or cloud SDKs.

See the "Hard rules" in CLAUDE.md. This is a static check with ast. It catches
`import x` and `from x import y`, and bans importlib, __import__, exec and eval
outright, since those can load modules or run code built at runtime and would get
past a static check.
"""

import ast
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_DIRS = [REPO_ROOT / "core", REPO_ROOT / "sidecar"]
FORBIDDEN = [
    "collector",
    "eval",
    "training",
    "anthropic",
    "openai",
    "google.generativeai",
    "google.genai",
    "requests",
    # Dev-time "collector" dependency group (D-12). Shipped code makes no network calls.
    "httpx",
    "bs4",
    # Not an SDK: banned because it loads modules by name at runtime.
    "importlib",
]
# Matched as bare names (exec(...), loader = __import__) and as attributes
# (builtins.exec). Any `.eval` attribute fails too, so a method like
# model.eval() would need an allowlist if core/ ever uses one.
BANNED_BUILTINS = {"__import__", "exec", "eval"}


def _is_forbidden(module: str) -> bool:
    return any(module == bad or module.startswith(bad + ".") for bad in FORBIDDEN)


def find_forbidden_imports(path: Path) -> list[str]:
    """Return the forbidden imports and banned builtin uses in one .py file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if _is_forbidden(node.module):
                candidates = [node.module]
            else:
                # `from google import generativeai` has module "google", so also
                # check the full dotted name of each imported item.
                candidates = [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Name) and node.id in BANNED_BUILTINS:
            candidates = [node.id]
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_BUILTINS:
            candidates = [node.attr]
        else:
            continue
        found += [n for n in candidates if n in BANNED_BUILTINS or _is_forbidden(n)]
    return found


def scan(dirs: list[Path]) -> dict[str, list[str]]:
    """Map each offending file (relative path) to its forbidden imports."""
    violations: dict[str, list[str]] = {}
    for directory in dirs:
        for path in sorted(directory.rglob("*.py")):
            bad = find_forbidden_imports(path)
            if bad:
                violations[path.relative_to(directory.parent).as_posix()] = bad
    return violations


def test_shipped_code_has_no_forbidden_imports() -> None:
    for directory in SHIPPED_DIRS:
        # Guard against a rename silently turning this test into a no-op.
        assert directory.is_dir(), f"missing {directory}"
    assert scan(SHIPPED_DIRS) == {}


def test_dev_groups_are_not_runtime_dependencies() -> None:
    """httpx and beautifulsoup4 live in dependency groups only (D-12). pymupdf moved
    to the runtime on purpose in D-28 (AGPL, to be settled before Phase 8, D-08)."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    runtime = " ".join(tomllib.loads(text)["project"]["dependencies"]).lower()
    for name in ("httpx", "beautifulsoup4"):
        assert name not in runtime, f"{name} must stay out of [project].dependencies"
    assert "pymupdf" in runtime  # D-28; if this changes, update D-08/D-28 too


def test_pymupdf_is_imported_only_by_the_pdf_module() -> None:
    """All PDF access goes through shiori_core.pdf, so the AGPL backend can be
    swapped by rewriting one file (D-08, D-28)."""
    allowed = REPO_ROOT / "core" / "shiori_core" / "pdf"
    offenders = []
    for directory in SHIPPED_DIRS:
        for path in sorted(directory.rglob("*.py")):
            if path.is_relative_to(allowed):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
                if any(n.split(".")[0] in ("pymupdf", "fitz") for n in names):
                    offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []


def test_scanner_catches_bad_imports(tmp_path: Path) -> None:
    pkg = tmp_path / "core"
    pkg.mkdir()
    (pkg / "bad.py").write_text(
        "import os\n"
        "import requests\n"
        "from eval.metrics import score\n"
        "from google import generativeai\n"
        "import evaluate_helpers\n"  # prefix match only, must not be flagged
        "from . import training\n",  # relative import, must not be flagged
        encoding="utf-8",
    )
    assert scan([pkg]) == {
        "core/bad.py": ["requests", "eval.metrics", "google.generativeai"],
    }


def test_scanner_catches_dynamic_imports(tmp_path: Path) -> None:
    pkg = tmp_path / "sidecar"
    pkg.mkdir()
    (pkg / "sneaky.py").write_text(
        "import builtins\n"
        "import importlib\n"
        "from importlib import import_module\n"
        "import importlib.util\n"
        "loader = __import__\n"
        "mod = builtins.__import__('requests')\n",
        encoding="utf-8",
    )
    found = scan([pkg])["sidecar/sneaky.py"]
    assert sorted(found) == sorted(
        ["importlib", "importlib", "importlib.util", "__import__", "__import__"]
    )


def test_scanner_catches_exec_and_eval(tmp_path: Path) -> None:
    pkg = tmp_path / "core"
    pkg.mkdir()
    (pkg / "runs_code.py").write_text(
        "import builtins\n"
        "exec('import requests')\n"
        "eval('1 + 1')\n"
        "run = exec\n"
        "builtins.eval('2')\n"
        "evaluate = 3\n",  # similar name, must not be flagged
        encoding="utf-8",
    )
    found = scan([pkg])["core/runs_code.py"]
    assert sorted(found) == sorted(["exec", "eval", "exec", "eval"])
