"""eval.repo_scan finds secrets, forbidden paths and restricted text, and never
runs a git command that writes. Fake keys are built at run time so this file
is clean itself."""

import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from collector.manifest import ManifestRow
from eval.repo_scan import (
    ALLOW_PATH,
    ALLOWED_SECRET_SHA256,
    build_index,
    check_glob,
    forbidden_path,
    git,
    load_allow_hashes,
    load_known_debt,
    load_restricted_index,
    main,
    restricted_hits,
    scan_file,
    scan_repo,
    secret_hits,
    split_known_debt,
)

GEMINI = "AI" + "za" + "A" * 35
GROQ = "gs" + "k_" + "b" * 24
ANTHROPIC = "sk" + "-ant-" + "c" * 24
OPENAI = "sk" + "-proj-" + "d" * 24


@pytest.mark.parametrize(
    "key,label",
    [(GEMINI, "Gemini"), (GROQ, "Groq"), (ANTHROPIC, "Anthropic"), (OPENAI, "OpenAI")],
)
def test_key_patterns(key: str, label: str) -> None:
    hits, allowed = secret_hits(f"x = '{key}'".encode(), {})
    assert hits == [f"{label} key pattern"]
    assert allowed == []


def test_anthropic_key_is_not_also_openai() -> None:
    assert secret_hits(ANTHROPIC.encode(), {})[0] == ["Anthropic key pattern"]


def test_plain_words_with_sk_are_not_keys() -> None:
    assert secret_hits(b"disk-encryption-is-enabled-on-all-hosts", {}) == ([], [])


def test_env_value_found_and_not_echoed() -> None:
    hits, _ = secret_hits(b"token=hunter2hunter2", {"MY_TOKEN": b"hunter2hunter2"})
    assert hits == ["value of MY_TOKEN from .env"]
    assert "hunter2" not in hits[0]


@pytest.mark.parametrize(
    "path,why",
    [
        (".env", ".env"),
        ("sub/.env", ".env"),
        ("models/qwen.bin", "models/"),
        ("models", "models/"),
        ("x/y.gguf", "*.gguf"),
        ("data/raw/p-portal/a.pdf", "data/raw/"),
        ("data/cache/labeling/x.json", "data/cache/"),
        ("data/processed/abc/sentences.json", "data/processed/"),
    ],
)
def test_forbidden_paths(path: str, why: str) -> None:
    assert forbidden_path(path) == why


@pytest.mark.parametrize(
    "path", [".env.example", "data/eval/splits.json", "eval/models.py", "data/rawish/a"]
)
def test_allowed_paths(path: str) -> None:
    assert forbidden_path(path) is None


SENT = "入札参加者は令和八年十月三十日までに提出すること。"
IDX = build_index({"abcdef123456": [SENT, "短い文。"]})


def test_restricted_sentence_found_by_doc_prefix_and_length_only() -> None:
    out, allowed = scan_file("notes.md", f"memo\n{SENT}\nend".encode(), {}, IDX)
    assert out == [("restricted text", "notes.md", f"doc abcdef12, {len(SENT)} chars")]
    assert allowed == []
    assert SENT not in repr(out)


def test_restricted_sentence_inside_json_escapes() -> None:
    escaped = "".join(f"\\u{ord(c):04x}" for c in SENT)
    flagged, allowed = restricted_hits(f'{{"t": "{escaped}"}}', IDX)
    assert flagged == {("abcdef12", len(SENT))}
    assert allowed == set()


def test_short_sentences_and_binary_are_ignored() -> None:
    assert restricted_hits("短い文。", IDX) == (set(), set())
    assert scan_file("a.bin", b"\0" + SENT.encode(), {}, IDX) == ([], [])


def test_git_refuses_write_commands() -> None:
    for cmd in ("commit", "add", "push", "tag", "checkout", "stash"):
        with pytest.raises(ValueError):
            git(cmd)


# --- allowlist kinds, each counted ------------------------------------------------

TITLE = "架空市庁舎情報システム保守業務"
BODY = "本業務の履行期間は契約締結日から令和九年三月三十一日までとする。"
LONG = "架空市" + "あ" * 97  # 100 characters
MANIFEST_TITLES = [TITLE + "（第2回）", LONG + "の件"]
TIDX = build_index({"fedcba987654": [TITLE, BODY, LONG]}, MANIFEST_TITLES)


def test_secret_q_is_allowed_by_its_exact_value() -> None:
    src = Path(__file__).with_name("test_silver.py").read_text()
    value = re.search(r'^SECRET_Q = "([^"]+)"', src, re.M)
    assert value is not None
    assert hashlib.sha256(value[1].encode()).hexdigest() in ALLOWED_SECRET_SHA256
    assert secret_hits(value[1].encode(), {}) == ([], ["Groq key pattern"])


def test_real_key_pattern_outside_the_allowlist_is_flagged() -> None:
    fake = GROQ.encode()
    allow = frozenset({hashlib.sha256(fake).hexdigest()})
    assert secret_hits(fake, {}, allow) == ([], ["Groq key pattern"])
    other = ("gs" + "k_" + "e" * 24).encode()
    assert secret_hits(fake + b" " + other, {}, allow)[0] == ["Groq key pattern"]
    assert secret_hits(other, {}, allow)[0] == ["Groq key pattern"]


def test_title_sentence_is_allowlisted_and_counted() -> None:
    out, allowed = scan_file("m.jsonl", TITLE.encode(), {}, TIDX)
    assert out == []
    assert allowed == [("restricted text", "m.jsonl", "doc fedcba98 via title")]


def test_title_of_any_document_counts_not_only_its_own() -> None:
    idx = build_index({"aaaaaaaa1111": [TITLE]}, MANIFEST_TITLES)
    out, allowed = scan_file("m.md", TITLE.encode(), {}, idx)
    assert out == []
    assert allowed == [("restricted text", "m.md", "doc aaaaaaaa via title")]


def test_title_allowlist_works_at_100_characters() -> None:
    assert len(LONG) == 100
    out, allowed = scan_file("m.md", LONG.encode(), {}, TIDX)
    assert out == []
    assert allowed == [("restricted text", "m.md", "doc fedcba98 via title")]


def test_body_sentence_is_flagged_even_next_to_a_title() -> None:
    out, allowed = scan_file("m.md", f"{TITLE}\n{BODY}".encode(), {}, TIDX)
    assert out == [("restricted text", "m.md", f"doc fedcba98, {len(BODY)} chars")]
    assert allowed == [("restricted text", "m.md", "doc fedcba98 via title")]


def test_reviewed_hash_is_allowlisted_and_other_sentences_are_not() -> None:
    hashes = frozenset({hashlib.sha256(BODY.encode()).hexdigest()})
    idx = build_index({"fedcba987654": [BODY, SENT]}, [], hashes)
    out, allowed = scan_file("m.md", f"{BODY}\n{SENT}".encode(), {}, idx)
    assert allowed == [("restricted text", "m.md", "doc fedcba98 via hash")]
    assert out == [("restricted text", "m.md", f"doc fedcba98, {len(SENT)} chars")]


def test_allow_file_holds_only_hashes_and_labels() -> None:
    raw = ALLOW_PATH.read_text()
    assert raw.isascii()  # no Japanese text can be in it
    hashes = load_allow_hashes()
    assert len(hashes) == 12  # 9 original + 3 open-corpus boilerplate hashes added
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes)


# --- coverage: documents that had no cached sentences ------------------------------


def row(doc_id: str, path: Path, fmt: str = "html", cls: str = "restricted"):
    return ManifestRow.model_validate(
        {
            "doc_id": doc_id,
            "source": "t",
            "url": "u",
            "landing_url": "u",
            "issuer_org": "架空市",
            "title_ja": "架空の件名",
            "doc_type": "notice",
            "notice_date": None,
            "wto_covered": None,
            "jetro_ref": None,
            "pages": None,
            "text_layer": None,
            "fetched_at": "2026-10-01T00:00:00",
            "license_note": "",
            "license_class": cls,
            "format": fmt,
            "is_it": False,
            "path": str(path),
        }
    )


def test_finding_from_a_document_with_no_cached_sentences(tmp_path: Path) -> None:
    page = tmp_path / "d.html"
    page.write_text(f"<html><body><p>{BODY}</p></body></html>", encoding="utf-8")
    processed = tmp_path / "processed"
    rows = [row("c0ffee" * 10 + "abcd", page), row("f" * 64, page, cls="open")]
    idx, cov, failed = load_restricted_index(rows, processed=processed)
    assert failed == []
    assert cov["restricted/unknown documents indexed"] == 1  # the open one is skipped
    assert cov["  of which html"] == 1
    out, _ = scan_file("notes.md", BODY.encode(), {}, idx)
    assert out == [("restricted text", "notes.md", f"doc c0ffeec0, {len(BODY)} chars")]
    cached = processed / rows[0].doc_id / "sentences_textlayer.json"
    assert cached.exists()
    page.unlink()  # a second run reads the cache, not the file
    assert load_restricted_index(rows, processed=processed)[2] == []


def test_scanned_pages_are_skipped_and_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kinds = ["text", "scanned", "outlined", "blank", "mixed"]
    sent = SimpleNamespace(text_orig=BODY, text_norm=BODY)
    doc = SimpleNamespace(
        pages=[SimpleNamespace(kind=k) for k in kinds], sentences=[sent]
    )
    seen = {}

    def fake_load(path: Path, ocr: bool = True) -> SimpleNamespace:
        seen["ocr"] = ocr
        return doc

    monkeypatch.setattr("eval.repo_scan.load_document", fake_load)
    r = row("ab" * 32, tmp_path / "x.pdf", fmt="pdf", cls="unknown")
    _, cov, _ = load_restricted_index([r], processed=tmp_path / "p")
    assert seen["ocr"] is False
    assert cov["text-layer pages covered"] == 3
    assert cov["OCR pages skipped (scanned or outlined)"] == 2


# --- url allow kind -----------------------------------------------------------------

URL = "https://example.invalid/tenders/2026/notice-0001.pdf"
URLS = [
    "https://example.invalid/tenders/2026/notice-0001.pdf?x=1",
    "https://a.invalid/",
]


def test_url_sentence_in_a_manifest_url_is_allowlisted_and_counted() -> None:
    idx = build_index({"fedcba987654": [URL]}, urls=URLS)
    out, allowed = scan_file("m.md", URL.encode(), {}, idx)
    assert out == []
    assert allowed == [("restricted text", "m.md", "doc fedcba98 via url")]


def test_url_not_in_any_manifest_is_flagged() -> None:
    idx = build_index({"fedcba987654": [URL]}, urls=["https://a.invalid/other"])
    out, allowed = scan_file("m.md", URL.encode(), {}, idx)
    assert out == [("restricted text", "m.md", f"doc fedcba98, {len(URL)} chars")]
    assert allowed == []


def test_url_allow_needs_a_sentence_that_is_only_a_url() -> None:
    sent = "詳細は " + URL + " を参照すること。"
    idx = build_index({"fedcba987654": [sent]}, urls=URLS)
    out, _ = scan_file("m.md", sent.encode(), {}, idx)
    assert len(out) == 1


# --- known debt ----------------------------------------------------------------------

DEBT = [
    {"path_glob": "notes/old_*.md", "doc_prefix": "fedcba98", "reason": "test"},
    {"path_glob": "gone.md", "doc_prefix": "fedcba98", "reason": "test"},
]
HIT = ("restricted text", "notes/old_a.md", "doc fedcba98, 20 chars")


def test_known_debt_is_split_out_and_stale_entry_is_reported() -> None:
    rest, debt, stale = split_known_debt([HIT], DEBT)
    assert rest == []
    assert debt == [(HIT, 0)]
    assert stale == [1]


def test_same_glob_but_other_doc_prefix_is_still_flagged() -> None:
    other = ("restricted text", "notes/old_a.md", "doc 01234567, 20 chars")
    rest, debt, _ = split_known_debt([other], DEBT)
    assert rest == [other]
    assert debt == []


def test_other_path_with_same_doc_prefix_is_still_flagged() -> None:
    other = ("restricted text", "notes/new_a.md", "doc fedcba98, 20 chars")
    assert split_known_debt([other], DEBT)[0] == [other]


@pytest.mark.parametrize(
    "glob",
    ["data/raw/*.pdf", "tests/*", "tests/**", "docs/", "*", "models/x.bin", "**/*.md"],
)
def test_globs_that_sweep_a_directory_are_rejected(glob: str) -> None:
    with pytest.raises(ValueError):
        check_glob(glob)


def test_file_glob_is_accepted() -> None:
    check_glob("tests/fixtures/collector/funabashi_*.html")


def run_main(monkeypatch, capsys, argv: list[str]) -> tuple[int, str]:
    monkeypatch.setattr(
        "eval.repo_scan.scan_repo", lambda tree_only=False: ([HIT], [], {}, [])
    )
    monkeypatch.setattr("eval.repo_scan.load_known_debt", lambda: DEBT)
    code = main(argv)
    return code, capsys.readouterr().out


def test_known_debt_passes_by_default_and_stays_visible(monkeypatch, capsys) -> None:
    code, out = run_main(monkeypatch, capsys, [])
    assert code == 0
    assert "notes/old_a.md" in out and "fedcba98" in out
    assert "1 known debt (2 entries, 1 stale)" in out
    assert "warning: stale known_debt entry 1" in out


def test_known_debt_fails_with_public(monkeypatch, capsys) -> None:
    code, out = run_main(monkeypatch, capsys, ["--public"])
    assert code == 1
    assert "restricted text: FAIL (1 findings)" in out


def test_allow_file_known_debt_is_ascii_file_level_and_documented() -> None:
    entries = load_known_debt()
    assert all(e["reason"].isascii() and e["doc_prefix"].isascii() for e in entries)


# --- --tree-only: tracked files only, no history -----------------------------------

INVENTED = "これは架空の文書だけに出てくる十分に長い一文です。"


def fake_repo(monkeypatch, tree_text: str, history_text: str):
    """A repo whose history holds history_text and whose tracked file holds tree_text.
    Returns the list of git subcommands that were run."""
    calls: list[str] = []
    blob = history_text.encode()

    def fake_git(*args: str, stdin: bytes | None = None) -> bytes:
        calls.append(args[0])
        if args[0] == "rev-list":
            return b"abc123 notes/old.md\n"
        if args[0] == "cat-file":
            return b"abc123 blob %d\n" % len(blob) + blob + b"\n"
        return b"notes/now.md\0"  # ls-files

    idx = build_index({"fedcba9876543210": [INVENTED]})
    monkeypatch.setattr("eval.repo_scan.git", fake_git)
    monkeypatch.setattr("eval.repo_scan.read_rows", lambda: [])
    monkeypatch.setattr("eval.repo_scan.read_bundles", lambda: {})
    monkeypatch.setattr("eval.repo_scan._dotenv", lambda: {})
    monkeypatch.setattr("eval.repo_scan.load_allow_hashes", lambda: frozenset())
    monkeypatch.setattr(
        "eval.repo_scan.load_restricted_index", lambda *a, **k: (idx, {}, [])
    )
    if tree_text:  # cwd is the test's tmp_path
        Path("notes").mkdir()
        Path("notes/now.md").write_text(tree_text)
    return calls


def test_tree_only_skips_history_hits_and_never_reads_history(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    calls = fake_repo(monkeypatch, "", INVENTED)
    findings, _, stats, _ = scan_repo(tree_only=True)
    assert findings == []
    assert "rev-list" not in calls and "cat-file" not in calls
    assert "history blobs" not in stats


def test_plain_mode_still_reads_history(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    calls = fake_repo(monkeypatch, "", INVENTED)
    findings, _, stats, _ = scan_repo()
    assert [f[:2] for f in findings] == [("restricted text", "notes/old.md")]
    assert "rev-list" in calls and stats["history blobs"] == 1


def test_tree_only_public_fails_on_a_known_debt_hit(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "eval.repo_scan.scan_repo", lambda tree_only=False: ([HIT], [], {}, [])
    )
    monkeypatch.setattr("eval.repo_scan.load_known_debt", lambda: DEBT)
    assert main(["--tree-only"]) == 0
    code = main(["--tree-only", "--public"])
    out = capsys.readouterr().out
    assert code == 1
    assert "history NOT scanned" in out and "does not cover git history" in out
