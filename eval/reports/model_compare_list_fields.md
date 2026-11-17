# Local models on the three list fields (dev split)

Same hybrid extractor for every model: same retrieval, prompts, thresholds and schema, `EXTRACTOR_VERSION` 0.3.0, temperature 0, one llama-server on 127.0.0.1:8792 at a time. Only the GGUF changes (`eval.run --model`). Every number below is from a run executed for this table (`eval/reports/run_cmp_*.json`, `hybrid_cmp_*.md`, `hybrid_diagnostic_cmp_*.md`). The earlier Qwen3.5-9B v3 numbers were not reused: `rules.py` and `eval/hybrid.py` differ from the v3 freeze, so that model was rerun.

**Read with care.** Scores are against model-reviewed dev silver labels (D-41), 14 documents, notices only (specs have no list fields). Small n: a few fields move a rate by several points. Qwen3.5-9B was one of the labelers behind those labels and the prompts were tuned on these documents with it, so it is favored. This is a fit on dev, not a forecast.

Scored fields: eligibility, deadlines, required_documents, one row per (document, field) with a label. Rates as `eval.run.tally`; `wrong value shown` = shown but wrong, or label absent. tok/s is not recorded by the harness (CallStat has seconds only). `model s/doc` = sum of model-call seconds over documents. Diagnostic columns count label items (hit, a not in window, b not produced, c dropped by a check, d wrong value or kind), summed over the three fields.

| model | list fields scored | verified accuracy | value accuracy | not found | wrong value shown | hallucination | citation exists | value in citation | model s/doc | tok/s | calls failed after retry | diagnostic hit / a / b / c / d | run wall s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Qwen3.5-9B-Q4_K_M.gguf` | 39 | 10 of 39 (26%) | 10 of 39 (26%) | 3 of 39 (8%) | 27 of 39 (69%) | 2 of 36 (6%) | 36 of 36 (100%) | 34 of 36 (94%) | 95 | not recorded | 0 of 38 | 123 / 10 / 12 / 2 / 40 | 1344 |
| `Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf` | 39 | 2 of 39 (5%) | 2 of 39 (5%) | 21 of 39 (54%) | 17 of 39 (44%) | 0 of 18 (0%) | 18 of 18 (100%) | 18 of 18 (100%) | 137 | not recorded | 1 of 38 | 59 / 10 / 50 / 2 / 66 | 1927 |
| `NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf` | 39 | 3 of 39 (8%) | 3 of 39 (8%) | 14 of 39 (36%) | 23 of 39 (59%) | 0 of 25 (0%) | 25 of 25 (100%) | 25 of 25 (100%) | 328 | not recorded | 2 of 38 | 62 / 10 / 54 / 3 / 58 | 4599 |
| `LFM2.5-8B-A1B-Q4_K_M.gguf` | 39 | 1 of 39 (3%) | 1 of 39 (3%) | 17 of 39 (44%) | 22 of 39 (56%) | 0 of 22 (0%) | 22 of 22 (100%) | 22 of 22 (100%) | 23 | not recorded | 0 of 38 | 19 / 10 / 79 / 5 / 74 | 328 |
| `qwen3.5-4b-ollama.gguf` | no result (see failures below) | | | | | | | | | | | | |
| `gemma4-e4b-ollama.gguf` | no result (see failures below) | | | | | | | | | | | | |
| `sarashina2.2-3b-instruct-v0.1-Q4_K_M.gguf` | 39 | 1 of 39 (3%) | 1 of 39 (3%) | 39 of 39 (100%) | 0 of 39 (0%) | - (0 of 0) | - (0 of 0) | - (0 of 0) | 74 | not recorded | 38 of 38 | 0 / 10 / 177 / 0 / 0 | 1034 |
| `LFM2.5-1.2B-JP-202606-Q4_K_M.gguf` | 39 | 1 of 39 (3%) | 1 of 39 (3%) | 25 of 39 (64%) | 14 of 39 (36%) | 0 of 14 (0%) | 14 of 14 (100%) | 14 of 14 (100%) | 46 | not recorded | 4 of 38 | 6 / 8 / 99 / 1 / 73 | 641 |
| `Qwen3.5-4B-Q4_K_M.gguf` | 39 | 2 of 39 (5%) | 2 of 39 (5%) | 6 of 39 (15%) | 32 of 39 (82%) | 1 of 33 (3%) | 33 of 33 (100%) | 32 of 33 (97%) | 55 | not recorded | 0 of 38 | 93 / 10 / 24 / 4 / 56 | 781 |
| `gemma-4-E4B-it-Q4_K_M.gguf` | 39 | 10 of 39 (26%) | 10 of 39 (26%) | 8 of 39 (21%) | 22 of 39 (56%) | 0 of 31 (0%) | 31 of 31 (100%) | 31 of 31 (100%) | 75 | not recorded | 0 of 38 | 114 / 10 / 2 / 3 / 58 | 1080 |

## Failures

- `qwen3.5-4b-ollama.gguf`: no result. llama-server exited while loading (RuntimeError in the run, exit 1, 1 to 2 s, no request sent). The same load failure is in `model_loadcheck.md`: for the qwen3.5-4b file the loader rejects `qwen35.rope.dimension_sections` (wrong array length), for the gemma4 file it says `failed to load model` with no further detail in that report. Not retried, not swapped.
- `gemma4-e4b-ollama.gguf`: no result. llama-server exited while loading (RuntimeError in the run, exit 1, 1 to 2 s, no request sent). The same load failure is in `model_loadcheck.md`: for the qwen3.5-4b file the loader rejects `qwen35.rope.dimension_sections` (wrong array length), for the gemma4 file it says `failed to load model` with no further detail in that report. Not retried, not swapped.
- `Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf` ran, calls failed after the retry (error type: count): Truncated 1. Not found is the recorded result for those fields. Cause not investigated.
- `NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf` ran, calls failed after the retry (error type: count): TimeoutError 2. Not found is the recorded result for those fields. Cause not investigated.
- `sarashina2.2-3b-instruct-v0.1-Q4_K_M.gguf` ran, calls failed after the retry (error type: count): HTTPError 38. Not found is the recorded result for those fields. Cause not investigated.
- `LFM2.5-1.2B-JP-202606-Q4_K_M.gguf` ran, calls failed after the retry (error type: count): Truncated 4. Not found is the recorded result for those fields. Cause not investigated.
