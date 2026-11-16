"""Scan the repo and its full git history for things that must never be committed.

    uv run python -m eval.repo_scan

Three checks, run over every blob in every commit of every ref plus the working-tree
copy of every tracked file:
  1. secrets: Gemini, Groq, Anthropic and OpenAI key patterns, and any value in .env
  2. forbidden paths ever committed: .env, *.gguf, data/raw, data/cache,
     data/processed, models/
  3. restricted text: any sentence of 12+ characters from a document whose
     license_class is restricted or unknown. The index is built from text-layer-only
     extraction (no OCR) of every such PDF and HTML document, cached in the gitignored
     data/processed/<doc_id>/sentences_textlayer.json. Scanned pages are skipped and
     counted.

Read-only: only `git rev-list`, `git cat-file` and `git ls-files` are ever run (git()
refuses anything else). A match is never printed: a finding is the file, the check and,
for restricted text, the first 8 characters of the doc id and the sentence length.
Exit code 1 unless every finding is allowlisted (see ALLOWED_* and
eval/repo_scan_allow.json); allowlisted hits are counted by kind in the report.
"Known debt" (restricted sentences in listed files, see known_debt in the allow file)
passes in the default mode but stays listed; `--public` counts it as a finding, so the
repo may be made public only when `--public` exits 0.
`--tree-only` skips git history: it scans the tracked files as they are on disk and
nothing else, so it says nothing about old commits. `--tree-only --public` is the
check that the working tree carries zero known debt; the history still has to be
dropped (fresh history, D-64) before the repo goes public.
Dev-time only: never imported by the app.
"""

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from shiori_core.html_ingest import load_html_document
from shiori_core.ingest import PasswordProtectedError, load_document
from shiori_core.models import EXTRACTOR_VERSION

from collector.manifest import ManifestRow, read_bundles, read_rows
from eval.silver.keys import _dotenv

READ_ONLY_GIT = {"rev-list", "cat-file", "ls-files"}
MIN_SENTENCE = 12
MIN_ENV_VALUE = 8
SECRET_PATTERNS = {
    "Gemini key pattern": rb"AIza[0-9A-Za-z_\-]{35}",
    "Groq key pattern": rb"gsk_[0-9A-Za-z]{20,}",
    "Anthropic key pattern": rb"sk-ant-[0-9A-Za-z_\-]{20,}",
    "OpenAI key pattern": rb"(?<![0-9A-Za-z])sk-(?!ant-)[0-9A-Za-z_\-]{20,}",
}
URL_RE = re.compile(r"https?://\S+")
ALLOW_PATH = Path("eval/repo_scan_allow.json")
PROCESSED_DIR = Path("data/processed")
TEXTLAYER_FILE = "sentences_textlayer.json"
FORBIDDEN_DIRS = ("data/raw", "data/cache", "data/processed", "models")

# The allowlist has these kinds, and every allowed hit is counted in the report:
#  - the fake key SECRET_Q in tests/test_silver.py, matched by the SHA-256 of its value
#    (the value itself is not written here, or this file would trip the scan)
#  - "title": a restricted sentence that equals or sits inside the title_ja of any
#    document or bundle in the manifests, at any length
#  - "url": a restricted sentence that is a single URL found inside some manifest
#    row's url or landing_url
#  - "hash": a reviewed sentence listed by SHA-256 in eval/repo_scan_allow.json
#  - "known debt": restricted text in a file and doc listed under known_debt in the
#    allow file; passes by default, fails with --public
ALLOWED_SECRET_SHA256 = frozenset(
    {"5f17c81548b984bfd32c8b52ee4c95835ecdb21eda609a5518093417c4d82dde"}
)

# first 12 chars -> [(sentence, doc id prefix, allowlist kind or None)]
Index = dict[str, list[tuple[str, str, str | None]]]
Finding = tuple[str, str, str]  # (check, path, detail)


def git(*args: str, stdin: bytes | None = None) -> bytes:
    if args[0] not in READ_ONLY_GIT:
        raise ValueError(f"git {args[0]} is not allowed here (read-only scan)")
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    return subprocess.run(
        ["git", *args], input=stdin, capture_output=True, check=True, env=env
    ).stdout


def forbidden_path(path: str) -> str | None:
    if path.rsplit("/", 1)[-1] == ".env":
        return ".env"
    if path.endswith(".gguf"):
        return "*.gguf"
    for d in FORBIDDEN_DIRS:
        if path == d or path.startswith(d + "/"):
            return d + "/"
    return None


def secret_hits(
    data: bytes,
    env_values: dict[str, bytes],
    allowed_hashes: frozenset[str] = ALLOWED_SECRET_SHA256,
) -> tuple[list[str], list[str]]:
    """(findings, allowlisted). A pattern is allowlisted only if every match of it
    has an allowlisted hash; one other match makes it a finding."""
    hits: list[str] = []
    allowed: list[str] = []
    for name, pat in SECRET_PATTERNS.items():
        found = [m.group() for m in re.finditer(pat, data)]
        if not found:
            continue
        ok = all(hashlib.sha256(m).hexdigest() in allowed_hashes for m in found)
        (allowed if ok else hits).append(name)
    hits += [f"value of {k} from .env" for k, v in env_values.items() if v in data]
    return hits, allowed


def load_allow_hashes(path: Path = ALLOW_PATH) -> frozenset[str]:
    return frozenset(json.loads(path.read_text())["sentence_sha256"])


def allow_kind(
    s: str, titles: str, hashes: frozenset[str], urls: str = ""
) -> str | None:
    """titles: every manifest title_ja joined with newlines. urls: every manifest
    url and landing_url joined with newlines."""
    if s in titles:
        return "title"
    if URL_RE.fullmatch(s) and s in urls:
        return "url"
    if hashlib.sha256(s.encode()).hexdigest() in hashes:
        return "hash"
    return None


DEBT_DETAIL = re.compile(r"doc (\w{8}), \d+ chars")
DebtEntry = dict[str, str]


def load_known_debt(path: Path = ALLOW_PATH) -> list[DebtEntry]:
    """known_debt entries of the allow file, each {path_glob, doc_prefix, reason}."""
    entries = json.loads(path.read_text()).get("known_debt", [])
    for e in entries:
        check_glob(e["path_glob"])
        if not re.fullmatch(r"[0-9a-f]{8}", e["doc_prefix"]):
            raise ValueError(f"known_debt doc_prefix must be 8 hex chars: {e}")
    return entries


def check_glob(glob: str) -> None:
    """A glob may pick files, never sweep a directory or any data folder."""
    last = glob.rsplit("/", 1)[-1]
    if "**" in glob or glob.endswith("/") or last.strip("*?") == "":
        raise ValueError(f"known_debt glob would cover a whole directory: {glob}")
    if glob.startswith(("data/", "models/")):
        raise ValueError(f"known_debt glob may not point into data or models: {glob}")


def split_known_debt(
    findings: list[Finding], entries: list[DebtEntry]
) -> tuple[list[Finding], list[tuple[Finding, int]], list[int]]:
    """(remaining findings, [(known-debt finding, entry index)], stale entry indexes).
    A finding is known debt when its path matches an entry's glob and its doc prefix
    equals the entry's doc_prefix."""
    rest: list[Finding] = []
    debt: list[tuple[Finding, int]] = []
    used: set[int] = set()
    for f in findings:
        m = DEBT_DETAIL.match(f[2]) if f[0] == "restricted text" else None
        hit = next(
            (
                i
                for i, e in enumerate(entries)
                if m
                and m[1] == e["doc_prefix"]
                and fnmatch.fnmatchcase(f[1], e["path_glob"])
            ),
            None,
        )
        if hit is None:
            rest.append(f)
        else:
            debt.append((f, hit))
            used.add(hit)
    return rest, debt, [i for i in range(len(entries)) if i not in used]


def build_index(
    docs: dict[str, list[str]],
    titles: Iterable[str] = (),
    hashes: frozenset[str] = frozenset(),
    urls: Iterable[str] = (),
) -> Index:
    """docs: doc id -> its sentence strings. titles: every manifest title_ja.
    urls: every manifest url and landing_url."""
    blob = "\n".join(titles)
    url_blob = "\n".join(urls)
    idx: Index = defaultdict(list)
    for doc_id, sentences in docs.items():
        for s in set(sentences):
            if len(s) >= MIN_SENTENCE:
                idx[s[:MIN_SENTENCE]].append(
                    (s, doc_id[:8], allow_kind(s, blob, hashes, url_blob))
                )
    return idx


def restricted_hits(
    text: str, idx: Index
) -> tuple[set[tuple[str, int]], set[tuple[str, str]]]:
    """(flagged {(doc prefix, sentence length)}, allowlisted {(doc prefix, kind)})
    for restricted sentences found in text. One pass over the text."""
    if "\\u" in text:  # JSON written with ensure_ascii
        text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), text)
    flagged: set[tuple[str, int]] = set()
    allowed: set[tuple[str, str]] = set()
    for i in range(len(text) - MIN_SENTENCE + 1):
        for s, prefix, kind in idx.get(text[i : i + MIN_SENTENCE], ()):
            if text.startswith(s, i):
                if kind is None:
                    flagged.add((prefix, len(s)))
                else:
                    allowed.add((prefix, kind))
    return flagged, allowed


def scan_file(
    path: str, data: bytes, env_values: dict[str, bytes], idx: Index
) -> tuple[list[Finding], list[Finding]]:
    """(findings, allowlisted hits)."""
    hits, ok = secret_hits(data, env_values)
    out: list[Finding] = [("secrets", path, h) for h in hits]
    allowed: list[Finding] = [("secrets", path, h) for h in ok]
    if b"\0" not in data[:8000]:
        flagged, ok_hits = restricted_hits(data.decode("utf-8", "replace"), idx)
        out += [
            ("restricted text", path, f"doc {p}, {n} chars") for p, n in sorted(flagged)
        ]
        allowed += [
            ("restricted text", path, f"doc {p} via {k}") for p, k in sorted(ok_hits)
        ]
    return out, allowed


def read_blobs(shas: list[str]) -> dict[str, bytes]:
    raw = git("cat-file", "--batch", stdin=("\n".join(shas) + "\n").encode())
    blobs: dict[str, bytes] = {}
    pos = 0
    while pos < len(raw):
        nl = raw.index(b"\n", pos)
        head = raw[pos:nl].split()
        if len(head) < 3:  # "<sha> missing"
            pos = nl + 1
            continue
        size = int(head[2])
        if head[1] == b"blob":
            blobs[head[0].decode()] = raw[nl + 1 : nl + 1 + size]
        pos = nl + 1 + size + 1
    return blobs


def textlayer_texts(row: ManifestRow, processed: Path = PROCESSED_DIR) -> dict:
    """Sentence strings of one document from its text layer only (no OCR), cached
    next to the normal extraction as sentences_textlayer.json (gitignored).
    Returns {"pages", "ocr_skipped", "texts"}; raises on unreadable files."""
    cache = processed / row.doc_id / TEXTLAYER_FILE
    if cache.exists():
        data = json.loads(cache.read_text())
        if data["extractor_version"] == EXTRACTOR_VERSION:
            return data
    if row.format == "html":
        doc = load_html_document(Path(row.path))
        pages = skipped = 0
    else:
        doc = load_document(Path(row.path), ocr=False)
        skipped = sum(1 for p in doc.pages if p.kind in ("scanned", "outlined"))
        pages = len(doc.pages) - skipped
    texts = [t for s in doc.sentences for t in (s.text_orig, s.text_norm)]
    data = {
        "extractor_version": EXTRACTOR_VERSION,
        "pages": pages,
        "ocr_skipped": skipped,
        "texts": texts,
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False))
    return data


def load_restricted_index(
    rows: list[ManifestRow],
    titles: Iterable[str] = (),
    hashes: frozenset[str] = frozenset(),
    processed: Path = PROCESSED_DIR,
    urls: Iterable[str] = (),
) -> tuple[Index, dict[str, int], list[str]]:
    """(index, coverage counts, documents that could not be read as 'prefix: error')."""
    docs: dict[str, list[str]] = {}
    cov = {
        "restricted/unknown documents indexed": 0,
        "  of which html": 0,
        "text-layer pages covered": 0,
        "OCR pages skipped (scanned or outlined)": 0,
        "zip rows without text (skipped)": 0,
        "documents that could not be read (see below)": 0,
    }
    failed: list[str] = []
    for r in rows:
        if r.license_class == "open":
            continue
        if r.format == "zip":
            cov["zip rows without text (skipped)"] += 1
            continue
        try:
            data = textlayer_texts(r, processed)
        except PasswordProtectedError:
            failed.append(f"{r.doc_id[:8]}: password protected")
        except Exception as e:  # one bad file must not hide the rest
            failed.append(f"{r.doc_id[:8]}: {type(e).__name__}")
        else:
            docs[r.doc_id] = data["texts"]
            cov["restricted/unknown documents indexed"] += 1
            cov["  of which html"] += r.format == "html"
            cov["text-layer pages covered"] += data["pages"]
            cov["OCR pages skipped (scanned or outlined)"] += data["ocr_skipped"]
    cov["documents that could not be read (see below)"] = len(failed)
    return build_index(docs, titles, hashes, urls), cov, failed


def scan_repo(
    tree_only: bool = False,
) -> tuple[list[Finding], list[Finding], dict[str, int], list[str]]:
    env_values = {
        k: v.encode() for k, v in _dotenv().items() if len(v) >= MIN_ENV_VALUE
    }
    rows = read_rows()
    titles = {r.title_ja for r in rows} | {b.title_ja for b in read_bundles().values()}
    urls = sorted({u for r in rows for u in (r.url, r.landing_url) if u})
    idx, cov, failed = load_restricted_index(
        rows, sorted(titles), load_allow_hashes(), urls=urls
    )
    findings: set[Finding] = set()
    allowed: set[Finding] = set()

    # history: every object reachable from any ref, with every path it was seen at
    blobs: dict[str, bytes] = {}
    if not tree_only:
        paths: dict[str, set[str]] = defaultdict(set)
        for line in (
            git("rev-list", "--all", "--objects")
            .decode("utf-8", "replace")
            .splitlines()
        ):
            sha, _, path = line.partition(" ")
            if path:
                paths[sha].add(path)
                if (why := forbidden_path(path)) is not None:
                    findings.add(("forbidden paths", path, f"matches {why}"))
        blobs = read_blobs(list(paths))
        for sha, data in blobs.items():
            for path in paths[sha]:
                f, a = scan_file(path, data, env_values, idx)
                findings.update(f)
                allowed.update(a)

    # working tree: tracked files as on disk now (may differ from the last commit)
    tracked = [
        p for p in git("ls-files", "-z").decode("utf-8", "replace").split("\0") if p
    ]
    for path in tracked:
        if (why := forbidden_path(path)) is not None:
            findings.add(("forbidden paths", path, f"matches {why}"))
        f = Path(path)
        if f.is_file():
            fs, a = scan_file(path, f.read_bytes(), env_values, idx)
            findings.update(fs)
            allowed.update(a)

    stats = {
        **({} if tree_only else {"history blobs": len(blobs)}),
        "tracked files": len(tracked),
        ".env values checked": len(env_values),
        **cov,
    }
    return sorted(findings), sorted(allowed), stats, failed


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    public = "--public" in args
    tree_only = "--tree-only" in args
    print(
        "mode: tracked working-tree files only, git history NOT scanned"
        if tree_only
        else "mode: working tree and full git history"
    )
    findings, allowed, stats, failed = scan_repo(tree_only)
    entries = load_known_debt()
    findings, debt, stale = split_known_debt(findings, entries)
    for k, v in stats.items():
        print(f"{k}: {v}")
    for f in failed:
        print(f"  not checked: {f}")
    if public:
        findings += [f for f, _ in debt]
    for check in ("secrets", "forbidden paths", "restricted text"):
        mine = [f for f in findings if f[0] == check]
        print(f"\n{check}: {'FAIL' if mine else 'ok'} ({len(mine)} findings)")
        for _, path, detail in mine:
            print(f"  {path}  [{detail}]")
    if not public:
        print(f"\nknown debt: {len(debt)} (file, doc) pairs, passes without --public")
        for f, i in debt:
            print(f"  {f[1]}  [{f[2]}]  entry {i}")
    for i in stale:
        e = entries[i]
        note = " (tree-only: may still match history)" if tree_only else ""
        print(
            f"warning: stale known_debt entry {i}: {e['path_glob']} {e['doc_prefix']}"
            + note
        )
    n_key = sum(1 for a in allowed if a[0] == "secrets")
    kinds = {
        k: sum(1 for a in allowed if a[2].endswith(f" via {k}"))
        for k in ("title", "url", "hash")
    }
    print(
        f"\nallowlisted (counted, not hidden): {n_key} secret (SECRET_Q), "
        f"{kinds['title']} (file, doc) pairs via title, "
        f"{kinds['url']} via url, {kinds['hash']} via hash, "
        f"{len(debt)} known debt ({len(entries)} entries, {len(stale)} stale)"
    )
    if public:
        print("--public: known debt counts as findings")
    if tree_only:
        print("--tree-only does not cover git history: old commits are not checked")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
