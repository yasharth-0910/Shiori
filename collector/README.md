# collector

Dev-time only, never shipped. Downloads public Japanese tender documents and records provenance.
Writes PDFs to `data/raw/<source>/` and one row per file to `data/manifests/documents.jsonl`.
One adapter per source; follows the rate limit, cache and robots.txt rules in `CLAUDE.md`.

```
uv run python -m collector digital --limit 40 --dry-run   # list bundles and files, download nothing
uv run python -m collector digital --limit 40             # download up to 40 new files, whole bundles only
uv run python -m collector wakayama_pref --limit 1000 --bundles 8   # at most 8 bundles with new files
uv run python -m collector p-portal --limit 150 --dry-run   # searches and fetches notice pages (cached), saves nothing
uv run python -m collector.report                         # rewrite data/manifests/corpus_report.md (keeps the hand-written Spot check section)
```

- `http.py`: the one HTTP client (robots.txt, 3 s per host, User-Agent, 5xx retries, no 403 retry, HTML cache in `data/raw/_http_cache/`).
- `sources/digital.py`, `sources/pportal.py`, `sources/listing.py`: adapters. They only find links and metadata (`discover(client) -> list[Candidate]`). Local-government sites are configs in `sources/sites.py`, one per site, grouped by layout.
- `collect.py`: download, SHA-256 dedupe, PyMuPDF page/text-layer check, manifest and bundle rows.
- `manifest.py`: pydantic models for `documents.jsonl` and `bundles.jsonl`.

`pdf`, `html` and `zip` are saved (PDFs inside ZIPs get their own rows, D-21). docx and xlsx links are listed in the dry run and skipped.
