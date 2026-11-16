# Rules extractor v4: six more fields, before and after

Split dev, 14 labeled documents: the 9 the rules were written from plus the 5 hold-out documents (58f13b9c, a81e99fe, d230e51e, 6b7142ab, 594c3cb6), which now count as dev. Before = the same extractor without the six fields (rules v3). After = `core/shiori_core/extract/rules.py` now. Deterministic, no model, no cloud call. Scores are against model-reviewed silver labels (D-41).

**There is no unseen set for these six fields.** The rules were written while reading these 14 documents' labels and sentences, so every number below is a fit, not a forecast. The rule wording was also checked for stray hits on the unlabeled dev and train documents, but those have no labels, so that check measured nothing.

## Verified accuracy per new field

| field | before, 14 docs | after, 14 docs | after, dev-9 | after, hold-out 5 | shown | wrong value shown | hallucination |
| --- | --- | --- | --- | --- | --- | --- | --- |
| award_method | 1 of 13 (8%) | 11 of 13 (85%) | 6 of 8 (75%) | 5 of 5 (100%) | 10 | 0 of 13 | 0 of 10 |
| spec_access | 0 of 13 (0%) | 6 of 13 (46%) | 2 of 8 (25%) | 4 of 5 (80%) | 6 | 0 of 13 | 0 of 6 |
| submission_modes | 1 of 13 (8%) | 12 of 13 (92%) | 7 of 8 (88%) | 5 of 5 (100%) | 11 | 0 of 13 | 0 of 11 |
| delivery_deadline | 13 of 14 (93%) | 13 of 14 (93%) | 8 of 9 (89%) | 5 of 5 (100%) | 0 | 0 of 14 | 0 of 0 |
| performance_period | 0 of 14 (0%) | 13 of 14 (93%) | 8 of 9 (89%) | 5 of 5 (100%) | 13 | 0 of 14 | 0 of 13 |
| contracting_officer | 3 of 13 (23%) | 12 of 13 (92%) | 7 of 8 (88%) | 5 of 5 (100%) | 9 | 0 of 13 | 0 of 9 |

## Whole extractor

| group | before | after |
| --- | --- | --- |
| all fields, verified | 129 of 301 (43%) | 178 of 301 (59%) |
| tier 1, verified | 66 of 130 (51%) | 93 of 130 (72%) |
| wrong value shown, all fields | 1 of 301 | 1 of 301 |
| hallucination (value not in cited sentences), all fields | 0 of 301 | 0 of 301 |

The other 17 fields score the same before and after: yes. The one wrong value shown on both sides is unified_qualification on 58f13b9c (unchanged from the hold-out run).

## Left out, and why

- spec_access: `email_after_pledge` (no example in the 14 documents). A 交付方法 line that says anything but the electronic system or a counter answers nothing, and then the 仕様 pointer is not used either: 136dfba9, 84e9d0c8, a81e99fe and f19cddbd are labeled differently from each other on near-identical wording (see_other_document versus public), so no one rule fits them. A pointer under a 業務内容 heading (28ad40ea), a link line on a tender page (4b0b9d82) and a posting on a website (d4000027) are not read.
- submission_modes: a mail or e-mail choice (郵送又はメール, 28ad40ea, labeled with electronic) answers nothing; `持参の場合` alone is not read; a paper bid is read only next to an electronic way (a clause that only says 紙入札方式に代える is not enough). A way the notice never names is left out, as the labels do it; a notice that names a way in other words than the ones coded gets an incomplete set. That is the main risk here and 14 documents cannot size it.
- delivery_deadline: 履行期限 is not read. f19cddbd (goods) is labeled see_other_document for it, but on services notices the label is absent and the wording does not tell the two apart. Only 納入期限 lines are read; none of the 14 documents has one, so this rule scores 13 of 14 only by staying silent (the 14th is f19cddbd). Its date and pointer forms are tested on unlabeled documents' wording (c2f9213c, 070b894e, 08558fc7).
- performance_period: a start-and-end range (令和X年Xから令和X年Xまで) is not read (no example among the 14). A date the segmenter split across two sentences is not read (136dfba9: the label itself puts the whole phrase in relative_text and leaves end empty, which the rule would not match anyway).
- contracting_officer: a13baaac stays not found: its label cites page text (`お知らせ`) glued to the post and has no name. Officers on one line (`支出負担行為担当官　…`) are not read; none of the 14 documents has that layout.
- award_method: proposal scoring that is not named 総合評価 (d4000027, 28ad40ea, labeled best_value) is not read, and neither is a committee choice with no scoring (guide: absent).
- title, issuer_org, scope_summary, item_category, contact, delivery_location: not touched, as asked.

## Two changes outside rules.py

- `Extracted` has a `status` (present or see_other_document). `eval/run.py` `rules_extractor` and `eval/hybrid.py` `extract` pass it on instead of a fixed `present`, one word each. Scoring code is unchanged. Without this a pointer answer (仕様書のとおり) would be scored as a plain value and never match its label.
- Because rules.py changed, the file hashes in `hybrid_freeze_dev_hybrid_v3.md` no longer match for rules.py, run.py and hybrid.py. That record stays as it was; any hybrid run from here needs its own freeze. See `freeze_rules_v4.md`.
