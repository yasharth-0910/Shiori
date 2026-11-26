# Shiori v0.1.1

## What Shiori is

Shiori reads Japanese public tender documents (入札公告, 仕様書, 入札説明書) and gives you an English summary and key fields such as the deadline, who can bid and what documents to send. It runs on your own computer, and every field points to the exact Japanese sentence it came from.

## What changed

- The sidecar's built-in telemetry is switched off in code and in its environment (D-117).
- A packaged app now ignores the SHIORI_SHOT variable, so its window always opens.
- The installer is about 17 MB smaller on macOS. Only the en-US locales and llama-server with its libraries are kept.

## What works

- Offline reading of PDFs that have a text layer, and of HTML tender notices.
- English fields with their source sentences. Click a field and the PDF opens at that page with the source text highlighted.
- Deadlines tab and export to CSV and calendar (.ics) files.
- First-run setup: the app can scan your computer for a supported model you already have, or download one. Downloads are checked against a pinned SHA-256 hash.

## What does not work yet

- Scanned PDFs (pages that are images) are refused with a clear message. OCR comes later as an optional download.
- There is no code-signing certificate. The first open needs the normal Gatekeeper (macOS) or SmartScreen (Windows) steps. See the Install section of README.md.
- Documents are kept only while the app is open. Saving them between sessions is not in this version yet.
- Processing takes several minutes per document on a laptop.

## Testing status

Only the macOS Apple Silicon build has been run by hand. The macOS Intel, Windows and Linux installers are built by CI and are untested. The llama.cpp trim was not started on Windows or Linux.

## Privacy

\*Privacy in Shiori means this: the app reads and processes your documents only on your own computer, runs its language model locally, makes no network requests while you work, and sends no telemetry. The only network use is the first-run model download, which sends none of your documents. This describes the shipped app, not how it was built: during development, some public tender documents, including some whose sites reserve rights, were sent to cloud AI services to prepare reference labels (docs/decisions.md, D-111). The app does not call any cloud service.

## License

AGPL-3.0-only. Shiori uses PyMuPDF, which is AGPL-3.0, so the whole app is AGPL-3.0.

## Checksums

Each installer comes with a SHA256SUMS file in the release assets. Compare it with the hash of your download before you run it.
