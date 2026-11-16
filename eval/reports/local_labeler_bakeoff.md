# Local labeler bake-off

Prompt sv4 (frozen), local llama-server, no cloud call. Scored against the label files of the pilot documents with the consensus agreement rule (`compare.score`), on the answers after the local shape repair. Run ended: --max-calls 25 reached.

Every rate has its counts next to it, because n is small. `labeler_overlap`: that model's answers fed the review candidates, so its score is optimistic.

| model | note | documents run (complete) | tier 1 fields | all fields | list fields | valid JSON before repair (parts) | repair request (parts) | citation exists | value in citation | tok/s | s per document |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LFM2.5-1.2B-JP-202606-Q4_K_M.gguf |  | 5 (2) | 3/40 (8%) | 4/96 (4%) | 0/12 (0%) | 2/5 (40%) | 2/5 (40%) | 23/29 (79%) | 2/29 (7%) | 76.1 | 108 |
| LFM2.5-8B-A1B-Q4_K_M.gguf |  | 5 (4) | 5/40 (12%) | 15/96 (16%) | 0/12 (0%) | 4/5 (80%) | 4/5 (80%) | 42/57 (74%) | 5/32 (16%) | 47.0 | 129 |
| Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf |  | 5 (4) | 19/40 (48%) | 49/96 (51%) | 1/12 (8%) | 4/5 (80%) | 3/5 (60%) | 52/52 (100%) | 39/51 (76%) | 9.4 | 635 |
| Qwen3.5-9B-Q4_K_M.gguf | labeler_overlap | 5 (5) | 30/40 (75%) | 67/96 (70%) | 1/12 (8%) | 5/5 (100%) | 2/5 (40%) | 74/74 (100%) | 64/66 (97%) | 6.5 | 678 |
| NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf |  | 0 (0) | - | - | - | - | - | - | - | - | - |
| gemini sv4 (reference, not ground truth) | labeler_overlap: it also fed the review candidates | 5 (5) | 32/40 (80%) | 85/96 (89%) | 6/12 (50%) | - | - | 70/70 (100%) | 65/65 (100%) | - | - |

## Per document

- f19cddbd4cba (notice, 法務省): 23 label lines, 15 reviewed by a person, 8 accepted by agreement of two labelers.
  - LFM2.5-1.2B-JP-202606-Q4_K_M.gguf: failed, 0/23 fields, 91 s
    wrong or missing: title, issuer_org, contracting_officer, notice_date, procurement_type, award_method, item_category, scope_summary, performance_period, delivery_deadline, delivery_location, eligibility, unified_qualification, deadlines, submission_modes, bid_bond, performance_bond, tax_basis, language_currency, required_documents, contact, wto_covered, spec_access
  - LFM2.5-8B-A1B-Q4_K_M.gguf: complete, 0/23 fields, 129 s
    wrong or missing: title, issuer_org, contracting_officer, notice_date, procurement_type, award_method, item_category, scope_summary, performance_period, delivery_deadline, delivery_location, eligibility, unified_qualification, deadlines, submission_modes, bid_bond, performance_bond, tax_basis, language_currency, required_documents, contact, wto_covered, spec_access
  - Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf: complete, 16/23 fields, 728 s
    wrong or missing: issuer_org, scope_summary, delivery_deadline, eligibility, deadlines, required_documents, spec_access
  - Qwen3.5-9B-Q4_K_M.gguf: complete, 17/23 fields, 419 s
    wrong or missing: scope_summary, delivery_location, eligibility, deadlines, required_documents, spec_access
  - NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf: not run
- 563042df9941 (notice, 内閣府): 23 label lines, 12 reviewed by a person, 11 accepted by agreement of two labelers.
  - LFM2.5-1.2B-JP-202606-Q4_K_M.gguf: complete, 4/23 fields, 158 s
    wrong or missing: title, issuer_org, contracting_officer, notice_date, item_category, scope_summary, performance_period, delivery_deadline, delivery_location, eligibility, unified_qualification, deadlines, submission_modes, bid_bond, performance_bond, required_documents, contact, wto_covered, spec_access
  - LFM2.5-8B-A1B-Q4_K_M.gguf: complete, 4/23 fields, 69 s
    wrong or missing: title, issuer_org, contracting_officer, procurement_type, award_method, scope_summary, performance_period, delivery_location, eligibility, unified_qualification, deadlines, submission_modes, bid_bond, performance_bond, tax_basis, language_currency, required_documents, wto_covered, spec_access
  - Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf: complete, 13/23 fields, 628 s
    wrong or missing: contracting_officer, scope_summary, delivery_location, eligibility, deadlines, bid_bond, performance_bond, required_documents, wto_covered, spec_access
  - Qwen3.5-9B-Q4_K_M.gguf: complete, 14/23 fields, 490 s
    wrong or missing: title, contracting_officer, notice_date, item_category, performance_period, eligibility, deadlines, required_documents, spec_access
  - NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf: not run
- 4b0b9d8229c7 (notice, 和歌山県): 23 label lines, 12 reviewed by a person, 11 accepted by agreement of two labelers.
  - LFM2.5-1.2B-JP-202606-Q4_K_M.gguf: failed, 0/23 fields, 134 s
    wrong or missing: title, issuer_org, contracting_officer, notice_date, procurement_type, award_method, item_category, scope_summary, performance_period, delivery_deadline, delivery_location, eligibility, unified_qualification, deadlines, submission_modes, bid_bond, performance_bond, tax_basis, language_currency, required_documents, contact, wto_covered, spec_access
  - LFM2.5-8B-A1B-Q4_K_M.gguf: complete, 3/23 fields, 133 s
    wrong or missing: contracting_officer, notice_date, procurement_type, award_method, item_category, scope_summary, performance_period, delivery_deadline, delivery_location, eligibility, deadlines, submission_modes, bid_bond, performance_bond, tax_basis, language_currency, required_documents, contact, wto_covered, spec_access
  - Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf: complete, 17/23 fields, 464 s
    wrong or missing: title, procurement_type, performance_period, deadlines, required_documents, spec_access
  - Qwen3.5-9B-Q4_K_M.gguf: complete, 18/23 fields, 729 s
    wrong or missing: title, award_method, performance_period, deadlines, required_documents
  - NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf: not run
- 28ad40ea4b1f (bid_instructions, 和歌山県): 23 label lines, 14 reviewed by a person, 9 accepted by agreement of two labelers.
  - LFM2.5-1.2B-JP-202606-Q4_K_M.gguf: failed, 0/21 fields, 130 s
    wrong or missing: title, issuer_org, contracting_officer, procurement_type, award_method, scope_summary, performance_period, delivery_deadline, delivery_location, eligibility, unified_qualification, deadlines, submission_modes, bid_bond, performance_bond, tax_basis, language_currency, required_documents, contact, wto_covered, spec_access
  - LFM2.5-8B-A1B-Q4_K_M.gguf: complete, 8/21 fields, 121 s
    wrong or missing: title, issuer_org, contracting_officer, award_method, scope_summary, performance_period, eligibility, deadlines, performance_bond, tax_basis, required_documents, contact, spec_access
  - Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf: failed, 0/21 fields, 1166 s
    wrong or missing: title, issuer_org, contracting_officer, procurement_type, award_method, scope_summary, performance_period, delivery_deadline, delivery_location, eligibility, unified_qualification, deadlines, submission_modes, bid_bond, performance_bond, tax_basis, language_currency, required_documents, contact, wto_covered, spec_access
  - Qwen3.5-9B-Q4_K_M.gguf: complete, 14/21 fields, 1530 s
    wrong or missing: title, issuer_org, performance_period, eligibility, deadlines, required_documents, contact
  - NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf: not run
- 4c40bbd831fe (spec, 和歌山県): 23 label lines, 2 reviewed by a person, 21 accepted by agreement of two labelers.
  - LFM2.5-1.2B-JP-202606-Q4_K_M.gguf: complete, 0/6 fields, 26 s
    wrong or missing: title, issuer_org, scope_summary, performance_period, delivery_deadline, delivery_location
  - LFM2.5-8B-A1B-Q4_K_M.gguf: failed, 0/6 fields, 192 s
    wrong or missing: title, issuer_org, scope_summary, performance_period, delivery_deadline, delivery_location
  - Qwen3-Swallow-8B-RL-v0.2-Q4_K_M.gguf: complete, 3/6 fields, 188 s
    wrong or missing: issuer_org, performance_period, delivery_location
  - Qwen3.5-9B-Q4_K_M.gguf: complete, 4/6 fields, 223 s
    wrong or missing: issuer_org, delivery_location
  - NVIDIA-Nemotron-Nano-9B-v2-Japanese.Q4_K_M.gguf: not run

## What this does not tell you

- Five documents. One more or fewer correct field moves a rate by a few points, and tier 1 has about 10 fields per document, so the tier 1 counts are small.
- Three of the five documents are from one Wakayama template family, so a model that learned that template looks better than it would on other issuers.
- The labels are not independent of the labelers: Gemini and Qwen3.5-9B supplied the candidates the reviewer chose from, and some lines were accepted without a person reading them (the per-document counts above). Qwen3.5-9B's score is the most optimistic.
- Speed is from a MacBook Air M4 with Metal. It is not the 16 GB Windows laptop without a GPU that the app targets; on CPU the ranking by speed can change (D-34: Nemotron generates 0.6 tok/s there).
- Seconds per document are the cached run times, and exclude the model load. Time and tok/s only exist for answers made with a build that recorded llama-server's timings.
- It scores field values and citations against the labels. It does not say whether an answer is useful to a bidder, and nobody here checked the Japanese meaning.
