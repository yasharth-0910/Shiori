# Splits (frozen, D-40)

`splits.json` maps each issuing organization to `train`, `dev` or `test`. Built by `uv run python -m eval.splits`: the candidate split from `corpus_report.md` plus two overrides, no randomness. Do not change an assignment without a new decision entry; `tests/test_splits.py` holds a copy and fails on any difference.

## Overrides of the candidate split

- 和歌山県 to dev: open; 8 spec and 8 bid_instructions, dev had 10 and 8
- 北海道 to test: open; 7 spec and 2 bid_instructions, test had 9 and 10

## Constraint checks

| constraint | passed | evidence |
|---|---|---|
| every org assigned once | yes | 37 of 37 orgs |
| about 60/20/20 of orgs (each within 1 of round(share x orgs)) | yes | train 21, dev 8, test 8 |
| dev: 2+ open orgs with 5+ docs | yes | 6: 内閣府, 厚生労働省, 和歌山県, 法務省, 総務省, 農林水産省 |
| test: 2+ open orgs with 5+ docs | yes | 5: 北海道, 岡山県, 最高裁判所, 経済産業省, 防衛省 |
| test: 4+ orgs with 5+ docs | yes | 6: 北海道, 岡山県, 最高裁判所, 経済産業省, 船橋市, 防衛省 |
| p-portal ministries in all three splits | yes | train 12; dev 5; test 4 |

## Result

| split | orgs | docs | open docs | restricted or unknown docs |
|---|---|---|---|---|
| train | 21 | 221 | 88 | 133 |
| dev | 8 | 137 | 81 | 56 |
| test | 8 | 145 | 116 | 29 |

## Orgs

- **train**: こども家庭庁, サイバー通信情報監理委員会, デジタル庁, 人事院, 個人情報保護委員会, 八王子市, 公正取引委員会, 国土交通省, 奈良市, 富山市, 川口市, 復興庁, 松江市, 横須賀市, 消費者庁, 環境省, 衆議院, 財務省, 郡山市, 金沢市, 鹿児島市
- **dev**: 内閣府, 厚生労働省, 和歌山県, 新潟県, 旭川市, 法務省, 総務省, 農林水産省
- **test**: 北海道, 岡山県, 文部科学省, 最高裁判所, 気象衛星センター, 経済産業省, 船橋市, 防衛省

Not merged: 気象衛星センター belongs to 気象庁 (D-25); no 気象庁 notice was collected, so nothing needed merging and 気象衛星センター stays in test as the candidate had it.
