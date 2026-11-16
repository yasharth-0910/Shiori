"""Static security rules for shipped code (core/, sidecar/, app/ when it exists).

Reads source with ast, runs nothing. Builds on tests/test_import_boundaries.py,
which already bans eval, exec, __import__, importlib, requests and httpx in
core/ and sidecar/; those are not repeated here. See docs/threat_model.md.

Rules:
  net        network-capable imports (socket, urllib.request, http.client, ...)
  shell      subprocess call with shell=True, os.system, os.popen
  unsafe     pickle load/loads/Unpickler, any marshal use, yaml.load without a
             safe loader, yaml.unsafe_load
  bind       sidecar/ names an all-interfaces address or a host other than 127.0.0.1

Allowlist entries need a written reason. Entries may name files that do not
exist yet (the loopback server and the model download are not built).
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_DIRS = [REPO_ROOT / "core", REPO_ROOT / "sidecar", REPO_ROOT / "app"]

NET_MODULES = [
    "socket",
    "urllib.request",
    "http.client",
    "aiohttp",
    "websockets",
    "ftplib",
    "smtplib",
    "telnetlib",
]
ALL_INTERFACES = {"0.0.0.0", "::", "[::]"}
LOOPBACK = "127.0.0.1"
SAFE_YAML_LOADERS = {"SafeLoader", "CSafeLoader"}

# rule -> {path relative to repo root: reason}
ALLOWLIST: dict[str, dict[str, str]] = {
    "net": {
        "sidecar/server.py": (
            "The loopback server (Phase 7) needs socket to bind a random free "
            "port on 127.0.0.1; the bind rule still checks the host."
        ),
        "core/shiori_core/model_download.py": (
            "The first-run model download is the only network path (D-09): "
            "pinned URLs, SHA-256 verified."
        ),
        "core/shiori_core/extract/llm.py": (
            "Calls the local llama-server over urllib.request; Client refuses any "
            "host but 127.0.0.1 when it is made (D-69)."
        ),
    },
}


def _matches(name: str, banned: list[str]) -> bool:
    return any(name == b or name.startswith(b + ".") for b in banned)


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Local name -> dotted origin, so `from x import y` reads as x.y."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out[a.asname or a.name.split(".")[0]] = (
                    a.name if a.asname else a.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for a in node.names:
                out[a.asname or a.name] = f"{node.module}.{a.name}"
    return out


def _dotted(node: ast.AST, aliases: dict[str, str]) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(aliases.get(node.id, node.id))
    return ".".join(reversed(parts))


def _kw(call: ast.Call, name: str) -> ast.expr | None:
    return next((k.value for k in call.keywords if k.arg == name), None)


def _is_false(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def find_violations(path: Path, in_sidecar: bool) -> set[str]:
    """Rules broken by one .py file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = _aliases(tree)
    rules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            # `from urllib import request` has module "urllib": check each item too.
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        else:
            names = []
        if any(_matches(n, NET_MODULES) for n in names):
            rules.add("net")
        if any(_matches(n, ["marshal"]) for n in names):
            rules.add("unsafe")

        if isinstance(node, ast.Call):
            fn = _dotted(node.func, aliases)
            if fn in ("os.system", "os.popen"):
                rules.add("shell")
            if fn.startswith("subprocess.") and _kw(node, "shell") is not None:
                # Anything but a literal False counts: a variable could be True.
                if not _is_false(_kw(node, "shell")):
                    rules.add("shell")
            if fn in (
                "pickle.load",
                "pickle.loads",
                "pickle.Unpickler",
                "yaml.unsafe_load",
            ):
                rules.add("unsafe")
            if fn == "yaml.load":
                loader = _kw(node, "Loader")
                if loader is None and len(node.args) > 1:
                    loader = node.args[1]
                loader_name = _dotted(loader, aliases).split(".")[-1] if loader else ""
                if loader_name not in SAFE_YAML_LOADERS:
                    rules.add("unsafe")
            if in_sidecar:
                host = _kw(node, "host")
                if (
                    isinstance(host, ast.Constant)
                    and isinstance(host.value, str)
                    and host.value != LOOPBACK
                ):
                    rules.add("bind")
        if (
            in_sidecar
            and isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in ALL_INTERFACES
        ):
            rules.add("bind")
    return rules


def scan(dirs: list[Path], base: Path = REPO_ROOT) -> dict[str, list[str]]:
    """Map each offending file (relative) to its broken rules, minus the allowlist."""
    out: dict[str, list[str]] = {}
    for d in dirs:
        for path in sorted(d.rglob("*.py")) if d.is_dir() else []:
            rel = path.relative_to(base).as_posix()
            rules = find_violations(
                path, in_sidecar=path.is_relative_to(base / "sidecar")
            )
            bad = sorted(r for r in rules if rel not in ALLOWLIST.get(r, {}))
            if bad:
                out[rel] = bad
    return out


def test_shipped_code_passes_static_security_rules() -> None:
    assert (REPO_ROOT / "core").is_dir() and (REPO_ROOT / "sidecar").is_dir()
    assert scan(SHIPPED_DIRS) == {}


def test_allowlist_entries_have_a_reason() -> None:
    for rule, entries in ALLOWLIST.items():
        for path, reason in entries.items():
            assert len(reason.split()) >= 5, f"{rule}: {path} needs a written reason"


def _write(tmp_path: Path, folder: str, source: str) -> dict[str, list[str]]:
    d = tmp_path / folder
    d.mkdir()
    (d / "m.py").write_text(source, encoding="utf-8")
    return scan([d], base=tmp_path)


def test_net_rule_triggers(tmp_path: Path) -> None:
    src = (
        "import socket\nimport smtplib\nfrom urllib import request\n"
        "import urllib.parse\nimport websockets.sync\n"
    )
    assert _write(tmp_path, "core", src) == {"core/m.py": ["net"]}


def test_net_rule_ignores_harmless_imports(tmp_path: Path) -> None:
    assert (
        _write(
            tmp_path,
            "core",
            "import urllib.parse\nimport http\nfrom http import HTTPStatus\n",
        )
        == {}
    )


def test_shell_rule_triggers(tmp_path: Path) -> None:
    for i, src in enumerate(
        (
            "import subprocess\nsubprocess.run('ls', shell=True)\n",
            "import subprocess as sp\nsp.Popen(cmd, shell=flag)\n",
            "from subprocess import call\ncall('ls', shell=True)\n",
            "import os\nos.system('ls')\n",
            "import os\nos.popen('ls')\n",
        )
    ):
        assert _write(tmp_path, f"d{i}", src) == {f"d{i}/m.py": ["shell"]}, src


def test_shell_rule_allows_plain_subprocess(tmp_path: Path) -> None:
    src = (
        "import subprocess\nsubprocess.run(['ls'], check=True)\n"
        "subprocess.run(['ls'], shell=False)\n"
    )
    assert _write(tmp_path, "core", src) == {}


def test_unsafe_rule_triggers(tmp_path: Path) -> None:
    for i, src in enumerate(
        (
            "import pickle\npickle.loads(b'')\n",
            "import pickle\npickle.load(f)\n",
            "from pickle import loads\nloads(b'')\n",
            "import marshal\n",
            "import yaml\nyaml.load(s)\n",
            "import yaml\nyaml.load(s, Loader=yaml.Loader)\n",
            "import yaml\nyaml.load(s, yaml.FullLoader)\n",
            "import yaml\nyaml.unsafe_load(s)\n",
        )
    ):
        assert _write(tmp_path, f"d{i}", src) == {f"d{i}/m.py": ["unsafe"]}, src


def test_unsafe_rule_allows_safe_yaml(tmp_path: Path) -> None:
    src = (
        "import yaml\nyaml.safe_load(s)\nyaml.load(s, Loader=yaml.SafeLoader)\n"
        "yaml.load(s, yaml.CSafeLoader)\n"
    )
    assert _write(tmp_path, "core", src) == {}


def test_bind_rule_triggers_only_in_sidecar(tmp_path: Path) -> None:
    for i, src in enumerate(
        (
            "import uvicorn\nuvicorn.run(app, host='0.0.0.0')\n",
            "HOST = '::'\n",
            "uvicorn.run(app, host='192.168.1.5', port=1)\n",
        )
    ):
        assert _write(tmp_path, f"sidecar{i}", src) == {}, (
            "not under sidecar/, rule is off"
        )
    (tmp_path / "sidecar").mkdir()
    for i, src in enumerate(
        (
            "import uvicorn\nuvicorn.run(app, host='0.0.0.0')\n",
            "HOST = '::'\n",
            "uvicorn.run(app, host='192.168.1.5', port=1)\n",
        )
    ):
        (tmp_path / "sidecar" / f"m{i}.py").write_text(src, encoding="utf-8")
    assert scan([tmp_path / "sidecar"], base=tmp_path) == {
        f"sidecar/m{i}.py": ["bind"] for i in range(3)
    }


def test_bind_rule_allows_loopback(tmp_path: Path) -> None:
    (tmp_path / "sidecar").mkdir()
    (tmp_path / "sidecar" / "ok.py").write_text(
        "uvicorn.run(app, host='127.0.0.1', port=0)\n", encoding="utf-8"
    )
    assert scan([tmp_path / "sidecar"], base=tmp_path) == {}


def test_allowlist_exempts_only_its_rule_and_file(tmp_path: Path, monkeypatch) -> None:
    d = tmp_path / "core"
    d.mkdir()
    (d / "dl.py").write_text("import socket\nimport marshal\n", encoding="utf-8")
    monkeypatch.setitem(
        ALLOWLIST, "net", {"core/dl.py": "invented reason for this test only"}
    )
    assert scan([d], base=tmp_path) == {"core/dl.py": ["unsafe"]}
