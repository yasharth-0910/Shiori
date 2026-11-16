# Model load check

`uv run python -m eval.model_loadcheck`, context 4096, one server at a time, `--reasoning off`. Fixed test prompt: one invented Japanese sentence asking for the day of a deadline (expected answer contains 13).

llama-server version:

```
0.00.000.818 I srv  llama_server: initializing ...
version: 0.5.0 (build 11146, commit 7fe450e19)
built with AppleClang 21.0.0.21000334 for Darwin arm64
```

| model | size GB | loaded | load s | tok/s | notes |
|---|---|---|---|---|---|
| LFM2.5-1.2B-JP-202606-Q4_K_M.gguf | 0.7 | yes | 1.0 | 86.2 | reply ok, has 13 |
| LFM2.5-8B-A1B-Q4_K_M.gguf | 5.2 | yes | 4.0 | 68.3 | reply ok, has 13 |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf | 6.5 | yes | 5.0 | 11.7 | reply ok, has 13 |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf | 5.0 | yes | 4.0 | 18.5 | reply ok, has 13 |
| Qwen3.5-9B-Q4_K_M.gguf | 5.7 | yes | 4.5 | 15.8 | reply ok, has 13 |
| gemma4-e4b-ollama.gguf | 9.6 | no | - | - | exited: 0.00.348.830 E llama_model_load_from_file_impl: failed to load model / 0.00.349.091 E common_fit_params: encountered an error while trying to fit params to free device memory: failed to load model / 0.00.568.243 W load: control-looking token:    212 '</s>' was not control-type; this is probably a bug in the model. its type will be overridden / 0.00.573.694 W load: special_eog_ids contains '</tool_response>', removing '</s>' token from EOG list / 0.00.596.902 E llama_model_load: error loading model: done_getting_tensors: wrong number of tensors; expected 2131, got 720 / 0.00.596.904 E llama_model_load_from_file_impl: failed to load model / 0.00.596.906 E cmn  common_init_: failed to load model '~/Coding/Etc/Shiori/models/gemma4-e4b-ollama.gguf' / 0.00.596.907 E srv    load_model: failed to load model, '~/Coding/Etc/Shiori/models/gemma4-e4b-ollama.gguf' / 0.00.596.908 I srv    operator(): operator(): cleaning up before exit... / 0.00.597.078 E srv  llama_server: exiting due to model loading error |
| qwen3.5-4b-ollama.gguf | 3.4 | no | - | - | exited: 0.00.078.683 I srv    load_model: loading model '~/Coding/Etc/Shiori/models/qwen3.5-4b-ollama.gguf' / 0.00.215.967 E llama_model_load: error loading model: error loading model hyperparameters: key qwen35.rope.dimension_sections has wrong array length; expected 4, got 3 / 0.00.215.970 E llama_model_load_from_file_impl: failed to load model / 0.00.215.991 E common_fit_params: encountered an error while trying to fit params to free device memory: failed to load model / 0.00.350.034 E llama_model_load: error loading model: error loading model hyperparameters: key qwen35.rope.dimension_sections has wrong array length; expected 4, got 3 / 0.00.350.037 E llama_model_load_from_file_impl: failed to load model / 0.00.350.038 E cmn  common_init_: failed to load model '~/Coding/Etc/Shiori/models/qwen3.5-4b-ollama.gguf' / 0.00.350.039 E srv    load_model: failed to load model, '~/Coding/Etc/Shiori/models/qwen3.5-4b-ollama.gguf' / 0.00.350.041 I srv    operator(): operator(): cleaning up before exit... / 0.00.350.170 E srv  llama_server: exiting due to model loading error |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M.gguf | 2.1 | yes | 2.0 | 35.3 | reply ok, has 13 |
