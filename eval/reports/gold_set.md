# Gold set selection

`uv run python -m eval.gold_select`, seed 20261016, split dev, license_class open only. Ids are 8-character prefixes; no document text.

Open dev documents by doc_type: bid_instructions 8, draft_contract 1, evaluation_criteria 1, forms 3, notice 48, other 8, qa 5, spec 8

Skipped (notice, tender_page, bid_instructions, spec only): none

Pilot documents that qualify: 28ad40ea4b1f, 4b0b9d8229c7, 4c40bbd831fe, 563042df9941, f19cddbd4cba; left out: none

Shortfalls: {'bid_instructions': 'wanted 4, got 3', 'spec': 'wanted 4, got 2'}

Bundles with notice, instructions and spec all selected: 1; bundles with two or more selected: 2

## Counts per stratum

| stratum | selected | wanted |
|---|---|---|
| notice (all) | 15 | about 12 |
| bid_instructions | 3 | about 4 |
| spec | 2 | about 4 |
| notice_summary | 6 | at least 6 |
| notice_other | 9 | |

## Counts per organization

| organization | documents |
|---|---|
| 内閣府 | 3 |
| 厚生労働省 | 2 |
| 和歌山県 | 6 |
| 法務省 | 3 |
| 総務省 | 3 |
| 農林水産省 | 3 |

## Waves

| wave | id | doc_type | organization | pages | stratum |
|---|---|---|---|---|---|
| 0 (already labeled) | 28ad40ea | bid_instructions | 和歌山県 | 7 | bid_instructions |
| 0 (already labeled) | 4b0b9d82 | notice | 和歌山県 | - | notice_other |
| 0 (already labeled) | 4c40bbd8 | spec | 和歌山県 | 6 | spec |
| 0 (already labeled) | 563042df | notice | 内閣府 | - | notice_other |
| 0 (already labeled) | f19cddbd | notice | 法務省 | - | notice_summary |
| 1 | d4000027 | bid_instructions | 和歌山県 | 13 | bid_instructions |
| 1 | 136dfba9 | notice | 農林水産省 | - | notice_summary |
| 1 | 84e9d0c8 | notice | 厚生労働省 | - | notice_summary |
| 1 | 389a7520 | notice | 農林水産省 | - | notice_other |
| 1 | a13baaac | notice | 農林水産省 | - | notice_other |
| 2 | e71b351a | bid_instructions | 和歌山県 | 7 | bid_instructions |
| 2 | 58f13b9c | notice | 総務省 | - | notice_summary |
| 2 | a9049787 | notice | 内閣府 | - | notice_summary |
| 2 | 714055a2 | notice | 内閣府 | - | notice_other |
| 2 | d0174ce0 | notice | 厚生労働省 | - | notice_other |
| 3 | 7e591bba | spec | 和歌山県 | 2 | spec |
| 3 | 6b7142ab | notice | 法務省 | - | notice_summary |
| 3 | 2fa0d5a4 | notice | 総務省 | - | notice_other |
| 3 | 9c955892 | notice | 法務省 | - | notice_other |
| 3 | f08ea5ae | notice | 総務省 | - | notice_other |

## Reserve

| id | doc_type | organization | pages | stratum |
|---|---|---|---|---|
| 53320d90 | bid_instructions | 和歌山県 | 9 | bid_instructions |
| fd637c1d | spec | 和歌山県 | 4 | spec |
| a81e99fe | notice | 厚生労働省 | - | notice_summary |
| bf99e8ba | notice | 総務省 | - | notice_other |
| 01e953d8 | bid_instructions | 和歌山県 | 8 | bid_instructions |
