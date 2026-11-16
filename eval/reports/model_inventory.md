# Model inventory (this Mac, 2026-11-16)

Read-only survey. Nothing was loaded, moved or deleted, and no inference ran. GGUF facts (architecture, quant, parameter count, license tag) come from reading each file's header. Safetensors facts come from `config.json` and the weight file sizes. "Loads in llama-server as is" is only claimed as **yes** where a benchmark run in D-34 actually loaded the file; anything else is marked unverified or no, with the reason.

llama-server on this Mac: `/opt/homebrew/bin/llama-server`, version 0.5.0 (build 11146). A string check of its binaries shows the architectures `gemma4`, `qwen35`, `qwen3`, `phi3`, `lfm2`, `lfm2moe` and `nemotron_h`, so the architectures exist; that alone does not prove a given file loads.

Free disk space: 75.2 GB free in the APFS container (`df -h /` shows 70 GiB available on the 460 GiB volume; 12 GiB used by the system volume, the data volume is shared in the same container).

## 1. Shiori `models/` (gitignored)

| Name | Params | Quant | Size on disk | Family | License | llama-server loads as is | D-34 benchmarked |
|---|---|---|---|---|---|---|---|
| LFM2.5-1.2B-JP-202606 | 1.17B | Q4_K_M | 0.73 GB | LFM2 (Liquid AI), `lfm2` | LFM Open License v1.0 (`lfm1.0`; not for commercial use at companies with USD 10M+ revenue, D-35) | yes (D-34) | yes |
| LFM2.5-8B-A1B | 8.47B total, MoE with 32 experts, about 1.5B active | Q4_K_M | 5.16 GB | LFM2 MoE, `lfm2moe` | LFM Open License v1.0 | yes (D-34; `--reasoning off` is ignored, needs `--reasoning-budget 0`) | yes |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese | 8.89B | Q4_K_M | 6.53 GB | Nemotron-H (hybrid Mamba/Transformer), `nemotron_h` | NVIDIA Nemotron Open Model License | yes (D-34; very slow on CPU, 0.6 tok/s generation) | yes |
| Qwen3-Swallow-8B-RL-v0.2 | 8.19B | Q4_K_M | 5.03 GB | Qwen3 (Swallow continued pretraining), `qwen3` | Apache-2.0 | yes (D-34) | yes |
| Qwen3.5-9B | 8.95B | Q4_K_M | 5.68 GB | Qwen3.5, `qwen35` | Apache-2.0 | yes (D-34; also the local silver labeler) | yes |
| Sarashina2.2-3B-instruct-v0.1 | 3.36B | Q4_K_M | 2.07 GB | Llama architecture (SB Intuitions), `llama` | MIT | partly: loads, but the chat route returns HTTP 500 with a JSON schema; needs `/completion` with a hand-applied template (D-34). Context is only 8192 | yes |
| Qwen3.5-4B | 4B | Q4_K_M | **file not on disk**; only `Qwen3.5-4B-Q4_K_M.cpu.log` and `.gpu.log` remain (D-34 recorded 2.74 GB) | Qwen3.5 | Apache-2.0 | yes when it existed (D-34) | yes |
| gemma-4-E4B-it | about 8B stored, 4B effective | Q4_K_M | **file not on disk**; only the two logs remain (D-34 recorded 4.98 GB) | Gemma 4 | Apache-2.0 (sources.md) | yes when it existed (D-34) | yes |
| NDLOCR-Lite (4 ONNX models plus code) | not an LLM | ONNX | 302 MB for the whole checkout | NDL OCR | CC BY 4.0 (sources.md) | n/a (ONNX OCR, not run by llama-server) | n/a (D-36) |

GGUF total in `models/`: 25.2 GB. Logs and jsonl files from D-34 and the silver run sit next to them (about 0.2 MB, the silver log is 132 KB).

Two things worth knowing: the two GGUFs that D-34 benchmarked as Qwen3.5-4B and Gemma 4 E4B are gone from `models/`, so those two cannot be re-run without downloading them again (sources.md has the exact repos and revisions). Ollama has its own copies of both families (below) but those are different conversions, not the benchmarked files.

## 2. Ollama (`~/.ollama/models`, 18 GiB of blobs)

| Name | Params | Quant | Size on disk | Family | License | llama-server loads as is | D-34 benchmarked |
|---|---|---|---|---|---|---|---|
| gemma4:e4b | 8.0B stored (4B effective) | Q4_K_M | 9.61 GB | Gemma 4, `gemma4` | Apache-2.0 (license layer in the Ollama manifest) | unverified. GGUF format and the architecture is in this build, but this is Ollama's own conversion and I did not load it | no (same family was benchmarked from a different GGUF, `unsloth`) |
| qwen3.5:4b | 4.66B | Q4_K_M | 3.39 GB | Qwen3.5, `qwen35` | Apache-2.0 | unverified, same reasoning | no (same family benchmarked from a different GGUF) |
| phi4-mini:latest | 3.84B | Q4_K_M | 2.49 GB | Phi-3 architecture (Microsoft), `phi3` | MIT | unverified, same reasoning (standard architecture, most likely fine) | no |
| klaro-sections-4b-ft:latest | about 4.7B (Qwen3.5-4B with a merged LoRA, bf16 source) | int4 (Ollama's own quantization) | 3.71 GB | Qwen3.5 (`Qwen3_5ForCausalLM`) | Apache-2.0 base; the fine-tune is the user's | **no**. It is stored as safetensors tensors in Ollama's native format, not a GGUF, so llama-server cannot read it. It would need conversion to GGUF from the merged weights | no |

Ollama total from the manifests: 19.2 GB (17.9 GiB).

## 3. LM Studio

No models. `~/Library/Application Support/LM Studio` exists (5.9 MB of app data, browser-style caches) but there is no `~/.lmstudio` or `~/.cache/lm-studio` folder and no model files under the app data. If you set a custom models folder in LM Studio, tell me the path and I will add it.

## 4. Hugging Face cache (`~/.cache/huggingface/hub`)

All of these are safetensors or ONNX, none is GGUF, so none loads in llama-server as is. None was benchmarked in D-34. Sizes are real unique file bytes.

| Name | Params | Quant | Size on disk | Family | License | Notes |
|---|---|---|---|---|---|---|
| Qwen/Qwen3.5-4B | 4.66B | bf16 | 9.33 GB | Qwen3.5 | Apache-2.0 | complete (2 shards); base for the Klaro fine-tune |
| microsoft/Phi-4-mini-instruct | 3.84B | bf16 | 7.69 GB | Phi-3 architecture | MIT | complete |
| openbmb/MiniCPM-o-2_6 | about 8.7B (multimodal) | bf16 | 4.55 GB | MiniCPM-o | Apache-2.0 per its README (the model weights may carry the separate MiniCPM license, not checked) | **incomplete**: no weight file, only 4.5 GB of other files, nominal size 17.3 GB |
| Qwen/Qwen3-0.6B | about 0.6B | bf16 | 1.52 GB | Qwen3 | Apache-2.0 | complete |
| Qwen/Qwen2.5-0.5B-Instruct | 0.49B | bf16 | 1.00 GB | Qwen2.5 | Apache-2.0 | complete |
| HuggingFaceTB/SmolLM2-135M-Instruct | 0.135B | bf16 | 0.27 GB | Llama architecture | Apache-2.0 | complete |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | about 22M | fp32 | 0.09 GB | BERT (reranker) | Apache-2.0 | complete, not a generative model |
| optimum-intel-internal-testing/tiny-random-Phi3ForCausalLM | tiny random | fp32 plus ONNX variants | 0.04 GB | Phi-3 architecture | not checked | test stub |
| katuni4ka/tiny-random-phi3 | tiny random | fp32 | 0.01 GB | Phi-3 architecture | not checked | test stub |
| Qwen/Qwen3.5-2B | 2B | n/a | 0.01 GB | Qwen3.5 | Apache-2.0 | config and tokenizer only, no weights |
| Qwen/Qwen3.5-0.8B | 0.8B | n/a | 0 GB | Qwen3.5 | Apache-2.0 | empty folder |
| Helsinki-NLP/opus-mt-de-en, opus-mt-en-de | n/a | n/a | 0 GB | Marian | n/a | empty folders |

Licenses in this section are the model families' published licenses where the local repo has no README to check, except Phi-4-mini and MiniCPM-o, where the local README says so.

## 5. Klaro repo (`~/Coding/major/klaro/models`, 1.6 GB)

| Name | Params | Quant | Size on disk | Family | License | llama-server loads as is | D-34 |
|---|---|---|---|---|---|---|---|
| adapters/klaro-sections-4b | LoRA r=16 on Qwen/Qwen3.5-4B | bf16 adapter | 116 MB | Qwen3.5 | Apache-2.0 base | no (a LoRA adapter in PEFT safetensors; llama.cpp needs it converted to a GGUF LoRA, plus the base) | no |
| adapters/smoke | LoRA r=16 on Qwen3.5-0.8B (smoke test) | bf16 adapter | 39 MB | Qwen3.5 | Apache-2.0 base | no, same reason | no |
| merged/klaro-sections-4b-ft | the merged 4B (weights now live in Ollama as `klaro-sections-4b-ft`) | n/a | 19 MB (config and tokenizer only) | Qwen3.5 | Apache-2.0 base | no weights here | no |
| hf/Qwen3.5-4B, hf/Qwen3.5-0.8B | n/a | n/a | 22 MB each (config and tokenizer only) | Qwen3.5 | Apache-2.0 | no weights here | no |
| opus-mt-de-en | about 74M (Marian translation) | fp32; stored three times (`pytorch_model.bin` 298 MB, `rust_model.ot` 536 MB, `tf_model.h5` 298 MB) | 1.1 GB | Marian MT | Apache-2.0 per its local README | no (not a GGUF-supported setup) | no |
| opus-mt-en-de | about 74M (Marian) | fp32 | 287 MB | Marian MT | not checked locally | no | no |

Klaro also has `.venv` and `.venv-finetune` folders and two zips (4 MB each) in the repo root; none holds models.

## Totals

| Place | Size |
|---|---|
| Shiori `models/` GGUFs | 25.2 GB (plus 302 MB OCR) |
| Ollama | 19.2 GB |
| Hugging Face cache | about 24.5 GB |
| Klaro `models/` | 1.6 GB |
| Free disk space | 75.2 GB |

## What I did not check

- No file was loaded, so every "unverified" above stays unverified until someone runs llama-server on it.
- Licenses for the tiny test stubs, `opus-mt-en-de` and the MiniCPM-o weights were not looked up.
- Parameter counts for GGUFs come from summing the tensor table (so they include embeddings); safetensors counts are file size divided by bytes per weight, or the model card figure for the small ones.
- Other tools that keep models (Jan, GPT4All, whisper under `~/.cache/whisper`, `~/Library/Application Support/whisper`) were out of scope. A full-disk search for stray `.gguf` files was started and stopped because it was too slow, so a model sitting in an unexpected folder would not be listed here.
