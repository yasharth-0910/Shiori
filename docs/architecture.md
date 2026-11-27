# Architecture

Status: planned. Update as things get built. Anything here that turns out wrong gets fixed, not left as history (history goes in decisions.md).

## The big picture

```
+------------------------------------------------------------------+
|  Electron app (user's machine, no network)                       |
|                                                                  |
|  Renderer (React)            Main process (Node)                 |
|  - PDF.js viewer     <-IPC-> - spawns + supervises child procs   |
|  - highlight layer           - holds session tokens              |
|  - fields / summary          - blocks all outbound requests      |
|                              - encrypted doc store, safeStorage  |
|                                   |                 |            |
|                          127.0.0.1:random    127.0.0.1:random    |
|                                   v                 v            |
|                     Python sidecar (FastAPI)   llama-server      |
|                     - shiori_core pipeline     (llama.cpp, GGUF) |
|                     - job queue + progress                       |
+------------------------------------------------------------------+

Dev-time only, never shipped:
  collector/  -> public tender PDFs -> data/raw/
  eval/       -> benchmark reports
  training/   -> LoRA adapters -> merged GGUF -> models/
```

The renderer never talks to the sidecar or the model directly. It sends IPC messages to main, main forwards them over localhost with the session token. This keeps the renderer sandboxed and makes "no network from the UI" easy to enforce with a strict CSP.

## Pipeline (inside the sidecar)

```
PDF
 |
 1. ingest       detect text layer vs scanned, per page
 2. extract      text layer: chars + boxes | scanned: OCR lines + boxes
 3. clean        drop headers/footers, fix reading order, detect tables
 4. normalize    build normalized text + offset map back to original
 5. segment      sentences/items with IDs p{page}_s{n}, section paths
 6. locate       per field: pick candidate sentences (heading cues, BM25)
 7. extract      LLM reads numbered candidates -> JSON (value + sentence IDs)
                 output constrained by JSON schema (llama.cpp grammar)
 8. normalize    dates, amounts, times -> canonical values (deterministic)
 9. verify       cited sentences must actually contain the value
                 fail -> status "not_found" (or "unverified" in debug mode)
10. summarize    executive summary built from verified fields only
11. translate    on demand, single sentence, for hover in the viewer
```

Why this order:

- Steps 1 to 5 are deterministic and testable without any model. Most bugs live here, so they get fixed without touching the LLM.
- Step 6 keeps the model's input small. A 60-page tender doesn't go into a 4B model's context; 20 to 40 relevant sentences do.
- Step 7 asks for sentence IDs, never page numbers or coordinates. Code maps IDs to pages and boxes.
- Step 9 is what makes the citations trustworthy. The model can be wrong; the UI only shows what code could confirm.
- Step 10 never reads the raw document, so the summary can't contain anything that isn't traceable.

## Data model

All models are pydantic classes in `core/shiori_core/models.py`.

```
Document
  id            sha256 of file bytes
  extractor_version
  filename, producer   base name only (no user paths in logs)
  format        "pdf" | "html"
  pages         list[Page]; empty for HTML
  text          HTML only: the extracted text the sentence anchors point into (D-37)
  sentences     list[Sentence], in reading order

Page
  number        1-based
  width, height in PDF points, as displayed (after /Rotate)
  kind          "text" | "scanned" | "outlined" | "mixed" | "blank"
                (scanned and outlined pages are read by OCR, D-36; mixed keep their text layer)
  rotation
  char_count, suspect_chars, image_cover, drawing_count   what the kind came from
  lines         list[Line]

Line
  id            "p{page}_l{n}", reading order
  text, chars   exact characters, each with a box
  bbox
  vertical      bool
  furniture     None | "page_number" | "header_footer" (left out of sentences, D-30)
  cell          the ruled table cell it sits in, or None (D-31)
  source        "text_layer" | "ocr". OCR lines have line-level boxes; the box of each
                character is an even split of the line box (an estimate)

Sentence
  id            "p{page}_s{n}", stable for a given file + extractor version;
                n counts sentences that start on that page. HTML: "h_s{n}" over the document
  page          int, the page it starts on; 0 for HTML
  section_path  e.g. ["3", "(3)"] from 公用文 numbering (D-32)
  section_titles  heading text of each level, same length as section_path
  text_orig     exact original characters, line spans joined with nothing between
  text_norm     normalized text for matching, never for display
  norm_to_orig  offset map (index in text_norm -> index in text_orig)
  boxes         list[LineBox], one per line span: line_id, page, start, end
                (offsets into the line's text) and bbox in PDF points. A sentence
                can have boxes on two pages.
  source        "text_layer" | "ocr" | "html"
  language      "ja" | "en". English text (the Summary section of WTO notices, or Latin-only
                sentences) is "en"; a sentence under a Summary heading carries that
                heading's section path only (D-37)
  anchor        HTML only: TextAnchor(start, end), offsets into Document.text; boxes is empty
  in_table      bool (cell coordinates are on the Line, not yet on the Sentence)

FieldResult
  field         field id from field_schema.md
  value_en      English value shown to the user
  value_ja      the Japanese span as it appears
  normalized    canonical value (ISO date, integer yen, enum...)
  citations     list[sentence_id]
  status        "verified" | "not_found" | "unverified"
  verifier_note why verification passed or failed (debug only)

Summary
  lines         list of {text_en, field_refs: list[field id]}
```

The extractor version is part of the cache key. If segmentation changes, sentence IDs change, so labels record the extractor version they were made with and the eval harness refuses to score mismatched versions.

## Process and port model

- Main process picks two free ports on 127.0.0.1 at startup and generates a random 32-byte token per child.
- Sidecar and llama-server bind to 127.0.0.1 only. Sidecar rejects requests without the token. llama-server is started with `--api-key` set to its token.
- If a child crashes, main restarts it once and surfaces an error to the user on a second crash.
- No child process output reaches a log: llama-server's is discarded, the sidecar's stderr is only counted (D-126).

## Performance targets (to be validated in Phase 4)

| Machine | Target |
|---|---|
| MacBook Air M4, 24 GB | 30-page text PDF fully processed in under 90 s |
| Windows laptop, 16 GB, CPU only | same doc under 4 min, first fields shown within 60 s |
| Scanned 10-page doc (OCR) | under 2 min on the Mac |
| Peak RAM | under 8 GB total for model + sidecar + app |

Fields stream to the UI as they finish, so the user sees results before the whole doc is done.

## Key technology choices

| Concern | Choice | Notes |
|---|---|---|
| Desktop shell | Electron + React + TS + Vite | Cross-platform, PDF.js is native to it |
| PDF rendering | PDF.js | Apache 2.0 |
| PDF text + boxes | PyMuPDF during research | AGPL. Decide before Phase 8: buy license, or switch to pypdfium2 / pdfplumber. See decisions.md |
| OCR | NDLOCR-Lite, PaddleOCR fallback | NDLOCR-Lite runs on CPU, built for Japanese |
| Inference | llama.cpp (`llama-server`) | Metal on Mac, CPU/Vulkan on Windows, JSON schema constrained output |
| Training | mlx-lm on Mac, PEFT/Unsloth on Colab as fallback | Output merged to GGUF |
| Local store | Encrypted files owned by main, one folder per document (AES-256-GCM, Node `crypto`) | Off by default. A key per document, wrapped by one master key held with Electron safeStorage (D-119) |
| Sidecar | FastAPI, packaged with PyInstaller | |

Storage is designed in `storage_design.md` (D-119); privacy is in `privacy.md`.
