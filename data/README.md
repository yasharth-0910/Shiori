# data/

Local data. Most of it is gitignored. Manifests, splits and labels for `open` documents are committed.

```
data/
  raw/                  downloaded PDFs, by source         (ignored)
    <source>/<doc_id>.pdf
  processed/            extractor output per document      (ignored)
    <doc_id>/sentences.json
    <doc_id>/debug.pdf
  cache/                labeler answers, usage ledger, review batches (ignored; holds restricted text)
  manifests/            committed
    documents.jsonl     one row per downloaded file
    bundles.jsonl       groups files that belong to the same tender
    corpus_report.md    stats from collector/report.py
  eval/                 committed: labels for license_class "open" only (D-24)
    splits.json         issuing org -> train | dev | test (frozen, D-40)
    splits.md           the split's constraint checks
    label_set.json      the 60 dev + 40 test documents to label (seed 20261003)
    label_set.md        per-split report of the label set
    dev/labels/<doc_id>.jsonl
    test/labels/<doc_id>.jsonl
    translation/        sentence pairs for hover translation eval
  eval_private/         (ignored) same layout, for "restricted" and "unknown" docs
```

`splits.json`, `splits.md` and `label_set.*` hold org names and doc ids only, never text.

Labels and translation pairs hold source text, so where they go depends on the document's `license_class` (D-22, D-24): `open` -> `data/eval/`, anything else -> `data/eval_private/`. `tests/test_eval_labels.py` fails if a non-open document's labels end up in `data/eval/`.

## Label files

`data/eval/<split>/labels/<doc_id>.jsonl` (open documents) and `data/eval_private/<split>/labels/<doc_id>.jsonl` (the rest), `<split>` from `splits.json`. One JSON line per field, all 23 v1 fields once each. Full format, provenance states and the validator: `docs/eval_protocol.md`; the fields: `docs/field_schema.md` (schema_version 1.0.0).

```json
{"doc_id": "...", "extractor_version": "0.3.0", "schema_version": "1.0.0",
 "field": "bid_bond", "status": "present", "value_ja": "入札保証金 免除",
 "normalized": {"status": "waived", "rate_percent": null}, "value_en": "Bid bond: waived",
 "citations": ["p3_s12"],
 "provenance": {"pre_labelers": [{"provider": "...", "model": "...", "date": "2026-10-05"}],
   "agreement": null, "auto_checks": [{"name": "citations_exist", "passed": true}],
   "reviewed_by": null, "review_note": null, "final_state": "silver_unreviewed"}}
```

`final_state` is `silver_unreviewed`, `silver_consensus`, `silver_model_reviewed` or `human_audited`; only a native speaker's review gives the last (D-41). Check files with `uv run python -m eval.validate_labels`.

## documents.jsonl row

```json
{
  "doc_id": "sha256 of file bytes",
  "source": "p-portal | jpo | jetro | kanpo | kkj | ...",
  "url": "direct file URL",
  "landing_url": "page the link was found on",
  "issuer_org": "as written on the page, Japanese",
  "title_ja": "as written on the page",
  "doc_type": "notice | bid_instructions | spec | evaluation_criteria | draft_contract | forms | rfi_material | tender_page | qa | result | other",
  "notice_date": "YYYY-MM-DD or null",
  "wto_covered": true,
  "jetro_ref": "JETRO notice URL if matched, else null",
  "pages": 12,
  "text_layer": "full | partial | none",
  "fetched_at": "ISO datetime",
  "license_note": "e.g. 政府標準利用規約 2.0, checked on site",
  "license_class": "open | restricted | unknown",
  "format": "pdf | html | zip",
  "extracted_from": "doc_id of the ZIP this PDF came out of, else null",
  "has_english_summary": "true | false for p-portal notices, else null",
  "is_it": "true if システム, クラウド, ソフトウェア, データ or 開発 is in the title or a bundle title (D-27)",
  "path": "data/raw/<source>/<doc_id>.<format>"
}
```

PDFs that need an open password (the empty password fails) are skipped, as are responses that are not PDFs: nothing is written and no row is added (first case: Niigata, part E). `text_layer` and `pages` are filled in by a quick check after download (PyMuPDF; a page has text if it yields 20 or more non-space characters), not trusted from the source. Both are `null` for `html` and `zip` rows.

`doc_type` values added in part E (2026-10-02): `tender_page` is a saved HTML page around a tender whose notice is a separate PDF (before: `other`). `qa` is answers to bidders' questions (質問回答, 質疑応答, 回答書). `result` is award or evaluation results (入札結果, 審査結果, 開札録), including HTML pages whose title says they only announce results (`...の結果について`, `...結果の公表`). Cues are in `collector/collect.py` (`DOC_TYPE_CUES`, `classify_page`). Existing rows were re-tagged in place on 2026-10-02 with the same code (59 `other` rows, 6 html `notice` rows that only announce results or answers); this is the one exception to append-only so far.

`is_it` (D-27) is set at collection time and was back-filled for all rows on 2026-10-02, in the same pass that re-tagged rows for the 公募文, 落札者決定基準 and 申告調書 cues (11 rows, see decisions.md D-27 and the Phase 1 close-out).

`has_english_summary` (part E): for p-portal notices, whether the notice body has the English `Summary` section that WTO notices carry. `null` for every other source.

`doc_type` `rfi_material` covers every file posted for a request for information (情報提供依頼), including draft specs inside an RFI. They describe a planned procurement, not a tender you can bid on.

ZIPs (D-21): the ZIP gets its own row (`format: "zip"`) for provenance. Each PDF inside gets a separate row with `extracted_from` set to the ZIP's doc_id, `url` set to `<zip url>#<member name>`, and `title_ja` from the member's file name. Only the extracted PDFs go into the bundle. docx and xlsx inside ZIPs are skipped for now.

`license_class` (D-16): `open` (PDL1.0, 政府標準利用規約, or anything CC BY compatible) may go into a published eval set. `restricted` (all rights reserved) is used only locally for training and dev, never published. `unknown` is treated as `restricted`.

`format` is `html` for notices that only exist as a web page (p-portal, D-18; tender pages whose text is the notice, D-20). The raw page bytes are stored as served.

Rows are validated by `collector.manifest.ManifestRow` on every read and write. The file is append-only; fix mistakes by hand with a note.

## bundles.jsonl row

```json
{"bundle_id": "...", "issuer_org": "...", "title_ja": "...", "doc_ids": ["...", "..."]}
```

`bundle_id` is `<source>:<key>`, where the key comes from the tender page (e.g. `funabashi:p146281`, `digital:<page uuid>`, `digital:rfi-<hash of the RFI's first file link>`). Written by the collector, which rewrites the file after each bundle.
