# Field schema (v1, frozen)

**schema_version 1.1.0.** The fields Shiori extracts from a tender document. Frozen on 2026-10-02 (D-39). The same ids, `applies_to` lists and enums live in `core/shiori_core/fields.py`, and `tests/test_fields.py` fails if the table below and the code disagree. After this point a change to a field id, an enum value or `applies_to` needs a decision entry and a relabel plan, and `schema_version` goes up. Every label file records the version it was made with.

## Unit and citations

- The label unit is the **document**, not the bundle. A field answered by a different document of the bundle is `see_other_document` for this one (SEM-8).
- Citations are Japanese sentence ids (`p2_s14`, `h_s31`). English Summary sentences (`Sentence.language == "en"`) are never cited. They are a cross-check signal for later (`en_summary_agrees` in the auto checks), not evidence.
- All datetimes are JST (`+09:00`).

## Result format

Every field produces one result (architecture.md); the label file uses the same shape plus provenance (eval_protocol.md):

```json
{
  "field": "bid_bond",
  "status": "present",
  "value_ja": "入札保証金 免除",
  "normalized": {"status": "waived", "rate_percent": null},
  "value_en": "Bid bond: waived",
  "citations": ["p3_s12"]
}
```

Field status values:
- `present`: the document states a value; `citations` has at least one sentence.
- `absent`: the document does not state it, **or the field does not apply to this document's type** (see `applies_to`). Absent is labeled explicitly: a system that shows a value for it is hallucinating, and that counts in the hallucination rate. `value_ja`, `normalized` and `citations` are empty.
- `see_other_document`: the document points elsewhere for this field. `normalized` is `{"ref": {"kind": ..., "text_ja": ...}}` with `kind` one of `spec`, `bid_instructions`, `other_notice`, `kokuji` (a 告示 number such as 告示第808号), `other`; `citations` holds the sentence that points.
- At run time the pipeline also has `verified`, `not_found` and `unverified` (D-04). Those are prediction states, not label states.

Inside a value, `not_stated` (bonds, `spec_access`) and `see_other_document` (`spec_access.mode`) are what an extractor may emit. A label never uses them: it uses field status `absent` or `see_other_document` instead, so each fact has one spelling.

## v1 fields

Heading cues are what to look for in section titles and line starts. They feed the `locate` module and help with checking labels. `applies_to` lists the `doc_type` values that normally contain the field (`notice`, `tender_page`, `bid_instructions`, `spec`; the other types are not labeled in v1). A field outside its `applies_to` types is labeled `absent`.

| Field id | Type | applies_to | Heading cues | Normalized form | Notes |
|---|---|---|---|---|---|
| `title` | text | notice, tender_page, bid_instructions, spec | 件名, 調達件名, 購入等件名, 業務名, 業務の名称 | null (value_ja) | |
| `issuer_org` | text | notice, tender_page, bid_instructions, spec | 発注機関, 調達機関, notice header | null (value_ja) | ministry/agency/municipality |
| `contracting_officer` | object | notice, tender_page, bid_instructions | 支出負担行為担当官, 契約担当官, 契約責任者 | {title, name} | at least one of the two |
| `notice_date` | date | notice, tender_page | top of notice, before 記 | {date} | |
| `procurement_type` | enum | notice, tender_page, bid_instructions | 一般競争入札, 指名競争入札, 企画競争, 公募, 随意契約, オープンカウンター | {type}: `open_competitive`, `designated_competitive`, `proposal_competition`, `public_solicitation`, `negotiated`, `open_counter`, `other` | |
| `award_method` | enum | notice, tender_page, bid_instructions | 落札者の決定方法, 総合評価, 最低価格 | {method}: `lowest_price`, `best_value`, `other` | |
| `item_category` | codes | notice, tender_page | 品目分類番号 | {codes: [string]} | numeric category codes on national notices |
| `scope_summary` | text | notice, tender_page, bid_instructions, spec | 調達件名の特質等, 業務内容, 概要, 目的 | null (value_ja) | 1 to 3 sentences, often from the spec; `value_ja` is the cited text, joined with a line break |
| `performance_period` | date range | notice, tender_page, bid_instructions, spec | 履行期間, 契約期間, 履行期限, 委託期間, 業務の期間 | {start, end, relative_text} | apply DATE-6 for 年度 phrases; at least one part set |
| `delivery_deadline` | date | notice, tender_page, bid_instructions, spec | 納入期限 | {date} | for goods |
| `delivery_location` | text | notice, tender_page, bid_instructions, spec | 納入場所, 履行場所 | null (value_ja) | |
| `eligibility` | list | notice, tender_page, bid_instructions | 競争参加資格, 参加資格, 暴力団関係事業者, 指名停止 | {items: [{kind, polarity, text_ja, text_en, citations}]} | `kind`: unified_qualification, legal, suspension, experience, certification, other. `polarity`: requirement or disqualification (SEM-3). 暴力団関係事業者 items are `legal` disqualifications, 指名停止 items are `suspension` |
| `unified_qualification` | object | notice, tender_page, bid_instructions | 全省庁統一資格, 等級, 営業品目, 競争参加地域 | {grades: [A..D], category, region} | split out because it's the first gate for most bidders |
| `deadlines` | list | notice, tender_page, bid_instructions | 入札日時, 入札書の受領期限, 提出期限, 受付期間, 開札の日時及び場所, 開札日時, 入札場所, 質問, 質疑, 質問書の提出期限, 入札説明会, 説明会, 公募期間, 応募期間, 受領期限, 必着 | {items: [{kind, datetime, relative_text, flags, citations}]} | one item per dated event, see below |
| `submission_modes` | object | notice, tender_page, bid_instructions | 電子調達システム, 電子入札, 持参, 郵送, 郵便等による入札の可否, 認めない | {modes: [in_person, mail, electronic], mail_not_allowed} | `mail_not_allowed` is true when mail bids are refused (認めない); then `mail` is not in `modes` |
| `bid_bond` | object | notice, tender_page, bid_instructions | 入札保証金 | {status, rate_percent} | `status`: required, waived, waived_with_proviso. `rate_percent` only with required or waived_with_proviso |
| `performance_bond` | object | notice, tender_page, bid_instructions | 契約保証金 | {status, rate_percent} | same as `bid_bond` |
| `tax_basis` | enum | notice, tender_page, bid_instructions | 消費税, 100分の10, 税抜, 税込 | {basis}: `bid_excludes_tax`, `bid_includes_tax` | NUM-6. No tax wording means `absent` (the draft's `unknown` is gone) |
| `language_currency` | object | notice, tender_page, bid_instructions | 使用する言語及び通貨 | {language, currency} | ISO codes, almost always `ja` and `JPY` |
| `required_documents` | list | notice, tender_page, bid_instructions | 提出書類, 提出物, 必要書類 | {items: [{name_ja, name_en, citations}]} | |
| `contact` | object | notice, tender_page, bid_instructions | 問い合わせ先, 担当, 連絡先 | {org, department, phone, email} | phone/email copied exactly, never translated |
| `wto_covered` | bool | notice, tender_page, bid_instructions | 政府調達に関する協定, WTO, 特定調達契約 | {covered} | `true` when the notice says the agreement applies, `false` only when it says it does not; silence is `absent` |
| `spec_access` | enum | notice, tender_page, bid_instructions | 仕様書, 入札説明書の交付, 誓約書, 閲覧 | {mode}: `public`, `email_after_pledge`, `at_counter` | how a bidder gets the specification. Pointing to another document is field status `see_other_document` |

### Lists: deadlines, eligibility, required_documents

One notice can have several deadlines (Wakayama `2f2f5bd3...`: in person 2026-10-27 14:00, mail must arrive by 2026-10-26 17:00, question deadline 2026-10-01 17:00). Each `deadlines` item is one dated event:

| `kind` | meaning |
|---|---|
| `bid_in_person` | bids handed in at a place and time (入札日時). In-person tenders have no 受領期限, so this is their bid deadline (Hokkaido `fb226cbd...`: 2026-09-10 13:30) |
| `mail_arrival` | bids sent by mail, with the arrival time (受領期限, 必着) |
| `electronic` | bids through an electronic system |
| `bid_opening` | 開札 |
| `question` | last day for questions (質問, 質疑) |
| `briefing` | 入札説明会, 現場説明会 |
| `document_request` | deadline to ask for or collect the documents (仕様書の交付 and the like) |
| `application` | the end of the period for submitting a proposal or application, when the document calls it 公募期間, 応募期間, 提案書の提出期限 or similar (Digital Agency `74aed2a5`: 公募期間 ends 2026-03-02 12:00) |
| `other` | any other dated step |

`datetime` is `YYYY-MM-DD` when the text gives no time, else `YYYY-MM-DDTHH:MM:00+09:00`. `relative_text` holds a non-calendar rule as written (入札説明書の交付後7日以内); exactly one of the two is set. `flags`: `arrival_required` (必着), `postmark_ok` (消印有効) (DATE-8). The line's `citations` are the union of the items' citations.

List fields are `present` when they have at least one item; an empty list is `absent`.

## Executive summary template (v0)

Built only from `verified` fields. Each line links to the fields it uses.

1. What: `{title}` for `{issuer_org}` ({procurement_type}, {award_method})
2. Deadlines: one line per `deadlines` item that is a bid deadline (`bid_in_person`, `mail_arrival`, `electronic`), with arrival flags, then `bid_opening` and `question`
3. Who can bid: `{unified_qualification}` + top requirement/disqualification items
4. Delivery: `{performance_period}` or `{delivery_deadline}` at `{delivery_location}`
5. Money terms: bid bond `{bid_bond}`, performance bond `{performance_bond}`, tax basis `{tax_basis}`
6. To submit: `{required_documents}` via `{submission_modes}`
7. Specification: `{spec_access}`
8. Contact: `{contact}`

Lines with missing fields say "not found in document" rather than disappearing, so the user knows what to check by hand.

## Cues seen in the reviewed notices but not tied to a v1 field

前金払 (advance payment) and 契約書作成 (whether a contract document is drawn up) appeared as headings in the two reviewed notices (Hokkaido `fb226cbd...`, Wakayama `2f2f5bd3...`). No v1 field holds them; the cues only help the section parser tell where neighbouring sections start. Whether payment terms deserve a field is an open question (decisions.md).

## Changelog

- v1 draft: initial field list.
- v1.0.0 (2026-10-02, D-39): frozen. `submission_deadline`, `bid_opening`, `question_deadline`, `briefing_session` replaced by the `deadlines` list; `submission_method` replaced by `submission_modes` with `mail_not_allowed`; bonds became `{status, rate_percent}`; `spec_access` added; field statuses are `present`, `absent`, `see_other_document`; `applies_to` added; `tax_basis.unknown` dropped (absent says the same); cues from the two reviewed notices added.
- v1.1.0 (2026-11-21, D-97): deadline kind `application` added. Additive: 1.0.0 labels stay valid.
