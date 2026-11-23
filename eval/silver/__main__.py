# ruff: noqa: E501
"""uv run python -m eval.silver [--local-focused] {keys,probe,status,plan,run,daemon,shadow,repair,resolve,report,reopen,export,import,calibrate,show,review-stats,replay,webimport}
(see --help)."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from eval.silver import config
from eval.silver.keys import ENV_NAMES, get_key
from eval.silver.run import (
    plan_text,
    run_docs,
    run_notes,
    select,
    status_text,
)  # fmt: skip


def _rows(a: argparse.Namespace):
    if getattr(a, "pilot", False):
        return select(None, True, list(config.PILOT))
    return select(a.split, a.open_only, a.docs.split(",") if a.docs else None)


def _ledger(provider: str, model: str, kind: str, outcome: str) -> None:
    """Key checks and probes go into the usage ledger like labeling calls."""
    from eval.silver.limiter import Ledger

    Ledger().append(ts=datetime.now(UTC).timestamp(), provider=provider, model=model,
                    kind=kind, outcome=outcome, ok=outcome == "ok",
                    tokens_in=0, tokens_out=0)  # fmt: skip


def probe(provider: str) -> int:
    """One tiny generation request (a few tokens), recorded in the ledger: is the model
    answering right now? Prints the outcome, never a key or a response."""
    from eval.silver.pipeline import _default_factory
    from eval.silver.providers import ProviderError

    prov = _default_factory(provider)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
              "required": ["ok"], "additionalProperties": False}  # fmt: skip
    try:
        c = prov.complete("Reply with JSON.", 'Return {"ok": true}.', schema, 64)
    except ProviderError as e:
        _ledger(provider, prov.model, "probe", e.outcome)
        print(f"{provider}: {e.outcome}")
        return 1
    from eval.silver.limiter import Ledger

    Ledger().append(ts=datetime.now(UTC).timestamp(), provider=provider, model=prov.model,
                    kind="probe", outcome="ok", ok=True,
                    tokens_in=c.tokens_in, tokens_out=c.tokens_out)  # fmt: skip
    print(f"{provider}: ok")
    return 0


def keys() -> int:
    """One list-models request per provider; prints works / the HTTP error, never a key.
    Each request is a ledger line (kind keys)."""
    import json
    import urllib.error
    import urllib.request

    urls = {
        "gemini": ("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1", "x-goog-api-key", ""),
        "groq": ("https://api.groq.com/openai/v1/models", "Authorization", "Bearer "),
    }  # fmt: skip
    bad = 0
    for p, (url, hdr, pre) in urls.items():
        key = get_key(p)
        if not key:
            print(f"{p}: no {ENV_NAMES[p]} in the environment or .env")
            bad += 1
            continue
        req = urllib.request.Request(
            url, headers={hdr: pre + key, "User-Agent": "shiori-dev/0.1"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                json.load(r)
            _ledger(p, "list-models", "keys", "ok")
            print(f"{p}: works")
        except urllib.error.HTTPError as e:
            _ledger(p, "list-models", "keys", f"http_{e.code}")
            print(f"{p}: HTTP {e.code}")
            bad += 1
        except OSError as e:
            _ledger(p, "list-models", "keys", "network")
            print(f"{p}: {type(e).__name__}")
            bad += 1
    return 1 if bad else 0


def shadow(rows, gguf: str) -> int:
    """Label with a local model only (same prompt), for comparison: writes the raw
    answer cache, never a label, a resolved line or a review item."""
    from eval.silver.pipeline import Pipeline
    from eval.silver.run import ja_sentences

    pipe = Pipeline()
    key = "local:" + gguf
    try:
        for row in rows:
            raw = pipe.label(row, ja_sentences(row), key, retry_failed=True)
            secs = sum(c.get("seconds", 0) for c in raw["chunks"].values())
            print(f"{row.doc_id[:12]}: {len(raw['chunks'])} parts, {secs:.0f} s")
    finally:
        pipe.close()
    return 0


def repair(rows, gguf: str) -> int:
    """The shape check and one repair request on the local model's cached answers
    (D-52): repair requests only, no full re-run, no cloud call."""
    from eval.silver.pipeline import Pipeline
    from eval.silver.run import ja_sentences

    pipe = Pipeline()
    try:
        for row in rows:
            for p in pipe.repair_cached(row, ja_sentences(row), "local:" + gguf):
                fixed = (
                    len(set(p["before"]) - set(p["after"]))
                    if p["kept"] == "repair"
                    else 0
                )
                print(f"{row.doc_id[:12]} part {p['part'] + 1}: {len(p['before'])} fields with problems, "
                      f"{fixed} fixed, kept {p['kept']}, {p['seconds']:.0f} s")  # fmt: skip
    finally:
        pipe.close()
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m eval.silver", description=__doc__)
    ap.add_argument(
        "--local-focused",
        action="store_true",
        help="the local labeler asks list fields and contact one per call (prompt "
        f"{config.LOCAL_PROMPT_VERSION}{config.FOCUSED_SUFFIX}, cached apart); give it to "
        "every command that reads or writes those answers",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    def sel(p: argparse.ArgumentParser, pilot: bool = True) -> None:
        p.add_argument("--split", choices=["dev", "test"], default="dev")
        p.add_argument("--open-only", action="store_true")
        p.add_argument("--docs", help="comma-separated doc id prefixes")
        if pilot:
            p.add_argument(
                "--pilot", action="store_true", help="the 5 pilot documents (open, dev)"
            )

    sub.add_parser("keys", help="one list-models request per provider")
    sub.add_parser(
        "probe", help="one tiny generation request (recorded in the ledger)"
    ).add_argument("provider", choices=["gemini", "groq"])
    rs = sub.add_parser(
        "review-stats", help="per provider: how often its candidate was right"
    )
    rs.add_argument(
        "--answers",
        type=Path,
        help="compute from an answers file and the export batches (the pilot) "
        "instead of reviews.jsonl",
    )
    rs.add_argument("--out", type=Path)
    rp = sub.add_parser(
        "replay",
        help="pilot review as a regression set: mapping, review stats, agreement rules",
    )
    rp.add_argument("--answers", type=Path, help="default: answers/pilot-all.txt")
    rp.add_argument("--out", type=Path)
    rp.add_argument(
        "--write-mapping",
        action="store_true",
        help="write the recovered A/B mapping of the pilot items to export/mapping.json",
    )
    sub.add_parser(
        "status", help="accepted / flagged / failed per document, usage today"
    ).add_argument("--split", choices=["dev", "test"])
    sel(
        sub.add_parser(
            "plan", help="calls, tokens and days of free quota; no API calls"
        )
    )
    r = sub.add_parser(
        "run", help="label with the providers (needs --yes and --max-calls)"
    )
    sel(r)
    r.add_argument("--yes", action="store_true")
    r.add_argument("--max-calls", type=int)
    r.add_argument("--retry-failed", action="store_true")
    r.add_argument(
        "--allow-test",
        action="store_true",
        help="label the test split (only with the frozen prompt version)",
    )
    rep = sub.add_parser(
        "report",
        help=f"rebuild eval/reports/silver_pilot_{config.PROMPT_VERSION}.md from the caches (no API calls)",
    )
    sel(rep)
    rep.add_argument(
        "--notes", type=Path, help="hand-written section put after the title"
    )
    sh = sub.add_parser(
        "shadow", help="label with a local model only, for the report (no labels)"
    )
    sel(sh)
    sh.add_argument(
        "--model", default=config.LOCAL_MODELS[0][0], help="gguf in models/"
    )
    rr = sub.add_parser(
        "repair",
        help="shape check + one repair request on cached local answers (no cloud call)",
    )
    sel(rr)
    rr.add_argument(
        "--model", default=config.LOCAL_MODELS[0][0], help="gguf in models/"
    )
    sel(
        sub.add_parser(
            "resolve", help="resolve documents from the raw cache only (no API calls)"
        )
    )
    ro = sub.add_parser(
        "reopen",
        help="turn an accepted consensus field back into a review item (a written "
        "label file is rewritten only when the review is imported)",
    )
    ro.add_argument("doc", help="doc id prefix")
    ro.add_argument("field")
    ro.add_argument("--reason", required=True, help="shown to the reviewer")
    ro.add_argument(
        "--with",
        dest="extra",
        help="one more cached answer as the last candidate: a local model name, gemini or "
        "groq, optionally @prompt (default: the line's prompt version)",
    )
    ro.add_argument(
        "--reviewed",
        action="store_true",
        help="also reopen a reviewed line (a new item id; the old review is kept)",
    )
    ro.add_argument(
        "--label",
        action="store_true",
        help="show the label line itself as A instead of its labelers' answers",
    )
    dm = sub.add_parser(
        "daemon",
        help="loop over one gold wave: label within each provider's daily budget, "
        "resolve, export review batches (D-62). Without --yes it only prints the plan",
    )
    dm.add_argument("--gold", action="store_true", required=True)
    dm.add_argument("--wave", type=int, required=True)
    dm.add_argument("--plan", action="store_true")
    dm.add_argument("--retry-failed", action="store_true", help="ask the failed parts of the wave's documents again (the same retry as run --retry-failed)")  # fmt: skip
    dm.add_argument("--yes", action="store_true")
    dm.add_argument("--max-calls", type=int, help="every request incl. retries and local; required with --yes")  # fmt: skip
    sel(sub.add_parser("export", help="write review batches"), pilot=False)
    imp = sub.add_parser("import", help="read the reviewer's answers")
    imp.add_argument("file", type=Path)
    imp.add_argument(
        "--reviewer",
        choices=["claude_chat", "claude_code"],
        default="claude_chat",
        help="claude_chat: a model in chat; claude_code: a Claude Code review session "
        "(docs/review_session.md). Both give silver_model_reviewed",
    )
    cal = sub.add_parser(
        "calibrate", help="compare two answer files for the same batch (writes nothing)"
    )
    cal.add_argument("answers_a", type=Path)
    cal.add_argument("answers_b", type=Path)
    sub.add_parser(
        "webimport",
        help="store Gemini web-chat answers (<dir>/<prefix>.md) as the raw answers of labeler web (D-104)",
    ).add_argument("folder", type=Path)
    sub.add_parser(
        "show", help="print a document's Japanese sentences (id | section | text)"
    ).add_argument("doc", help="doc id prefix")
    a = ap.parse_args(argv)
    config.LOCAL_FOCUSED = a.local_focused

    if a.cmd == "keys":
        return keys()
    if a.cmd == "probe":
        return probe(a.provider)
    if a.cmd == "review-stats":
        import json

        from eval.silver.review import review_stats

        if a.answers:
            from eval.silver import replay as rp_

            items = rp_.load_pilot(a.answers)
            recs = rp_.pilot_records(items, rp_.pilot_mapping(rp_.recover_mapping()))
        else:
            p = config.CACHE / "reviews.jsonl"
            recs = (
                [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
                if p.exists()
                else []
            )
        text = review_stats(recs) if recs else "no reviews recorded yet (reviews.jsonl)"
        if a.out:
            a.out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    if a.cmd == "replay":
        import json

        from eval.silver import replay as rp_

        items = rp_.load_pilot(a.answers)
        verdict = rp_.recover_mapping()
        mapping = rp_.pilot_mapping(verdict)
        text = rp_.report(
            items,
            rp_.relaxation_replay(items),
            verdict,
            rp_.pilot_records(items, mapping),
        )
        text += (
            "\n## Every review round, on the candidates as shown\n\n"
            + rp_.rounds_table(rp_.load_reviews())
            + "\n"
        )
        if a.write_mapping:
            mp = config.CACHE / "export" / "mapping.json"
            old = json.loads(mp.read_text()) if mp.exists() else {}
            mp.write_text(json.dumps({**mapping, **old}, indent=1, sort_keys=True))
            print(f"wrote {mp}")
        if a.out:
            a.out.write_text(text, encoding="utf-8")
            print(f"wrote {a.out}")
        else:
            print(text)
        return 0
    if a.cmd == "status":
        print(status_text(a.split))
        return 0
    if a.cmd == "plan":
        print(plan_text("selection", _rows(a)))
        return 0
    if a.cmd == "report":
        from eval.silver.compare import full_report

        notes = a.notes.read_text(encoding="utf-8") if a.notes else ""
        print(f"wrote {full_report(_rows(a), notes)}")
        return 0
    if a.cmd == "shadow":
        return shadow(_rows(a), a.model)
    if a.cmd == "repair":
        return repair(_rows(a), a.model)
    if a.cmd == "resolve":
        from eval.silver.run import resolve_cached

        print(resolve_cached(_rows(a)))
        return 0
    if a.cmd == "reopen":
        import json

        from eval.silver.review import reopen

        (row,) = select(None, False, [a.doc])
        item = reopen(row, a.field, a.reason, a.extra, a.label, a.reviewed)
        print(
            f"{row.doc_id[:12]} {a.field}: flagged again, {len(item['sides'])} candidates"
        )
        return 0
    if a.cmd == "daemon":
        from eval.silver import daemon

        if not (a.yes and not a.plan):
            print(daemon.plan_text(a.wave, datetime.now(UTC).timestamp(), a.max_calls, a.retry_failed))  # fmt: skip
            return 1 if daemon.tier1_problems() else 0
        if not a.max_calls or a.max_calls < 1:
            print("daemon --yes needs --max-calls N")
            return 2
        if daemon.tier1_problems():
            print("\n".join(daemon.tier1_problems()))
            return 2
        rows, refused = daemon.gold_rows(a.wave)
        for d, why in refused:
            print(f"refused {d[:12]}: {why}")
        print(daemon.Daemon(a.wave, rows, a.max_calls, retry_failed=a.retry_failed).start())  # fmt: skip
        return 0
    if a.cmd == "export":
        from eval.silver.review import export

        paths = export(a.split, a.open_only, lambda s, o: _rows(a))  # honours --docs
        print(f"{len(paths)} batches in {config.CACHE / 'export'}")
        return 0
    if a.cmd == "import":
        from eval.silver.review import import_answers, unsure_ids

        text = a.file.read_text()
        n, errs = import_answers(text, a.reviewer)
        for e in errs:
            print("ERROR", e)
        print(
            f"imported {n} labels (reviewed_by {a.reviewer})"
            if not errs
            else f"{len(errs)} errors, nothing imported"
        )
        unsure = unsure_ids(text)
        if not errs:
            from eval.silver.review import held_paths

            print(f"held {len(unsure)} UNSURE items, not imported"
                  + (f" ({', '.join(unsure)}): {held_paths()[0]}" if unsure else ""))  # fmt: skip
        return 1 if errs else 0
    if a.cmd == "calibrate":
        from eval.silver.review import calibrate

        print(calibrate(a.answers_a.read_text(), a.answers_b.read_text(),
                        a.answers_a.name, a.answers_b.name), end="")  # fmt: skip
        return 0
    if a.cmd == "webimport":
        from eval.silver.webimport import REPORT, webimport

        text, n = webimport(a.folder)
        print(text)
        print(f"wrote {REPORT}; {n} failures or refusals")
        return 1 if n else 0
    if a.cmd == "show":
        from eval.silver.prompt import line
        from eval.silver.run import ja_sentences

        (row,) = select(None, False, [a.doc])
        print(
            f"doc {row.doc_id} | doc_type {row.doc_type} | license {row.license_class}"
        )
        for s in ja_sentences(row):
            print(line(s))
        return 0
    # run
    if not (a.yes and a.max_calls):
        print("run needs both --yes and --max-calls N")
        return 2
    if a.split == "test" and not a.pilot and not a.allow_test:
        print(
            "the test split is labeled once, at the end, with the frozen prompt version: add --allow-test"
        )
        return 2
    rows = _rows(a)
    for note in run_notes(rows, a.max_calls, datetime.now(UTC).timestamp()):
        print("note:", note)
    print(run_docs(rows, a.max_calls, a.retry_failed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
