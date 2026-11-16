# Model feasibility (D-34)

Q4_K_M GGUFs on a MacBook Air M4, 24 GB. One fixed deadline prompt per document, JSON-schema constrained output, thinking off, temperature 0, context 16384. Not an accuracy test. `ids exist` only checks that cited sentence IDs are in the document.

## Speed

| model | mode | file GB | load s | doc | prompt tok | prompt tok/s | gen tok/s | wall s | JSON valid | ids exist | route |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LFM2.5-1.2B-JP-202606-Q4_K_M | gpu | 0.73 | 1.0 | notice | 2573 | 1239.2 | 104.6 | 2.9 | True | False | chat |
| LFM2.5-1.2B-JP-202606-Q4_K_M | gpu | 0.73 | 1.0 | spec | 1420 | 1237.9 | 101.1 | 1.9 | True | True | chat |
| LFM2.5-1.2B-JP-202606-Q4_K_M | gpu | 0.73 | 1.0 | wto_notice | 1752 | 1196.9 | 104.9 | 2.2 | True | True | chat |
| LFM2.5-1.2B-JP-202606-Q4_K_M | gpu | 0.73 | 1.0 | long_spec | 8503 | 971.2 | 83.3 | 9.0 | True | True | chat |
| LFM2.5-1.2B-JP-202606-Q4_K_M | cpu | 0.73 | 1.8 | notice | 2573 | 99.8 | 49.6 | 27.5 | True | False | chat |
| LFM2.5-1.2B-JP-202606-Q4_K_M | cpu | 0.73 | 1.8 | spec | 1420 | 90.4 | 42.0 | 17.5 | True | True | chat |
| LFM2.5-1.2B-JP-202606-Q4_K_M | cpu | 0.73 | 1.8 | wto_notice | 1752 | 75.7 | 34.6 | 25.3 | True | True | chat |
| LFM2.5-1.2B-JP-202606-Q4_K_M | cpu | 0.73 | 1.8 | long_spec | 8503 | 45.6 | 22.2 | 187.5 | True | True | chat |
| Qwen3.5-4B-Q4_K_M | gpu | 2.74 | 3.1 | notice | 2300 | 297.5 | 27.0 | 8.7 | True | True | chat |
| Qwen3.5-4B-Q4_K_M | gpu | 2.74 | 3.1 | spec | 1338 | 275.5 | 26.6 | 5.9 | True | True | chat |
| Qwen3.5-4B-Q4_K_M | gpu | 2.74 | 3.1 | wto_notice | 1542 | 279.9 | 26.7 | 7.6 | True | False | chat |
| Qwen3.5-4B-Q4_K_M | gpu | 2.74 | 3.1 | long_spec | 7680 | 239.8 | 17.8 | 33.5 | True | True | chat |
| Qwen3.5-4B-Q4_K_M | cpu | 2.74 | 4.6 | notice | 2300 | 14.7 | 7.8 | 159.3 | True | True | chat |
| Qwen3.5-4B-Q4_K_M | cpu | 2.74 | 4.6 | spec | 1338 | 16.7 | 7.8 | 83.4 | True | True | chat |
| Qwen3.5-4B-Q4_K_M | cpu | 2.74 | 4.6 | wto_notice | 1542 | 18.1 | 7.9 | 92.1 | True | False | chat |
| Qwen3.5-4B-Q4_K_M | cpu | 2.74 | 4.6 | long_spec | 7680 | 13.7 | 5.1 | 567.7 | True | True | chat |
| gemma-4-E4B-it-Q4_K_M | gpu | 4.98 | 6.1 | notice | 2486 | 272.9 | 27.0 | 12.5 | True | True | chat |
| gemma-4-E4B-it-Q4_K_M | gpu | 4.98 | 6.1 | spec | 1457 | 254.8 | 25.9 | 7.0 | True | True | chat |
| gemma-4-E4B-it-Q4_K_M | gpu | 4.98 | 6.1 | wto_notice | 1617 | 230.2 | 25.9 | 9.4 | True | True | chat |
| gemma-4-E4B-it-Q4_K_M | gpu | 4.98 | 6.1 | long_spec | 8324 | 208.3 | 23.6 | 41.3 | True | True | chat |
| gemma-4-E4B-it-Q4_K_M | cpu | 4.98 | 7.9 | notice | 2486 | 13.0 | 7.8 | 203.3 | True | True | chat |
| gemma-4-E4B-it-Q4_K_M | cpu | 4.98 | 7.9 | spec | 1457 | 15.1 | 7.7 | 100.7 | True | True | chat |
| gemma-4-E4B-it-Q4_K_M | cpu | 4.98 | 7.9 | wto_notice | 1617 | 15.2 | 7.4 | 114.3 | True | True | chat |
| Qwen3.5-9B-Q4_K_M | gpu | 5.68 | 9.8 | notice | 2300 | 160.7 | 15.8 | 18.8 | True | True | chat |
| Qwen3.5-9B-Q4_K_M | gpu | 5.68 | 9.8 | spec | 1338 | 132.1 | 16.2 | 11.8 | True | True | chat |
| Qwen3.5-9B-Q4_K_M | gpu | 5.68 | 9.8 | wto_notice | 1542 | 128.4 | 14.9 | 15.6 | True | False | chat |
| Qwen3.5-9B-Q4_K_M | gpu | 5.68 | 9.8 | long_spec | 7680 | 69.0 | 5.5 | 115.9 | True | True | chat |
| Qwen3.5-9B-Q4_K_M | cpu | 5.68 | 17.1 | notice | 2300 | 8.5 | 2.7 | 296.3 | True | True | chat |
| Qwen3.5-9B-Q4_K_M | cpu | 5.68 | 17.1 | spec | 1338 | 8.7 | 4.2 | 159.2 | True | True | chat |
| Qwen3.5-9B-Q4_K_M | cpu | 5.68 | 17.1 | wto_notice | 1542 | 9.4 | 4.8 | 175.9 | True | False | chat |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M | gpu | 5.03 | 5.0 | notice | 2734 | 161.0 | 16.3 | 24.4 | True | True | chat |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M | gpu | 5.03 | 5.0 | spec | 1493 | 141.1 | 17.8 | 13.0 | True | True | chat |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M | gpu | 5.03 | 5.0 | wto_notice | 1840 | 142.0 | 17.0 | 15.7 | True | True | chat |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M | gpu | 5.03 | 5.0 | long_spec | 9184 | 56.6 | 6.3 | 172.1 | True | True | chat |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M | cpu | 5.03 | 12.0 | notice | 2734 | 7.4 | 3.5 | 403.0 | True | True | chat |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M | cpu | 5.03 | 12.0 | spec | 1493 | 8.5 | 3.7 | 187.2 | True | True | chat |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M | cpu | 5.03 | 12.0 | wto_notice | 1840 | 7.1 | 2.2 | 278.1 | True | True | chat |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M | gpu | 6.53 | 10.7 | notice | 2868 | 111.1 | 11.0 | 33.1 | True | True | chat |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M | gpu | 6.53 | 10.7 | spec | 1495 | 103.0 | 11.4 | 17.1 | True | True | chat |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M | gpu | 6.53 | 10.7 | wto_notice | 1983 | 83.4 | 6.0 | 31.3 | True | True | chat |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M | gpu | 6.53 | 10.7 | long_spec | 9843 | 39.3 | 4.2 | 258.2 | True | True | chat |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M | cpu | 6.53 | 14.0 | notice | 2868 | 12.7 | 0.7 | 337.4 | True | True | chat |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M | cpu | 6.53 | 14.0 | spec | 1495 | 10.9 | 0.9 | 162.6 | True | True | chat |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M | cpu | 6.53 | 14.0 | wto_notice | 1983 | 12.5 | 0.3 | 320.6 | True | True | chat |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M | gpu | 2.07 | 1.9 | notice | 2303 | 147.6 | 7.4 | 112.6 | True | True | completion |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M | gpu | 2.07 | 1.9 | spec | 1445 | 230.3 | 11.5 | 30.9 | True | True | completion |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M | gpu | 2.07 | 1.9 | wto_notice | 1477 | 228.4 | 9.6 | 25.5 | True | True | completion |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M | gpu | | | long_spec | | | | | HTTP 400 | | |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M | cpu | 2.07 | 5.9 | notice | 2303 | 19.9 | 8.4 | 267.6 | True | True | completion |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M | cpu | 2.07 | 5.9 | spec | 1445 | 20.5 | 11.1 | 165.4 | True | True | completion |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M | cpu | 2.07 | 5.9 | wto_notice | 1477 | 18.4 | 9.3 | 180.1 | True | True | completion |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M | cpu | | | long_spec | | | | | HTTP 400 | | |
| LFM2.5-8B-A1B-Q4_K_M | gpu | 5.16 | 2.7 | notice | 2289 | 688.6 | 60.3 | 4.2 | True | True | chat |
| LFM2.5-8B-A1B-Q4_K_M | gpu | 5.16 | 2.7 | spec | 1270 | 605.9 | 49.3 | 2.6 | True | True | chat |
| LFM2.5-8B-A1B-Q4_K_M | gpu | 5.16 | 2.7 | wto_notice | 1581 | 552.0 | 65.7 | 3.3 | True | True | chat |
| LFM2.5-8B-A1B-Q4_K_M | gpu | 5.16 | 2.7 | long_spec | 7424 | 530.9 | 52.6 | 14.5 | True | True | chat |
| LFM2.5-8B-A1B-Q4_K_M | cpu | 5.16 | 10.7 | notice | 2289 | 33.2 | 15.2 | 72.3 | True | True | chat |
| LFM2.5-8B-A1B-Q4_K_M | cpu | 5.16 | 10.7 | spec | 1270 | 29.0 | 11.3 | 47.8 | True | False | chat |
| LFM2.5-8B-A1B-Q4_K_M | cpu | 5.16 | 10.7 | wto_notice | 1581 | 29.6 | 5.9 | 60.5 | True | True | chat |

## Memory

GPU column: growth of the GPU's in-use system memory (ioreg IOAccelerator) while the server runs, which includes Metal buffers. CPU column: peak resident set size with `-ngl 0`, where all weights live in the process. Both include the KV cache for a 16384-token context, allocated up front.

| model | file GB | GPU mode MB | GPU-mode RSS MB (under-reports) | CPU mode peak RSS MB |
|---|---|---|---|---|
| LFM2.5-1.2B-JP-202606-Q4_K_M | 0.73 | 1125 | 998 | 1713 |
| LFM2.5-8B-A1B-Q4_K_M | 5.16 | 5244 | 5063 | 7102 |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M | 6.53 | 7736 | 6316 | 7297 |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M | 5.03 | 7830 | 6875 | 8837 |
| Qwen3.5-4B-Q4_K_M | 2.74 | 3624 | 3344 | 5785 |
| Qwen3.5-9B-Q4_K_M | 5.68 | 6553 | 5909 | 6877 |
| gemma-4-E4B-it-Q4_K_M | 4.98 | 5580 | 4416 | 5180 |
| sarashina2.2-3b-instruct-v0.1-Q4_K_M | 2.07 | 5478 | 4452 | 5805 |
