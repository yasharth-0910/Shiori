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
    for line in labels[0].read_text().splitlines():
        lab = json.loads(line)
        cites = []
        for sid in lab["citations"]:
            s = sentences[sid]
            cites.append(
                {
                    "id": sid,
                    "page": s["page"],
                    "text_ja": s["text_orig"],
                    # PDF points, origin top-left, as displayed (core/models.py)
                    "boxes": [{"page": b["page"], "bbox": b["bbox"]} for b in s["boxes"]],
                }
            )
        fields.append(
            {
                "field": lab["field"],
                "status": lab["status"],
                "value_en": lab["value_en"],
                "value_ja": lab["value_ja"],
                "citations": cites,
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / row["path"], OUT / "doc.pdf")
    (OUT / "fixture.json").write_text(
        json.dumps({"doc_id": doc_id, "pdf": "doc.pdf", "fields": fields}, ensure_ascii=False, indent=1)
    )
    n_cites = sum(len(f["citations"]) for f in fields)
    print(f"doc {doc_id[:8]}: {len(fields)} fields, {n_cites} citations -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
