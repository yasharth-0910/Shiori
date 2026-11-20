# ruff: noqa: E501
"""Throwaway diagnostic: what does the model really answer in the scalar fallback call? (look only, no tuning)

    uv run python -m eval.scalar_probe [prefix ...]      # default: 2f2f5bd3 53320d90 4965207b

Runs the sidecar's path (read_pages, doc type from page 1, segment, rules.extract) and then
llm.extract_scalars through a `complete` that sends the same request llm.Client.complete sends but keeps the
whole response (content, finish_reason, usage, any reasoning text). The raw responses go to
data/cache/scalar_probe/ (gitignored, they hold document text). Only counts and the prompt template are printed.
Starts and stops one llama-server (eval.hybrid.Server, reasoning off). Local only, no cloud call.
"""

import http.client
import json
import sys
from pathlib import Path

from shiori_core.doctype import detect_doc_type, first_page_lines
from shiori_core.extract import llm, rules
from shiori_core.ingest import read_pages
from shiori_core.segment import segment

from eval import hybrid

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/cache/scalar_probe"
DEFAULT = ("2f2f5bd3", "53320d90", "4965207b")


def make_complete(calls: list[dict]):
    def complete(system: str, user: str, schema: dict, max_out: int) -> str:
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
            "max_tokens": max_out,
            "cache_prompt": True,
            "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "strict": True, "schema": schema}},
        }  # same body as llm.Client.complete  # fmt: skip
        conn = http.client.HTTPConnection("127.0.0.1", hybrid.PORT, timeout=llm.TIMEOUT)
        try:
            conn.request(
                "POST",
                "/v1/chat/completions",
                json.dumps(body).encode(),
                {"Content-Type": "application/json"},
            )
            r = json.load(conn.getresponse())
        finally:
            conn.close()
        choice = r["choices"][0]
        calls.append({"max_out": max_out, "finish_reason": choice.get("finish_reason"), "usage": r.get("usage"), "message": choice["message"]})  # fmt: skip
        if choice.get("finish_reason") == "length":
            raise llm.Truncated("answer cut at the token cap")
        return choice["message"]["content"] or ""

    return complete


def probe(prefix: str, manifest: list[dict], splits: dict) -> None:
    rows = [m for m in manifest if m["doc_id"].startswith(prefix)]
    if len(rows) != 1:
        print(f"{prefix}: manifest matches {len(rows)}")
        return
    m = rows[0]
    if splits.get(m["issuer_org"]) == "test":
        print(f"{prefix}: test split, refused")
        return
    doc = read_pages(ROOT / m["path"])
    doc_type = (
        detect_doc_type(first_page_lines(doc.pages[0])) if doc.pages else "notice"
    )
    sents = segment(doc.pages)
    have = set(rules.extract(doc_type, sents))
    asked = [
        f
        for f in llm.SCALAR_FIELDS
        if doc_type in llm.BY_ID[f].applies_to and f not in have
    ]
    calls: list[dict] = []
    stats: list[llm.CallStat] = []
    llm.extract_scalars(doc_type, sents, make_complete(calls), have, stats)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{prefix}.json").write_text(json.dumps({"doc_type": doc_type, "asked": asked, "calls": calls}, ensure_ascii=False, indent=1), encoding="utf-8")  # fmt: skip
    print(f"\n== {prefix} doc_type={doc_type} asked={len(asked)} {asked} sentences_sent={stats[0].sentences_sent if stats else 0} calls={len(calls)}")  # fmt: skip
    for i, c in enumerate(calls, 1):
        text = c["message"].get("content") or ""
        u = c["usage"] or {}
        reasoning = len(c["message"].get("reasoning_content") or "")
        try:
            got = json.loads(text)
            parsed = isinstance(got, dict)
        except ValueError:
            got, parsed = {}, False
        nn = [f for f in asked if isinstance(got, dict) and got.get(f) is not None]
        nul = [
            f for f in asked if isinstance(got, dict) and f in got and got[f] is None
        ]
        absent = [f for f in asked if isinstance(got, dict) and f not in got]
        # a null in this schema is the bare JSON null: there is no slot for a reason
        print(f"call {i}: chars={len(text)} json_ok={parsed} finish={c['finish_reason']} non_null={len(nn)} null={len(nul)} absent={len(absent)} reasoning_chars={reasoning} prompt_tokens={u.get('prompt_tokens')} completion_tokens={u.get('completion_tokens')} of_cap={c['max_out']}")  # fmt: skip
        print(f"  null fields: {nul}; the answer holds text outside the JSON: {text.strip()[:1] != '{' or text.strip()[-1:] != '}'}; any reason written for a null: no slot in the schema (value is the bare null)")  # fmt: skip
        print(f"  non-null: {nn}")


VARIANTS = {
    "A": (llm.SCALAR_SYSTEM, False),
    "B": (llm.SCALAR_SYSTEM.replace(" When unsure, answer null.", ""), False),
    "C": (llm.SCALAR_SYSTEM, True),
    "D": (llm.SCALAR_SYSTEM.replace(" When unsure, answer null.", ""), True),
}


def variants(prefix: str, manifest: list[dict], splits: dict) -> None:
    """Four prompt variants, built here only (llm.py untouched). Prints values and checks, no judgement."""
    import time

    rows = [m for m in manifest if m["doc_id"].startswith(prefix)]
    if len(rows) != 1 or splits.get(rows[0]["issuer_org"]) == "test":
        print(f"{prefix}: not run")
        return
    doc = read_pages(ROOT / rows[0]["path"])
    doc_type = (
        detect_doc_type(first_page_lines(doc.pages[0])) if doc.pages else "notice"
    )
    sents = segment(doc.pages)
    ja = [s for s in sents if s.language == "ja"]
    found = rules.extract(doc_type, sents)
    asked = [
        f
        for f in llm.SCALAR_FIELDS
        if doc_type in llm.BY_ID[f].applies_to and f not in found
    ]
    asked_all_sent = {s.id for s in llm.scalar_sentences(asked, ja)}
    print(f"\n===== {prefix} doc_type={doc_type}")
    print(f"rules already found: {sorted(found)}")
    print(
        f"scalar fields applicable to the type: {[f for f in llm.SCALAR_FIELDS if doc_type in llm.BY_ID[f].applies_to]}"
    )
    print(f"probe asks: {asked}")
    for f in ("title", "issuer_org"):
        if f in found:
            ids = found[f].citations
            alone = {s.id for s in llm.scalar_sentences([f], ja)}
            print(f"rules {f} cites {ids}: in the all-fields sent set {[i in asked_all_sent for i in ids]}; in a {f}-only sent set {[i in alone for i in ids]}")  # fmt: skip
        else:
            print(f"rules did not find {f}")
    by_all = {s.id: s for s in ja}
    saved = {}
    for name, (system, per_field) in VARIANTS.items():
        groups = [[f] for f in asked] if per_field else [asked]
        calls: list[dict] = []
        complete = make_complete(calls)
        tot, nn_total = 0.0, 0
        print(f"--- variant {name}: {len(groups)} call(s), fields asked {len(asked)}")
        for g in groups:
            sent = llm.scalar_sentences(g, ja)
            ids_sent = {s.id for s in sent}
            t0 = time.monotonic()
            try:
                got = json.loads(
                    complete(
                        system,
                        llm.scalar_prompt(g, sent),
                        llm.scalar_schema(g),
                        llm.SCALAR_MAX_OUT,
                    )
                )
            except (OSError, ValueError, KeyError) as e:
                got = {}
                print(f"  call {g}: failed {type(e).__name__}")
            secs = time.monotonic() - t0
            tot += secs
            nn = [f for f in g if isinstance(got.get(f), dict)]
            nn_total += len(nn)
            print(
                f"  call fields={g} sent={len(sent)} non_null={len(nn)} seconds={secs:.1f}"
            )
            for f in nn:
                a = got[f]
                v = a.get("value_ja") or ""
                cit = a.get("citations") or []
                cited = [by_all[c] for c in cit if c in by_all]
                text = "\n".join(c.text_orig for c in cited)
                line = "\n".join(llm.one_line(c) for c in cited)
                exact = bool(v) and (v in text or v in line)
                print(f"    {f}: value_ja={v!r} cited={cit} in_sent_set={[c in ids_sent for c in cit]} exact_substring={exact} extra={ {k: x for k, x in a.items() if k not in ('value_ja', 'citations')} }")  # fmt: skip
        print(f"  total non_null={nn_total} seconds={tot:.1f}")
        saved[name] = calls
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"variants_{prefix}.json").write_text(
        json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def main(argv: list[str]) -> None:
    splits = json.loads((ROOT / "data/eval/splits.json").read_text())
    manifest = [
        json.loads(x)
        for x in (ROOT / "data/manifests/documents.jsonl").read_text().splitlines()
    ]
    hybrid.State.server = hybrid.Server()
    try:
        for p in argv or DEFAULT:
            variants(p, manifest, splits)
    finally:
        hybrid.stop()
    rules_text = llm.scalar_prompt(list(llm.SCALAR_FIELDS), [])
    print("\n--- SYSTEM ---\n" + llm.SCALAR_SYSTEM)
    print("\n--- USER (all 8 fields shown; a document asks only the ones the rules left empty) ---\n" + rules_text.replace("Sentences to read:\n\nAnswer:", "Sentences to read:\n<TEXT>\n\nAnswer:"))  # fmt: skip


if __name__ == "__main__":
    main(sys.argv[1:])
