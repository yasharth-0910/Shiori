# Frozen hybrid extractor (dev_hybrid_v3)

A hold-out score is tied to this version only if every hash below still matches. **Not a generalization number.** The prompts, the retrieval window and the examples were tuned on the same dev documents this is scored on (the prompt examples now come from unlabeled dev documents, not from the 9). The labels are model-reviewed silver labels (D-41), and Qwen3.5-9B itself was one of the two labelers that made the candidates they were reviewed from (D-50), so every score here is optimistic.

## Files

`eval/hybrid.py` is the harness (calls, diagnostic, this record); the extraction itself is llm.py, rules.py, fields.py and value_normalize.py. llm.py, rules.py and fields.py were not edited between the scored run and this record; hybrid.py gained this command after the run.

| file | git blob id (`git hash-object`) | SHA-256 |
| --- | --- | --- |
| `core/shiori_core/extract/llm.py` | `2a6acb353538e1c9553cfe3e7958e0c781d67b2f` | `49eed8aa997cc350b73ca01958b901c17658294ef645c6aad27a5309d8125378` |
| `core/shiori_core/extract/rules.py` | `7aa391386e4ad6b9f15ca32ab6f3b52adc1fae87` | `1ea33cc58343adc1b3b5c434012faffc4f069cb13991ef87c960062ed694c5f4` |
| `core/shiori_core/fields.py` | `2e4cfff02fee1d747a450ca76cb8df62712e30d9` | `d519f0229a80cba89dc84377b26a5c8492751abec17b311a769072fd254154ae` |
| `core/shiori_core/value_normalize.py` | `7e4ead120df964e48fbeb3ec323d4f85b37053b7` | `8c0bc9e98ee88eaba9ec7f4e29d4a4c24d8686c81824295a17788fba23098c92` |
| `eval/hybrid.py` | `863f1e898ceee4746862be8ae266cd7e83ba72f9` | `659e2413e5628c18b6fbfad1a1d6c332db998b0066159280c12ce873863b79c2` |

## Prompts as sent (no sentences) and schemas

| field | prompt SHA-256 | schema SHA-256 |
| --- | --- | --- |
| system message | `a42e4e35f6ee720c57404a7b1922bffaa020c3378c842e2f2de1de1217f5aee2` | |
| eligibility | `09b0a08cc2ba7ee59cf33fc17ed311e819f599ac2e82cbc52e91508d96f0b542` | `90cc0da4aefd996a314d6d6805666d8fa836633d22baeb38c266e138c0cf9bc7` |
| deadlines | `c38e71706095b2c119007e7bb79d86a9684437ff9e5b854228b059f5b4505abe` | `a09172cf8d6ed7435234dece7f5fa30b88bee637fd12c9c185c7f168db339106` |
| required_documents | `4c6a2ef2c232e1d3dd0825d8ca2dd28ce3936478f8f6d6200a214a009f75d401` | `3b1de9f5c040ff9722db13a2acc8597680cc5c7c143ce4ebdc384798b457781c` |

## Settings

- retrieval: window 3 sentences, budget 7000 characters, extra cues {'required_documents': 'deadlines'}, heading cues {'required_documents': ('書類', '入札方法', '入札者に要求される事項')}
- call: max 2048 tokens, timeout 300 s, one retry, temperature 0, schema bounds 40 items and 8 citations
- model: `Qwen3.5-9B-Q4_K_M.gguf`, 5680522464 bytes, SHA-256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`; context 16384
- llama-server: version: 0.5.0 (build 11146, commit 7fe450e19)
- score this freeze belongs to: `eval/reports/hybrid_dev_hybrid_v3.md` and `eval/reports/hybrid_diagnostic_dev_hybrid_v3.md`
