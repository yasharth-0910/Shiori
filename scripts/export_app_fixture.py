"""Dev-time: build the static fixture the desktop app shows (Phase 7, step 1).

Reads ONE open-license dev document: its label file (data/eval/dev/labels), its
sentences.json (data/processed) and its PDF (path from the manifest). Writes
app/public/fixture.json and app/public/doc.pdf. Both are gitignored: the fixture
holds document text. Labels stand in for model output, so the viewer can be built
before the model is good. Stdlib only. No network, no model.

  uv run python scripts/export_app_fixture.py <doc_id or unique prefix>
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "public"


def main(prefix: str) -> None:
    labels = [p for p in (ROOT / "data/eval/dev/labels").glob(f"{prefix}*.jsonl")]
    if len(labels) != 1:
        sys.exit(f"need exactly one dev label file for {prefix!r}, found {len(labels)}")
    doc_id = labels[0].stem

    row = next(
        r
        for r in map(json.loads, (ROOT / "data/manifests/documents.jsonl").read_text().splitlines())
        if r.get("doc_id") == doc_id
    )
    if row["license_class"] != "open" or row["format"] != "pdf":
        sys.exit("only open-license PDF documents")

    sentences = {
        s["id"]: s
        for s in json.loads((ROOT / f"data/processed/{doc_id}/sentences.json").read_text())["sentences"]
    }

    fields = []
    cited: dict[str, dict] = {}  # sentence id -> what the viewer needs; cited ids only
    for line in labels[0].read_text().splitlines():
        lab = json.loads(line)
        items = (lab["normalized"] or {}).get("items") if isinstance(lab["normalized"], dict) else None
        items = [
            {"text_ja": i.get("text_ja"), "text_en": i.get("text_en"), "citations": i.get("citations", [])}
            for i in items or []
        ]
        ids = list(dict.fromkeys(lab["citations"] + [c for i in items for c in i["citations"]]))
        for sid in ids:
            s = sentences.get(sid)
            if s:  # a cited id that does not exist stays out: the app shows it as missing
                cited[sid] = {
                    "page": s["page"],
                    "text_orig": s["text_orig"],
                    "section_path": s["section_path"],
                    "section_titles": s["section_titles"],
                    # PDF points, origin top-left, as displayed (core/models.py)
                    "boxes": [{"page": b["page"], "bbox": b["bbox"]} for b in s["boxes"]],
                }
        fields.append(
            {
                "field": lab["field"],
                "status": lab["status"],
                "value_en": lab["value_en"],
                "value_ja": lab["value_ja"],
                "items": items,
                "citations": lab["citations"],
                # the pipeline's own results, copied as stored; the app never recomputes them
                "checks": [{"name": c["name"], "passed": c["passed"]} for c in lab["provenance"]["auto_checks"]],
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / row["path"], OUT / "doc.pdf")
    (OUT / "fixture.json").write_text(
        json.dumps({"doc_id": doc_id, "pdf": "doc.pdf", "fields": fields, "sentences": cited}, ensure_ascii=False, indent=1)
    )
    print(f"doc {doc_id[:8]}: {len(fields)} fields, {len(cited)} cited sentences -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
