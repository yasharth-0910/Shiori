# Labeling guide (silver labels, prompt sv4)

Conventions for how a field is written when the facts are clear but the shape is not. They come from the review of the 37 pilot items (`eval/reports/silver_pilot.md`, answers in `data/cache/labeling/answers/pilot-all.txt`) and of the sv3 pilot (`pilot2.txt` to `pilot4.txt`). Each rule has one pilot example: item id, document, sentence. The field definitions themselves are in `field_schema.md`; this file only settles how to write them down.

The block between the two `prompt` markers below is sent, word for word, to both labelers in every call (`eval/silver/prompt.py` reads it). **Editing that block changes the prompt: bump `PROMPT_VERSION` in `eval/silver/config.py`**, or cached answers made with the old text will be mixed with new ones. sv3 changed the org rule for contact and issuer_org (D-51). sv4 added the rules from the sv3 pilot review, the client-organization rule for issuer_org and the contact vs delivery place rule, and is the one prompt version of every labeler (D-54).

<!-- prompt:start -->
- contracting_officer: title is the full official title line(s), including 支出負担行為担当官 or 契約担当官 and the post, joined with one space (支出負担行為担当官 出入国在留管理庁次長). name is the person only (内藤惣一郎).
- contact: org is the body that issues the notice in its own name. At national level that is a ministry or its external agency, a 〇〇庁 (出入国在留管理庁). At local level it is the prefecture or the city (和歌山県); its internal bodies such as 教育庁, 企業局, 病院局, 警察本部 and 会計局 are departments, so 和歌山県教育庁 is org 和歌山県, department 教育庁. Everything below the org is department (総務課予算第二係; 会計局会計課 for 和歌山県会計局会計課). phone and email are copied from the source; write the phone with ASCII hyphens (03-3592-7516).
- title: the name of the procurement inside the headline, without status tags such as ［審査結果掲載］ and without wrapper phrases such as に係る公募型プロポーザルの実施について. Never put a status tag in title. When the document has a 委託業務名 or 件名 line, take that line, not the document's own heading such as …に係る公募要領.
- issuer_org: the org of the contact rule: a ministry or a 〇〇庁 at national level (出入国在留管理庁), the prefecture or the city at local level (和歌山県, also when the text says 和歌山県教育庁). The organization name only, never a whole sentence, never a unit below it (和歌山県, not 和歌山県会計局会計課). The portal metadata field 調達機関 is not the issuer when the notice is issued by an external agency in its own name (調達機関 法務省, issuer_org 出入国在留管理庁).
- issuer_org: when a document has no issuer statement (common in specs), cite the sentences that name the client organization, such as rights belonging to 和歌山県 or something prepared by 和歌山県教育庁; the org follows the org rule (和歌山県).
- contact and delivery_location: contact uses the 問い合わせ先 or 担当 line; delivery_location uses the 納品場所 or 履行場所 line. A delivery place is never the contact.
- notice_date: the date line in the notice body, before the officer's name or before 記. Portal metadata dates such as 公開開始日 and 公開終了日 are not the notice date; if the body has no date line, notice_date is absent.
- award_method: only when the text says 総合評価, 最低価格 or an equivalent rule for picking the winner. Never infer it from the procurement type. A proposal and an estimate scored together, the highest score winning, is best_value. A committee selection with no scoring described is absent.
- procurement_type: 公募型プロポーザル is proposal_competition.
- see_other_document: always include ref {kind, text_ja}, for text fields too. Use it when the sentence says 仕様書による, 入札説明書による, 仕様書のとおり and similar, instead of a value.
- 履行期限 on a goods tender fills both performance_period and delivery_deadline, with the same citation (both see_other_document when it points to the spec).
- delivery_deadline: a services contract has none; its 契約期間 goes to performance_period.
- scope_summary: use the document's own work-content line (業務内容, 業務の概要, 目的). If that line only points elsewhere (仕様書のとおり, 入札説明書による), the status is see_other_document. A procurement title alone is not a scope summary.
- spec_access: 別紙「仕様書」のとおり is see_other_document with ref kind spec.
- eligibility: polarity follows text_ja as written. A text_ja that keeps its negation (…ないこと, "must not be …") is a requirement; a text_ja with the negation stripped, describing the bad state, is a disqualification.
- performance_period: "最長 …まで" keeps the whole phrase in relative_text and the date in end. "契約締結日から …まで" puts 契約締結日 in relative_text and the date in end.
- required_documents: include 入札書 whenever the notice mentions submitting a bid form in any way (入札書を提出, 入札書に記載, a receipt deadline for bids), plus every document named with a submission deadline or a duty to submit. Do not add 入札書 for a proposal competition that never mentions one.
- tax_basis: tax wording on a commission cap in a proposal competition counts: 消費税…を含む is bid_includes_tax, 消費税…を含まない is bid_excludes_tax.
- unified_qualification: category is quoted exactly as written, brackets included (「物品の製造」、「物品の販売」又は「役務の提供等」).
- value_ja is copied exactly. Never shorten it with an ellipsis (… or ...). If the value needs two separate parts, cite both sentences and join the two parts with a line break, never with ; or other added characters.
<!-- prompt:end -->

## Examples from the pilot

Documents: `f19cddbd4cba` (法務省 notice, p-portal), `563042df9941` (内閣府 notice, p-portal), `4b0b9d8229c7` (和歌山県 tender page). All open, dev split. Item ids are the review items of the pilot export.

**contracting_officer** (F-0021, `f19cddbd4cba` h_s26, h_s27). Source lines: `支出負担行為担当官` / `出入国在留管理庁次長　内藤惣一郎`. Accepted: title `支出負担行為担当官 出入国在留管理庁次長`, name `内藤惣一郎`. Rejected: title `支出負担行為担当官` with the post moved into name. Same split in F-0020 (`563042df9941` h_s22, h_s23).

**contact** (F-0038, `f19cddbd4cba` h_s46). Source: `…出入国在留管理庁総務課予算第二係　高北、野々山、入江　　電話03－3592－7516`. Accepted: org `出入国在留管理庁`, department `総務課予算第二係`, phone `03-3592-7516`. Rejected: org and department null, phone with full-width dashes. 出入国在留管理庁 is a 庁 under 法務省, but it issues the notice in its own name, so it is the org, not 法務省. F-0036 (`4b0b9d8229c7`) puts `和歌山県` in org and `データ利活用推進センター` in department.

**contact and issuer_org, prefecture units** (`081d27569eac`, 和歌山県 bid instructions, dev, open; not a pilot item). p1_s1 is `和歌山県会計局会計課`. org and issuer_org are `和歌山県`; department is `会計局会計課`. 会計局 is a unit of the prefecture, not a body that issues notices in its own name, so it never goes in org.

**contact and issuer_org, a prefecture's 教育庁** (`4c40bbd831fe`, 和歌山県 spec, dev, open; review item F-0039). p1_s23 says the domain name is the one `和歌山県教育庁で準備したもの`. 教育庁 is the office of the prefecture's board of education, an internal body of 和歌山県 even though its name ends in 庁, so issuer_org is `和歌山県` and a contact there would be org `和歌山県`, department `教育庁`. A national 〇〇庁 such as 出入国在留管理庁 is different: it is an external agency of a ministry and issues notices in its own name, so it is the org. In the sv2 shadow run the local model answered issuer_org `和歌山県教育庁`; under this rule that is the department, not the org. Reviewed answer (F-0039, `answers/pilot4.txt`): issuer_org `和歌山県`, citing p5_s20, p1_s23 and p5_s5.

**issuer_org in a spec with no issuer statement** (F-0039, `4c40bbd831fe`). The spec never says who issues it. Sentences that name the client organization do: p5_s5 says the copyright of new work belongs to `和歌山県`, p1_s23 that the domain name is the one `和歌山県教育庁で準備したもの` (prepared by the prefecture's 教育庁). By the org rule issuer_org is `和歌山県`. p3_s1 mentions only the prefecture's office PCs and is not a citation. The F-0039 label also cites p5_s20, `和歌山県教育庁 生涯学習局生涯学習課`; that line sits under `（２） 納品場所` (p5_s19, delivery place), so under this rule it is a delivery_location line, not an issuer or contact line. The label is kept as reviewed.

**contact vs delivery place** (`4c40bbd831fe` p5_s19 to p5_s23). The office, address and phone under `（２） 納品場所` say where the work is delivered. contact comes from a 問い合わせ先 or 担当 line only; a 納品場所 or 履行場所 block goes to delivery_location, even when it names an office with a phone number.

**title** (F-0018, `4b0b9d8229c7` h_s1). Headline: `［審査結果掲載］「令和8年度和歌山県データを利活用した公募型研究事業」に係る公募型プロポーザルの実施について`. Accepted: `令和8年度和歌山県データを利活用した公募型研究事業`. Rejected: the whole headline with the tag.

**issuer_org** (F-0019, `4b0b9d8229c7` h_s2). Accepted: `和歌山県`. Rejected: the full sentence that starts with 和歌山県は、….

**notice_date** (F-0023, `f19cddbd4cba` h_s25). `令和８年８月28日` stands alone between `次のとおり一般競争入札に付します。` and the officer's title: that is the notice date, 2026-08-28. Counterexample, F-0022 (`563042df9941`): the candidate cited h_s11 `令和08年08月19日`, the value under the portal heading `公開開始日` (h_s10). Under this rule it is not the notice date. F-0022 was answered absent (`data/cache/labeling/answers/pilot-extra2.txt`): the notice body has no date line.

**award_method** (F-0015, `4b0b9d8229c7`). A labeler answered best_value because the notice is a 公募型プロポーザル (h_s4). The notice names no award rule, only selection by a committee: absent.

**procurement_type** (F-0013, `4b0b9d8229c7` h_s1). `公募型プロポーザル` is proposal_competition. Rejected: public_solicitation from `公募型研究事業`.

**see_other_document on a text field** (F-0029, `563042df9941` h_s30, section 2(3)). Source: `入札説明書による。`. Label: status see_other_document, value_ja `入札説明書による。`, normalized `{"ref": {"kind": "bid_instructions", "text_ja": "入札説明書による。"}}`. Both labelers had this right in the pilot, but neither could send a ref for a text field, and both failed the schema check. Same for scope_summary in F-0024 (h_s28) and spec_access in F-0011 (h_s28).

**履行期限 on a goods tender** (F-0027 and F-0028, `f19cddbd4cba` h_s34). Source: `(4)　履行期限　仕様書のとおり。`. performance_period and delivery_deadline are both see_other_document, kind spec, citing h_s34.

**performance_period** (F-0025, `4b0b9d8229c7` h_s24). Source: `最長 令和9年9月末まで`. Accepted: end `2027-09-30`, relative_text `最長 令和9年9月末まで`. F-0026 (`563042df9941` h_s32): `契約締結日から令和９年２月２６日まで` gives end `2027-02-26`, relative_text `契約締結日`.

**required_documents** (F-0035, `f19cddbd4cba` h_s49, h_s55). h_s49 gives the receipt deadline for bids (`入札書の受領期限`), so 入札書 is an item, cited h_s49. h_s55 says the 納品仕様書等 must be submitted by a set date, so it is an item too. Both labelers listed only the second. In `563042df9941` the bid form is mentioned as `入札書に記載された金額` (h_s35) and `入札書のシステムへの提出期限` (h_s52): either one is enough for 入札書. Counterexample, `4b0b9d8229c7` (和歌山県 公募型プロポーザル): the notice never mentions 入札書, so it is not an item there.

**tax_basis** (F-0008, `4b0b9d8229c7` h_s26). Source: `1件当たり 2,000,000円（消費税及び地方消費税を含む。）`, a cap on the commission in a proposal competition, not a bid price. Labeled bid_includes_tax. **Borderline**: the amount is a cap, not what the bidder writes on a bid form. Recorded so it is done the same way every time; a native speaker may disagree.

**unified_qualification** (F-0007, `f19cddbd4cba` h_s41). Accepted category: `「物品の製造」、「物品の販売」又は「役務の提供等」`, brackets and 又は kept. Rejected: `物品の製造、物品の販売、役務の提供等`.

**value_ja without ellipsis** (F-0009, `563042df9941` h_s35). One labeler shortened the quote with `…`, so it was not found in the cited sentence. The shorter exact quote `見積もった契約金額の１１０分の１００に相当する金額を入札書に記載すること` was accepted. For two parts (F-0020, h_s22 and h_s23) the parts are joined with a line break; a `; ` join failed value_in_citation.

## Answer forms (sv3)

Gemini answers in plain JSON mode since sv3 (D-49), so the prompt describes the shape of every `normalized` value instead of sending a schema. The forms below are generated from the pydantic models in `core/shiori_core/fields.py` by `eval/silver/prompt.py` (`field_form`) and sent in the field list of every prompt, with a one-line hint per field. `tests/test_silver_sv3.py` fails if this block and the code disagree. `a|b` is a choice, `[x, ...]` a list, `str|null` an optional text. Values a label never uses inside a field (`not_stated`, `see_other_document`) are left out: those are field statuses.

The whole answer is one object: `{"fields": {"<field>": {"status", "ref", "value_ja", "value_en", "citations", "reason"}}, "normalized": {"<field>": value or null}}`, with an entry in `fields` for every field asked and a key in `normalized` for every asked field that is not a text field.

<!-- forms:start -->
- title: text (value_ja only, no normalized)
- issuer_org: text (value_ja only, no normalized)
- contracting_officer: {"title": str|null, "name": str|null}
- notice_date: {"date": "YYYY-MM-DD"}
- procurement_type: {"type": open_competitive|designated_competitive|proposal_competition|public_solicitation|negotiated|open_counter|other}
- award_method: {"method": lowest_price|best_value|other}
- item_category: {"codes": [str, ...]}
- scope_summary: text (value_ja only, no normalized)
- performance_period: {"start": "YYYY-MM-DD"|null, "end": "YYYY-MM-DD"|null, "relative_text": str|null}
- delivery_deadline: {"date": "YYYY-MM-DD"}
- delivery_location: text (value_ja only, no normalized)
- eligibility: {"items": [{"kind": unified_qualification|legal|suspension|experience|certification|other, "polarity": requirement|disqualification, "text_ja": str, "text_en": str|null, "citations": [str, ...]}, ...]}
- unified_qualification: {"grades": [A|B|C|D, ...], "category": str|null, "region": str|null}
- deadlines: {"items": [{"kind": bid_in_person|mail_arrival|electronic|bid_opening|question|briefing|document_request|other, "datetime": str|null, "relative_text": str|null, "flags": [arrival_required|postmark_ok, ...], "citations": [str, ...]}, ...]}
- submission_modes: {"modes": [in_person|mail|electronic, ...], "mail_not_allowed": bool}
- bid_bond: {"status": required|waived|waived_with_proviso, "rate_percent": number|null}
- performance_bond: {"status": required|waived|waived_with_proviso, "rate_percent": number|null}
- tax_basis: {"basis": bid_excludes_tax|bid_includes_tax}
- language_currency: {"language": str|null, "currency": str|null}
- required_documents: {"items": [{"name_ja": str, "name_en": str|null, "citations": [str, ...]}, ...]}
- contact: {"org": str|null, "department": str|null, "phone": str|null, "email": str|null}
- wto_covered: {"covered": bool}
- spec_access: {"mode": public|email_after_pledge|at_counter}
<!-- forms:end -->

## Not settled here

- A regional office that signs a notice in its own name with its own 支出負担行為担当官 (for example a 地方整備局). The rule says everything below the ministry or 庁 is department; no pilot example has tested it yet.
- A notice that gives only an opening time (開札) and never names 入札書. The rule needs a mention of the bid form, so 入札書 is not added; no example yet.

## From the sv3 pilot review (in the prompt since sv4)

Answers in `data/cache/labeling/answers/pilot2.txt`, `pilot3.txt` and `pilot4.txt`.

- **eligibility polarity** (F-0042, `28ad40ea4b1f`): an item whose text_ja keeps …ないこと is a requirement.
- **award_method** (F-0046, `28ad40ea4b1f`): proposal and estimate scored together, highest score wins: best_value. F-0015 (`4b0b9d8229c7`): committee selection, no scoring: absent.
- **scope_summary** (F-0049, `28ad40ea4b1f`; F-0024 reopened as F-0057, `563042df9941` h_s28 `入札説明書による。`): the work-content line, or see_other_document when it only points elsewhere.
- **spec_access** (F-0044, `28ad40ea4b1f`): 別紙「仕様書」のとおり is see_other_document, kind spec.
- **title** (F-0047, `28ad40ea4b1f`): the 委託業務名 line, not the 公募要領 heading.
- **issuer_org vs 調達機関** (F-0055, `f19cddbd4cba`): 調達機関 法務省, issuer 出入国在留管理庁.
- **delivery_deadline on a services contract** (F-0050, `4c40bbd831fe`): absent; 契約期間 is the performance period.
- **issuer_org from client-organization sentences; contact vs delivery place** (F-0039, `4c40bbd831fe` p5_s5, p1_s23, p5_s19): above.

## From the gold wave 1 review (not in the prompt)

- **eligibility, minors exception** (F-0076 `136dfba9ee59`, F-0081 `84e9d0c8325c`, F-0137 `a13baaac55c8`): the なお/ただし sentence about 未成年者, 被保佐人 or 被補助人 who have the needed consent stays inside the 第70条 item. Same item, same text_ja, and its sentences go in that item's citations. It is not a separate item and not dropped.
- **eligibility, 第73条 item** (`f19cddbd4cba` h_s43, `5d75d4a67c71` h_s38): 予算決算及び会計令第73条の規定に基づき、支出負担行為担当官が定める資格を有する者であること is kind other, not legal (D-71).
- **deadlines, bid receipt kind** (F-0059 `136dfba9ee59`, F-0064 `84e9d0c8325c`, F-0132 `a13baaac55c8`): a bid receipt deadline on an electronic notice is kind electronic. Kind mail_arrival with flag arrival_required only when 必着 is in a cited sentence (F-0132, h_s95). 到着するよう alone (F-0064, h_s85) gives mail_arrival with no flag, because the validator reads only 必着 and 消印有効 as flags.
- **submission_modes, paper and mail** (F-0068 `136dfba9ee59`, F-0072 `84e9d0c8325c`): when the notice allows paper bidding on request and gives a bid submission place, in_person counts. mail counts only when a sentence says mail or 郵送 (F-0072, h_s85); F-0068 never says it, so no mail.
