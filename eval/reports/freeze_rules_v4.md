# Frozen rules extractor (v4)

Record of the files of the rules-only extractor after the six fields were added (award_method, spec_access, submission_modes, delivery_deadline, performance_period, contracting_officer) and the `--diagnose` fix. The v3 record `hybrid_freeze_dev_hybrid_v3.md` is untouched and no longer matches rules.py, run.py or hybrid.py. Written 2026-11-17, nothing committed. `git hash-object` is the id git gives a file once committed, so the ids hold only while the files stay as they are.

There is no unseen set for the six new fields: every score in `rules_v4_side_by_side.md` is a fit to the 14 labeled dev documents the rules were written from.

## Files changed in this task

| file | git blob id | SHA-256 |
| --- | --- | --- |
| `core/shiori_core/extract/rules.py` | `6b9fa83a3295dd7ce439684a64ea32774ce69f2e` | `a8e676bba33abbbf2d85cbaff9008be64d8df0ed81ec089192da7fe055113632` |
| `eval/run.py` | `aade4fd1f7a272c204038f97eb8709e1945b9b6f` | `38680f88cba76e07d874ff5d5f431bd537ae05af023c5308d89a87b96f4913b0` |
| `eval/hybrid.py` | `a55280c7222e867cb72315ab11dcc2fc9e58d8dc` | `8d6c5275e68e65ba4706a1cd36651829b947060fd78674029a4450ef8f11761e` |
| `eval/rules_v4_report.py` | `f8d8cb1e45480603bc80b5157f59f244d3ac809f` | `707cae6ff91eec58d7c8b37d704f128867768159e3314269f8723273870799f6` |
| `tests/test_rules.py` | `0841afa45cb1c5ac600c51465047f4045b197115` | `2583aeab1f1a33ee6d3268336765136cbb01d4a4a8dccfe6f129698fc4be2987` |
| `tests/test_hybrid_diagnostic.py` | `0df86752120b787fa19d607bd39dc0dd372fb16a` | `568548102e13af3c63869f81da6cf0b838e0d7dd746ccb2e9048db4941d6ea49` |

## Files read by the extractor and not changed (must not be edited for the numbers to hold)

| file | git blob id | SHA-256 |
| --- | --- | --- |
| `core/shiori_core/value_normalize.py` | `7e4ead120df964e48fbeb3ec323d4f85b37053b7` | `8c0bc9e98ee88eaba9ec7f4e29d4a4c24d8686c81824295a17788fba23098c92` |
| `core/shiori_core/extract/llm.py` | `2a6acb353538e1c9553cfe3e7958e0c781d67b2f` | `49eed8aa997cc350b73ca01958b901c17658294ef645c6aad27a5309d8125378` |
| `core/shiori_core/fields.py` | `2e4cfff02fee1d747a450ca76cb8df62712e30d9` | `d519f0229a80cba89dc84377b26a5c8492751abec17b311a769072fd254154ae` |

## Settings

- extractor version 0.3.0, schema 1.0.0, no model, no network, no cloud call.
- score: `eval/reports/run_dev_rules_v4.md` (`uv run python -m eval.run --split dev --extractor rules --name dev_rules_v4`) and `eval/reports/rules_v4_side_by_side.md` (`uv run python -m eval.rules_v4_report`).
