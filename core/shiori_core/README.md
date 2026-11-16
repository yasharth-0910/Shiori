# shiori_core

The document pipeline, shipped inside the app. PDF in, sentences with IDs and boxes,
then cited and verified field values and a summary out.
Must make no network requests and must not import `collector`, `eval`, `training` or any cloud SDK
(enforced by `tests/test_import_boundaries.py`).
