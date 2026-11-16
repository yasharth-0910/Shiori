# sidecar

Shipped. FastAPI server that wraps `shiori_core` for the desktop app, bound to 127.0.0.1 with token auth.
Runs a job queue (one document at a time to start) and reports progress per pipeline stage.
Same import rules as `core/`: no dev-time packages, no cloud SDKs.
