# Japanese rules

What the pipeline has to handle when reading Japanese tender documents. Written for someone who doesn't read Japanese yet: every rule has an example and an English gloss.

How to use this file:

- Each rule has an ID (e.g. `NUM-3`). Tests that implement a rule reference its ID.
- Rules marked **[verify]** are believed correct but should be confirmed against collected documents before relying on them. When confirmed, remove the tag and note the doc ID.
- New rules come from the Phase 5 failure log. Add them here with an example from a real document.

---

## 1. Characters, normalization, segmentation

**TXT-1. No spaces between words.** Japanese is written without word spaces. Never split on whitespace. Spaces that do appear are usually layout artifacts (justified text, table padding) or full-width spaces (U+3000) used for indentation.

**TXT-2. Keep original, normalize a copy.** Store `text_orig` exactly. Build `text_norm` for matching, with an offset map so a match in `text_norm` can be highlighted on the original glyphs.

**TXT-3. NFKC is the base normalization, with exceptions.** NFKC turns full-width ASCII into half-width (`２０２６` -> `2026`), half-width katakana into full-width (`ｼｽﾃﾑ` -> `システム`), and expands compatibility characters (`㈱` -> `(株)`, `㍻` -> `平成`). Watch out:
- It turns circled numbers into plain digits (`①` -> `1`). In tenders, ①②③ are often list markers. Detect them as markers **before** NFKC.
- It changes string length, so the offset map must be built character by character, not assumed.

**TXT-4. Lookalike characters.** These get confused in extraction and break matching. Map them to one form in `text_norm`:
- Wave dash `〜` (U+301C) vs full-width tilde `～` (U+FF5E). Both used for ranges.
- Long vowel mark `ー` (U+30FC), full-width minus `－` (U+FF0D), hyphen `‐` (U+2010), en dash `–`. In katakana words `ー` is correct; between numbers it's a range or minus.
- Kanji variants (異体字): `髙`/`高`, `﨑`/`崎`, `邊`/`辺`. Mostly in names. Normalize for matching only; never in displayed text.
- Seen in Phase 2 part B: `―` (U+2015, horizontal bar) as the dash in form numbers, `様式３―Ａ` next to `様式３－Ｂ` in the same sentence (doc `ab5e74f19ac1...`, Yokosuka, p6). Mapped to `-` with the other dashes. **[verify]** that U+2015 is never a real long dash in running text.

**TXT-5. Punctuation.** Sentence end: `。` (sometimes `．` in older or technical government docs). Comma: `、` (sometimes `，`). Quotes: `「」` and `『』`. Parentheses: `（）`. Middle dot `・` separates list items or katakana words.

**TXT-6. Segmentation is not just `。`.** Split on `。！？`, but also at:
- line starts with list markers (`1`, `(1)`, `（１）`, `ア`, `(ア)`, `①`, `・`)
- table cell boundaries
- `記` and `以上` lines (see DOC-1)
Many tender lines are label-value items with no `。`: `（３）納入期限　令和8年3月31日` means "(3) Delivery deadline: 31 March 2026 (Reiwa 8)". Each such item is its own segment.
- Phase 2 part B patterns (implemented in `segment.py`, D-32), each **[verify]** with a Japanese reader:
  - A line that starts with hiragana or closing punctuation continues the previous sentence even when the previous line ends short of the margin. The source breaks `...公正かつ厳正に行い` / `ます。` early (doc `ab5e74f19ac1...`, Yokosuka, p6). Hiragana can't start an item.
  - `※` (note) and `◎` start items like `・` does: `◎調達機関番号 020 ◎所在地番号 13` (doc `2aa7506afc08...`, JMA notice, p2).
  - A table-of-contents line (dot leader, then a page number) is one item: `4. 作業の実施内容に関する事項 ....... 4` (doc `8a00ce8d8cae...`, Digital spec, p2). Without this rule the whole TOC became one 2,600-character sentence.
  - In ruled tables, the lines of one cell can come out of the PDF interleaved with the next cell's lines (doc `3f8e45974117...`, Wakayama Q&A, p1). Segmentation keeps a cell's lines together.
  - One visual line can come out of the extractor as two lines on the same baseline, overlapping by a glyph (doc `209ff2190e47...`, JMA, p4: `「競争参加者の資格に関する公示」` | `（令和８年３月`). They are joined back; lines with a real gap between them are table cells or columns and stay apart.
  - An inline list `次により（ａ）参加申込書...、` that wraps so `（ｂ）法人の登記事項証明書...` starts a line looks like a new item (doc `ab5e74f19ac1...`, p5). It is split there but opens no section level (DOC-2).
- Phase 2 part C patterns (D-37), each **[verify]**:
  - A sentence with an unclosed bracket continues onto the next line even when the line is short: `2:00 p.m. 27 October 2026（Deadline for bids submitted by mail : 5:00 p.m. 26` / `October 2026）` (doc `2f2f5bd332965253...`, Wakayama, p3, English Summary).
  - A line that starts in lowercase Latin continues the line before it when that ends in a letter or comma: `...a financial accounting system and` / `lease of equipment` (same page). Not when the line before ends in a digit: `FAX 073-423-3502` and `e-mail e1201003＠...` stay two items.
  - A heading and its body can be one line with no space and no break: `(10)入札の取りやめ又は延期この入札は、取りやめること又は延期することがある。` (doc `fb226cbdd14b...`, Hokkaido, p3). Not split: known limitation (open question). Section titles taken from such a sentence are the whole first 40 characters.

**TXT-7. Tokenization only where needed.** For BM25 indexing use SudachiPy (mode C) or fugashi + UniDic. Segmentation and matching do not need tokenization.

**TXT-8. Legacy encodings.** Old `.txt`/`.csv` attachments may be Shift_JIS / CP932. Decode with `cp932`, not `shift_jis`, since CP932 covers Windows-specific characters like `①` and `㈱`.

**TXT-9. Spaced-out digits in text layers.** **[verify]** how widespread. Some PDF text layers put a space between every character of a number, probably because the PDF places each glyph separately (character spacing or justified layout). In `text_norm`, remove spaces between two digits, and between a digit and one of `年 月 日 時 分 円 万 億`, in either order. Leave every other space alone (TXT-1: some spaces are real, e.g. table padding between a label and its value). Spaces removed here must be recorded in the offset map like any other deletion (TXT-2).
- Example, doc `209ff2190e47b6d02169d1d985f8e1c3f04354a4166ec42d45e2e8a626800a4f` (JMA, page 1): the text layer reads `令和８年６月\n1 6 日` for `令和8年6月16日` ("16 June, Reiwa 8"). After this rule: `1 6 日` -> `16日`.
- The same doc and the other two JMA samples also have `0 2 0`, `1 1 月`, `3 0 日`, and doc `2aa7506afc0882cdbe20dfe37fd643ab19099247fc0450613da07c427a81973c` has `1 6 日\n1 6 時\n0 0` (16th, 16:00), where line breaks also split one date or time. Joining across line breaks is a separate, riskier step (a line break between two numbers can be a real table cell boundary) and is not part of this rule.
- Risk: two separate numbers that happen to sit next to each other with one space (e.g. adjacent table cells `1 2`) would be merged. Check how often that happens once the extractor knows table cells.
- Seen after the first collection run (2026-10-02, 62 PDFs): spaces *between digits* only in the 3 JMA files, but a space *between a number and its unit* in 28 of 34 Digital Agency PDFs and 7 of 25 Funabashi PDFs, so the digit-unit half of this rule matters far more than the JMA example suggests. It looks like the gap word processors leave between half-width digits and full-width text. Examples: `令和8 年5 月` in doc `bc1edf9db02c025655c776072537598385752032cb542114d8615fe7dd6b84d5` (Funabashi, page 1), `100 円未満` ("under 100 yen") in doc `10be3ae3df341944e162faafa85ace8105d4beb7c887f3e4c6f0e64c3a9d8019` (Digital, page 5). Doc `2a4dacf5624b6341f80d80993d33bdc141a6b6c1f8777b444ac5a8c6ad9a655d` (Digital, page 3) also has a space between the era name and the digit: `令和 2 年 12 月 25 日`. Phase 2 part B: implemented, the space between an era name (`令和 平成 昭和 大正 明治`) and a digit or `元` is removed too. **[verify]**
- Seen again in the city survey (2026-10-02): digit-unit spaces in samples from Wakayama, Okayama and Niigata prefectures, Hokkaido, Koriyama and Kanazawa. After the part D collection, 98 of 237 local-government PDFs have at least one, across 9 organizations.
- Phase 2 finding (2026-10-02): many of these spaces are not in the PDF at all. MuPDF inserts a space wherever it sees a gap between glyphs; the extractor now turns that off (D-29). The JMA `1 6 日` comes out as `16日`, and English pages lose their letter spacing. The spaces counted above were measured with the default, so they overstate the problem. With the Phase 2 extractor, over all 322 PDFs: a digit-space-unit pair (either order) in 46 PDFs from 10 sources, a digit-space-digit pair in 23 PDFs from 8 sources. Those are real space glyphs, e.g. `令和 2 年 12 月 25 日` (doc `2a4dacf5...`, Digital, page 3, fixture `digital_text.pdf`). The rule still applies to them, but check the 23 digit-space-digit cases before relying on it: some are table cells or section numbers (the Yokosuka counterexample below). **[verify]**
- Counterexample, open doc `22f7df9a01b83c2c5ea8d96584b8888c296c8e4cc491a6ca755fa148ce7be3d1` (Okayama): `２ １の各号に掲げる者が、当社又は当団体の経営に実質的に関与していません。` is item number `２` followed by a reference to item `１` ("each item of 1"). Joining the digits gives `21の各号`, which is wrong. So detect line-start section numbers (TXT-6, DOC-2) **before** this rule runs, and never join a space that follows a line-start list marker.

**TXT-10. Letter-spaced headings and form labels.** **[verify]** how widespread. Short headings, form titles and label cells are often spread out to fill a width (均等割り, even spacing), and the text layer then has a space after every character. In `text_norm`, when three or more single CJK characters (kanji or kana) are each separated by exactly one space, remove those spaces. This matters for heading cues (field_schema.md) and section detection, which would otherwise miss the heading.
- Example, doc `56d0c0a1cc3ffedd347e89304559985956e26bd8c51be3828e94d1d6b3e4d48e` (Digital, page 1): `再 委 託 承 認 申 請 書` for `再委託承認申請書` ("application for approval of subcontracting"). The same form is appended to two specs (docs `756d17c8...`, `d313a509...`).
- Doc `fd1a4b7d9a7ad3e4f154fa1e9302a0cf69c062059b728ab543ba3825cd69088a` (Digital, pages 19, 22, 23): `作 業 依 頼 書` ("work request form").
- After the part D collection: letter-spaced runs in 39 of 237 local-government PDFs across 6 organizations (most in Hokkaido, 15).
- Risk: in doc `abb788301429d7b1b08ddabffb6f5a047e69c82bdee5ecba3689a02fa517b5c6` (Digital, draft contract) the signatory line reads `官 田 邉 国 治`, a job title followed by a person's name. Joining it is fine for matching, but the real word boundaries are lost, so never use `text_norm` for display.

**TXT-11. Private Use Area characters as bullets.** **[verify]** that they are always bullets. They are not always: see TXT-12. Only treat a PUA character as a bullet when it is at the start of a line or directly before a URL. Some Word-generated PDFs map bullet glyphs from symbol fonts to Unicode Private Use Area code points, which have no meaning and render as boxes. Seen: `U+F09E` at the start of list items, 31 times in doc `756d17c840065acfd806390bdc4af550fc586b1aa3244d85efb1e9d7af15ea6e` (Digital spec, pages 21 and 28) and 28 times in doc `d313a5093ec965c7d109d167031bb2fd32f9243000b028cf85a3c78ddb57842a` (Digital spec); `U+F09F` in doc `2a4dacf5624b6341f80d80993d33bdc141a6b6c1f8777b444ac5a8c6ad9a655d` (page 22). Treat a PUA character at the start of a line as a list marker for segmentation (TXT-6) and drop it from `text_norm`. Never show it in the UI. Real Unicode bullets like `⚫` (U+26AB, doc `6e16813abe483cc834c2d3605bd12cdc6378960d08ccd621b304d44c950e8652`, Funabashi, page 2) are list markers too. Also seen as a bullet: `U+F8FD` before a URL in doc `b16ad9882fbccf2ccb7dcf3454b61abe7c72eeba06c4052bb2a32af881893d4a` (Niigata Prefecture, page 5). Not a bullet but also meaningless as text: `U+F02C` after 代表者職氏名 ("representative's title and name") on a bid form, doc `073ad71ae49287618e788c0c3ddca4740b7a23dcf3e5a83a92cf5177aa23b73a` (Okayama, 入札書, page 1), probably where the seal (印) goes **[verify]**.

**TXT-12. Private Use Area characters as custom kanji (外字).** **[verify]** which kanji is meant. Japanese offices define custom characters (外字, gaiji) for rare kanji in place and personal names, and these come out of the text layer as PUA code points. Unlike TXT-11 bullets, they carry meaning, so never drop them and never guess the character silently.
- Example, doc `94521ecfd7f468991447db5f31bfa86a2129f3b0f366317e09b5085db2d71b89` (Nara City, notice, page 1) and doc `faef6e6a09d935a2162d0ec42e31d8a14b9ceeba92f8ddbec19b87474f8cfbde` (Nara City, spec, page 3): `都\ue27d南之庄町`, `都\ue27d甲岡町`, `都\ue27d友田町`, all district names in Nara City. The text layer can't say which kanji it is, but the rendered page shows `祁`, so the text reads `都祁南之庄町` (the Tsuge area). Checked by rendering the glyph, 2026-10-02. The spans around it are in MS-Mincho, so the 外字 was probably a variant form of 祁 that the office's font lacked.
- How it is stored (Phase 2, 2026-10-02): in both Nara PDFs the 外字 is not a font glyph. Word drew it as a small image tagged with /ActualText U+E27D. MuPDF gives that character an empty box, and its per-character output drops it, so the extractor puts it back with the box of the character cell before the next character (D-29, `pdf._recover_pua`). Doc `faef6e6a...` page 3 has 6 of them, doc `94521ecf...` page 1 has 1. Expect other offices' 外字 to arrive the same way.
- Handling: keep the PUA character in `text_orig`; in `text_norm` map it to a placeholder that can't match anything by accident; show the rendered glyph (image crop) in the UI instead of a box. A small per-document table PUA -> confirmed kanji could be added later if the same code points repeat.

**TXT-13. Single-glyph parenthesized numbers are list markers.** **[verify]** the level. `⑴ ⑵ ⑶` ... `⒇` (U+2474 to U+2487) are one character each, and NFKC turns each into three: `⑴` -> `(1)`. In the local-government PDFs they almost always start a line (419 of the 446 uses of `⑴` to `⑹`, 94%), as the `(1)` level of 公用文 numbering (DOC-2). Detect them as list markers before NFKC, like `①` (TXT-3), and remember that NFKC changes the string length here (TXT-2 offset map).
- Example, doc `8666347d881d68640b4a04d3c659b04e7cceb8294cec5264fc0fa6fb0ac88b9c` (Funabashi spec): `⑴ 災害対策基本法 ⑵ 個人情報の保護に関する法律 ⑶ 船橋市地域防災計画`, a list of laws the contractor must follow.
- Common in this corpus: hundreds of uses each in the Asahikawa, Funabashi and Wakayama files. Check whether a document mixes `⑴` and typed `(1)` at the same level before treating them as equal.
- Phase 2 part B: `⑴` and typed `(1)` / `（１）` are treated as the same numbering style (both normalize to `(1)`). No document mixing them at different levels has been seen yet. **[verify]**

**TXT-14. Vertical-form glyphs mapped to wrong code points.** **[verify]** the mapping, read off the rendered page. In vertical text, brackets, the long vowel mark and 。 have separate vertical glyphs. Some PDFs map those glyphs to unrelated code points, so the text layer has rare CJK Extension A ideographs or Latin phonetic letters where the punctuation should be. Seen in doc `6b36d69abc0d311de1b79374fdbd2947508cd13a4ba0ea015e06cb8452177685` (Okayama 入札説明書（別紙）, page 9, envelope example, fixture `okayama_rotated_vertical.pdf` page 2; producer iText): `郵送の場合の内封筒䥹裏面は封印のこと䣎䥺` for `郵送の場合の内封筒（裏面は封印のこと。）` ("inner envelope when sent by post (seal the back)"), and `ᵯiPad端末管理ツᶌルライセンス䣖の` for `「iPad端末管理ツールライセンス」の` ("iPad device management tool licenses"). Mapping read from the render: `ᵯ` U+1D6F -> `「`, `䣖` U+48D6 -> `」`, `ᶌ` U+1D8C -> `ー`, `䥹` U+4979 -> `（`, `䥺` U+497A -> `）`, `䣎` U+48CE -> `。`. Doc `34ef78f9cc26...` (Okayama, pages 12 and 13, same layout) also has `䣓 䣔 䣕 ᵰ`, not yet read. NFKC leaves all of these unchanged. The extractor keeps them and counts them as suspect characters (`ingest.is_suspect`); `extraction_report.md` lists the pages. Normalization could map them per document, but only after the mapping is confirmed.

**TXT-15. Kangxi radicals in place of kanji.** **[verify]** how widespread. `⾧` (U+2FA7, KANGXI RADICAL LONG) appears where `長` is meant: `次⾧`, `部⾧`, `課⾧` (deputy director, department head, section head) in doc `520549b35c98...` (Asahikawa, page 1), `延⾧` (extension) in doc `12f50d0602ce...` (Wakayama, page 2). They look identical, but a search for `長` misses them. NFKC maps U+2F00 to U+2FD5 to the ordinary kanji, so `text_norm` handles it; never search `text_orig`.

**TXT-16. Other lookalikes NFKC does not fix.** **[verify]** how widespread.
- `﴾ ﴿` (U+FD3E, U+FD3F, ornate parentheses from the Arabic block) used as `(` `)` in Digital specs: doc `6af28f8826d9...` pages 25, 51, 52 (`デバイスID﴾Device ID﴿`, page 52), and doc `8a00ce8d8cae...` page 26, where `﴾1﴿` and `﴾2﴿` are list markers (TXT-6, DOC-2). NFKC leaves them alone, so map them to `(` `)` in `text_norm` before list markers are detected.
- Cyrillic `О` (U+041E) for Latin `O` in `ＣＤО` and `ＴОＡ` (doc `52b0c72c1215...` page 1, doc `9b6a573a3652...` page 8, Asahikawa). NFKC leaves it alone. Matters only for matching Latin names.
- `︓` (U+FE13, vertical-form colon) in horizontal text, `※URL︓https...` (doc `d313a5093ec9...`, Digital, page 18). NFKC maps it to `:`.

**TXT-17. Joined lines of Latin text need a space back.** Japanese joins wrapped lines with nothing (TXT-1); English doesn't. Where a sentence is joined across a line break and both sides are Latin letters or digits, `text_norm` gets one space, mapped back to the line break, and `text_orig` stays as the PDF has it. Example, doc `2f2f5bd332965253...` (Wakayama, p4): `…640-8585, Japan` / `TEL 073-441-3288` is `Japan TEL`, not `JapanTEL`; `5:00 p.m. 26` / `October 2026` is `26 October 2026`. The space is not removed by TXT-9, so `100` / `200` stays two numbers. Kana and kanji next to Latin get no space. **[verify]**

**TXT-18. OCR text differs from text-layer text in small, regular ways.** **[verify]** NDLOCR-Lite (D-36) writes half-width brackets and digits, and drops spaces: where the text layer of doc `fb226cbdd14b...` (Hokkaido, p1, rendered to a picture and read back) has `契約締結の日から令和９年（2027年）１月29日まで` OCR gives `契約締結の日から令和9年(2027年)1月29日まで`, and `(2) 入札日時 令和８年（2026年）９月10日（木）午後１時30分` comes back as `(2)入札日時令和8年(2026年)9月10日(木)午後1時30分`. After NFKC the two agree except for the spaces, which TXT-9 and TXT-10 treat as layout anyway. What OCR gets wrong is measured in `data/manifests/ocr_report.md`.

---

## 2. Numbers and money

**NUM-1. Digit forms.** Arabic digits appear half-width (`123`) or full-width (`１２３`). NFKC handles both.

**NUM-2. Kanji numerals.** `〇一二三四五六七八九` with positional `十 百 千`. Examples: `二十五` = 25, `三百六` = 306, `千二百` = 1200. A leading `一` is often dropped (`十` = 10, `百` = 100, `千` = 1000).

**NUM-3. Large units work in groups of four digits.** `万` = 10^4, `億` = 10^8, `兆` = 10^12. These mix with Arabic digits:
- `1億2,345万円` = 123,450,000 yen
- `500万円` = 5,000,000 yen
- `3.5億円` = 350,000,000 yen
A converter that only handles digits will read `500万円` as 500. That's a classic failure.

**NUM-4. 大字 (formal numerals).** Bid forms sometimes use tamper-proof numerals: `壱`(1) `弐`(2) `参`(3) `拾`(10) `萬`(10,000). Rare in notices, more common in filled-in forms. Support them in the converter. **[verify]** frequency in corpus.

**NUM-5. Thousands separators.** `,` or `，`. Occasionally a space. Strip before parsing.

**NUM-5a. 千円 units and unit labels.** **[verify]** Amounts in thousands of yen: `見積上限額 金1,100千円` = 1,100,000 yen (doc `8869632bb85c...`, Wakayama), and `千円未満の端数` = "fractions under 1,000 yen" (doc `b8feb4d29162...`). A unit in a table header, `（単位：千円）` or `金額（千円）`, is not an amount. Blank and placeholder amounts in forms: `金     円` (doc `0f7b9667dcd5...`), `契約金額(税込) ●円` (doc `756d17c84006...`, Digital spec annex).

**NUM-4 frequency (Phase 2 part B):** no 大字 amounts in the 322 PDFs. Don't detect 大字 by character alone: `参` is in `参加` ("participation") on almost every page.

**NUM-6. Tax wording changes the meaning of an amount.**
- `税込` / `消費税込み` = tax included
- `税抜` / `税別` = tax excluded
- `消費税及び地方消費税` = consumption tax and local consumption tax (together 10% at the standard rate)
- Many national tender notices say the bid amount should **exclude** tax, and the winning price is the bid amount plus 10%. The standard clause reads roughly: `落札決定に当たっては、入札書に記載された金額に当該金額の10％に相当する額を加算した金額（…）をもって落札価格とするので` ("the award price is the amount on the bid form plus an amount equal to 10% of it"; open doc `2aa7506afc08...`, JMA, with a rounding parenthetical shown here as `（…）`; Wakayama notices such as open doc `2f2f5bd3...` write `100分の10` instead of `10％`). Extract the tax basis as its own attribute. **[verify]** exact wording varies by agency.
- Variants seen (Phase 2 part B, **[verify]**): `入札書に記載された金額に当該金額の10％に相当する額を加算した金額` (10% instead of 100分の10, doc `2aa7506afc08...`, JMA); `見積もった契約金額の110分の100に相当する金額を入札書に記載すること` ("write 100/110 of the estimated price on the bid form", same doc and 14 others); `消費税及び地方消費税の額を含まない金額を入札書に入力すること` (doc `88d80c6c71c6...`). Not tax: `契約金額の100分の10に相当する額以上の契約保証金` is a performance bond of 10% of the price. Only the `加算` and `入札書に記載` forms say anything about tax. The two halves can combine the other way: `見積もった金額に当該金額の１００分の１０に相当する額を加算した額を見積書に記載` (doc `28ad40ea4b1f...` p6_s10) says the amount **written** already has the 10% added, so it includes tax (`bid_includes_tax`). The rule for it runs before the award-clause rule, which shares its first half; `110分の100 ... を入札書に記載` stays tax excluded.

**NUM-7. Ceiling price.** `予定価格` is the internal ceiling price. It is usually **not** disclosed in the notice before bidding; some local governments publish it in advance (`予定価格の事前公表`). If a document states it, extract it; never infer it.

---

## 3. Dates and times

**DATE-1. Japanese eras.** Dates are usually written in era years.

| Era | Reading | Starts | Gregorian = era year + |
|---|---|---|---|
| 令和 | Reiwa | 2019-05-01 | 2018 |
| 平成 | Heisei | 1989-01-08 | 1988 |
| 昭和 | Showa | 1926-12-25 | 1925 |
| 大正 | Taisho | 1912-07-30 | 1911 |
| 明治 | Meiji | 1868 | 1867 |

Example: `令和8年10月2日` = 2026-10-02.

**DATE-2. 元年 means year 1.** `令和元年` = 2019. Treat `元` as 1 only directly before `年`.

**DATE-3. Era boundary years.** 2019 is both `平成31年` (Jan 1 to Apr 30) and `令和元年` (from May 1). Validate: `平成31年6月` is invalid and signals an OCR or typing error.

**DATE-4. Abbreviated forms.** `R8.10.2`, `R8/10/2`, `令8.10.2`, `H31.4.1`, and single-glyph eras `㋿` (U+32FF) and `㍻`. Gregorian years also appear: `2026年10月2日`, sometimes both: `令和8年（2026年）10月2日`.
- Seen: `R8.2.13`, `R7/11/7` (doc `fd1a4b7d9a7a...`, Digital 運用マニュアル, pp. 22 and 2), `R7年度` (doc `72cf89b9a2b7...`, Wakayama Q&A), and the western year in brackets after the era year, `令和８年 (2026年）８月19日` (doc `fb226cbdd14b...`, Hokkaido notice). No kanji-numeral dates (`令和八年`) in the 322 PDFs. **[verify]**

**DATE-5. Weekday in parentheses.** `令和8年10月2日（金）`. Weekday kanji: `月火水木金土日` = Mon to Sun. Use it as a check: if the computed weekday doesn't match, flag the date.
- The check catches real errors: 5 documents give a weekday that doesn't match the date, e.g. `令和8年3月3日(水)から令和8年3月16日(月)` (doc `4a654d8861b5...`): 16 March 2026 is a Monday but 3 March is a Tuesday. Since D-38 the converter returns the date as written with a `WeekdayMismatch` warning (the date, the weekday it really falls on, the weekday written), because it can't tell which part is the typo; it used to return no value. Also seen: `（金曜日）` spelled out (doc `4397a1092113...`). **[verify]** each case against the rendered page.
- A matching weekday is evidence the day number was read right: `令和８年（2026年）９月10日（木）午後１時30分` (doc `fb226cbd...`, Hokkaido, `p1_s22`) and `令和８年（2026年）９月29日（火）午前10時00分` (doc `737f48e78112...`, `p2_s2`) both agree with the calendar.

**DATE-6. Fiscal year (年度).** Japanese government fiscal year runs **April 1 to March 31**. `令和8年度` = 2026-04-01 to 2027-03-31. Phrases like `令和8年度末まで` ("until the end of FY Reiwa 8") mean 2027-03-31, not 2026-12-31. This is one of the most common silent errors.
- Seen: lists of consecutive years, `令和４･５･６年度国土交通省競争参加資格` (doc `2aa7506afc08...`, JMA: the unified qualification for FY Reiwa 4 to 6), converted to one range; the western form `（2025年度）` (doc `10be3ae3df34...`); placeholders `令和○年度` (doc `79004c98b435...`) and `0000年度` in a form template. `1年度目` ("the first year") has no era and is not a fiscal year. **[verify]**
- Month-end: `令和9年3月末` means the last day of that month and converts deterministically (no examples with a day count yet). `令和8年3月` alone is "year and month only": 182 matches, the most common date that can't be converted, often a planned month (`令和8年2月` in a schedule). **[verify]**
- Forms leave dates blank: `令和  年  月  日`, `令和８年 月 日` (year filled, month and day blank; doc `0f7b9667dcd5...`, Wakayama contract). 104 matches. The converter reports them as blank form fields rather than failures.

**DATE-7. Times.** `午前10時` = 10:00, `午後3時30分` = 15:30, `正午` = 12:00, `15時00分`, `17:00`. `午前0時` and `午後0時` exist and are ambiguous in casual use; flag them.

**DATE-8. Deadline semantics.**
- `必着` = must **arrive** by (postmark doesn't count)
- `消印有効` = postmark date counts
- `まで` = until (inclusive of that time in practice)
- `から` = from
- `以降` = on or after, `以前` = on or before
- `迄` = old form of `まで`
Store the arrival-vs-postmark attribute with the deadline. A bidder who misses this loses the tender.

**DATE-9. Relative dates.** `契約締結日から60日以内` = within 60 days from contract signing. These can't be turned into a calendar date. Store as relative, show as text.

---

## 4. Document structure

**DOC-1. Notice skeleton.** Japanese official notices commonly look like:

```
入札公告                          <- "Tender notice"
次のとおり一般競争入札に付します。   <- "We hereby put the following to open tender."
令和8年9月1日                      <- notice date
支出負担行為担当官 ○○省大臣官房会計課長 山田太郎   <- contracting officer, title, name
記                                <- marks start of the body ("as follows")
1 調達内容 ...
2 競争参加資格 ...
...
以上                              <- marks the end of the body
```

**DOC-2. Numbering hierarchy (公用文).** Section levels usually go:
`第1` -> `1` -> `(1)` / `（１）` -> `ア` -> `(ア)` -> `a` -> `(a)`
Some documents start at `1`. The katakana level uses the order `ア イ ウ エ オ カ キ ク ケ コ ...`. Parse this into a section path for every segment; it's the strongest signal for which field a sentence belongs to.

Seen in the corpus (Phase 2 part B, all **[verify]** with a Japanese reader). The parser does not assume a fixed hierarchy; each style takes the next level down the first time it appears (D-32):
- Dotted numbers `1.` -> `1.1` -> `1.1.1`, mostly in Digital Agency documents (doc `fd1a4b7d9a7a...`, 運用マニュアル) and in specs laid out as a table (doc `3fc2a22e507d...`, Okayama: `3.1 インターフェースとして...` inside cells). `1.0 版制定` (a version) and `3.0秒以内` (a measurement) are not section numbers.
- Contracts: `第１章` -> `第１条` -> `２` `３` (paragraphs) -> `⑴` (items) (doc `75a0c52799f9...`, Digital draft contract; doc `0f7b9667dcd5...`, Wakayama). The first paragraph of an article has no number, so the paragraph level starts at `２`. The article's title sits on the line above in brackets, `（契約期間）` before `第２条`; the parser gives that line the previous article's path (open question).
- Law-style items `一` `二` `三` (号) in eligibility lists citing 予決令 (doc `2baf60234d67...`, 5 documents in all).
- Circled katakana `㋐ ㋑ ㋒` as a level (docs `6c7ed844e973...`, `d43dd5c2172b...`, Kanazawa).
- Roman numerals `Ⅰ` `Ⅱ` as the top level of a spec (doc `c2f9213cead4...`, Okayama 整備仕様書), and `（ⅰ）` to `（ⅳ）` as a lower level (doc `3fc2a22e507d...`). 54 bare and 11 bracketed uses in 6 documents.
- Specs whose whole body is a table, numbered inside the cells (doc `3fc2a22e507d...`, Okayama; doc `6bed5f0434e7...`, Koriyama 特記仕様書 with `第1章` in cells).
- Section numbers missing from the text layer: some Digital Agency specs use Word auto-numbering for `1.1`-level headings, and the numbers are not in the text (doc `756d17c84006...`, `8a00ce8d8cae...`: ` 契約期間` with a leading space and no number). Their content stays under the last numbered heading.
- `記` appears in 32 documents, `以上` in only 8: many bodies end at the end of the file.

**DOC-3. Typical national 一般競争入札 notice sections.** **[verify]** order varies, but these are common:

| Section | Gloss | Fields inside |
|---|---|---|
| 1 調達内容 | Procurement details | 品目分類番号 (item category), 調達件名及び数量 (title and quantity), 調達件名の特質等 (specs, usually "per the specification"), 納入期限 / 履行期間, 納入場所 / 履行場所, 入札方法 |
| 2 競争参加資格 | Eligibility | legal disqualifications, 全省庁統一資格 grade and category, suspension status, other conditions |
| 3 入札書の提出場所等 | Where/when to submit | 契約条項を示す場所 (where contract terms are shown), 入札説明書の交付 (how to get bid instructions), 入札書の受領期限 (bid receipt deadline), 開札の日時及び場所 (bid opening time and place) |
| 4 その他 | Other | 契約手続において使用する言語及び通貨 (language and currency, usually Japanese and yen), 入札保証金及び契約保証金 (bid and performance bonds, often 免除 = waived), 入札の無効 (invalid bids), 落札者の決定方法 (award method), 契約書作成の要否 (whether a written contract is needed) |
| 5 Summary | English summary | Present on WTO-covered notices. **[verify]** useful as a free partial reference translation. Written `５ Summary` (p-portal HTML) or `14 Summary` (doc `2f2f5bd332965253...`, Wakayama PDF). Its sentences are marked `language` en and carry the Summary heading's section path only (D-37). |

**DOC-4. The document bundle.** One tender usually has several files:
- `入札公告` / `公示` (notice), 1 to 4 pages
- `入札説明書` (bid instructions), detailed procedures
- `仕様書` (specification), what is being bought, often the longest
- `評価項目一覧` / `評価基準書` (evaluation criteria, for comprehensive evaluation tenders)
- `契約書（案）` (draft contract)
- `様式` (forms)
Fields can live in any of these. The notice is the authority for dates; the spec is the authority for scope.

**DOC-5. 仕様書 sections you'll see.** `目的` (purpose), `概要` (overview), `業務内容` / `作業内容` (scope of work), `要件` (requirements: `機能要件` functional, `非機能要件` non-functional), `成果物` / `納品物` (deliverables), `作業体制` (team structure), `情報セキュリティ` (security), `再委託` (subcontracting), `秘密保持` (confidentiality), `契約不適合責任` (liability for non-conformity).

**DOC-6. Layout hazards.**
- Tables with merged cells, especially for schedules and eligibility grids
- Two-column pages
- Vertical text (縦書き) in some forms
- Page numbers like `- 3 -` or `3/12`
- Text drawn as images inside an otherwise text PDF (logos, stamps, sometimes whole tables)
- Fonts with no Unicode mapping: extraction returns garbage, treat that page as scanned. None found in the 322 corpus PDFs (no U+FFFD); the nearest case is TXT-14.
- Text drawn as vector outlines (no text layer, no image): 21 pages in 4 documents, all from "Microsoft: Print To PDF" (D-23). Classified `outlined`, need OCR.
- Pages with a text layer and large images that hold more text (engineering drawings with title blocks, maps, screenshots): 10 pages, classified `mixed`. Example: doc `69bb4a0580c8...` (Niigata, 図面), where the drawing's title block repeats on every page and is flagged as a header/footer.
- Vertical text comes in two forms. Solid: characters set close (gaps about 0.1 character), either a vertical font (wmode 1, doc `1cfb7dc75bbb...`, Asahikawa) or one character per fragment (resume-style labels like `生年月日`, doc `ac58cfb92021...`, Hachioji, page 19). These are joined into one line and flagged. Letter-spaced: gaps around 0.7 character (envelope example, doc `6b36d69abc0d...`, page 9). These stay one character per line, because table rows with one character per cell (`○` marks, doc `d97dc236d8fc...`; digits, doc `a0f13100504f...`) are 0.35 to 0.49 apart and must not be joined. **[verify]** that no field-bearing text is letter-spaced vertical.
- Pages rotated with /Rotate: 7 pages in 3 documents (Okayama, Niigata), all 90 degrees. Boxes are stored for the displayed page (D-29).
- Running headers are rare in this corpus: exact repeats at the page edge in only 6 documents (`＜別添２＞`, `（案）` "draft", table header rows on continuation pages). Page numbers are common: 100 documents. Form labels like `（様式１）` ... `（様式６）` sit at the same place on every page but differ, and must not be treated as headers.

---

## 5. Procurement vocabulary

Readings are included so Yasharth can learn them. English renderings here are the glossary the app uses; keep them consistent everywhere.

| Japanese | Reading | English in app | Notes |
|---|---|---|---|
| 入札公告 | にゅうさつこうこく | Bid notice | |
| 公示 | こうじ | Public notice | used for WTO-covered procurements |
| 調達 | ちょうたつ | Procurement | |
| 件名 | けんめい | Title | |
| 一般競争入札 | いっぱんきょうそうにゅうさつ | Open competitive bidding | |
| 指名競争入札 | しめいきょうそうにゅうさつ | Selective bidding | only invited bidders |
| 随意契約 | ずいいけいやく | Negotiated contract | no competition, or limited |
| 企画競争 | きかくきょうそう | Proposal competition | closest to an RFP |
| 公募 | こうぼ | Open call | |
| 総合評価落札方式 | そうごうひょうからくさつほうしき | Best-value award (price + technical score) | |
| 最低価格落札方式 | さいていかかくらくさつほうしき | Lowest-price award | |
| 落札者 | らくさつしゃ | Winning bidder | |
| 予定価格 | よていかかく | Ceiling price | usually undisclosed, see NUM-7 |
| 予算決算及び会計令 | よさんけっさんおよびかいけいれい | Order for Budgets, Settlement of Accounts and Accounting | often abbreviated 予決令 in the document itself |
| 関東・甲信越 | かんとう・こうしんえつ | Kanto-Koshinetsu | unified qualification region; also written 関東甲信越 |
| 東海・北陸 | とうかい・ほくりく | Tokai-Hokuriku | region; also 東海北陸 |
| 九州・沖縄 | きゅうしゅう・おきなわ | Kyushu-Okinawa | region; also 九州沖縄 |
| 北海道 / 東北 / 近畿 / 四国 | ほっかいどう / とうほく / きんき / しこく | Hokkaido / Tohoku / Kinki / Shikoku | regions |
| 入札説明書 | にゅうさつせつめいしょ | Bid instructions | |
| 仕様書 | しようしょ | Specification | |
| 提案書 | ていあんしょ | Proposal | |
| 競争参加資格 | きょうそうさんかしかく | Eligibility to bid | |
| 全省庁統一資格 | ぜんしょうちょうとういつしかく | Unified qualification (all ministries) | national registration with grade A to D, business category, region. Foreign firms need this too |
| 等級 | とうきゅう | Grade | A/B/C/D in the unified qualification |
| 営業品目 | えいぎょうひんもく | Business category | |
| 入札書 | にゅうさつしょ | Bid form | |
| 受領期限 | じゅりょうきげん | Receipt deadline | |
| 開札 | かいさつ | Bid opening | |
| 入札保証金 | にゅうさつほしょうきん | Bid bond | |
| 契約保証金 | けいやくほしょうきん | Performance bond | |
| 免除 | めんじょ | Waived | |
| 履行期間 | りこうきかん | Performance period | |
| 納入期限 | のうにゅうきげん | Delivery deadline | |
| 納入場所 / 履行場所 | のうにゅうばしょ / りこうばしょ | Delivery location / place of performance | |
| 支出負担行為担当官 | ししゅつふたんこういたんとうかん | Contracting officer | official title on national notices |
| 契約担当官 | けいやくたんとうかん | Contracting officer | |
| 入札説明会 | にゅうさつせつめいかい | Bidders' briefing | sometimes mandatory |
| 質問 / 質疑 | しつもん / しつぎ | Questions | look for a question deadline |
| 電子調達システム | でんしちょうたつシステム | E-procurement system (GEPS) | |
| 再度入札 | さいどにゅうさつ | Re-bid | |
| 指名停止 | しめいていし | Suspension from bidding | eligibility exclusion |
| 暴力団排除 | ぼうりょくだんはいじょ | Exclusion of organized crime groups | standard eligibility clause |
| 再委託 | さいいたく | Subcontracting | |
| 契約不適合責任 | けいやくふてきごうせきにん | Liability for non-conformity | |
| 成果物 | せいかぶつ | Deliverables | |
| 秘密保持 | ひみつほじ | Confidentiality | |
| 資料提供招請 | しりょうていきょうしょうせい | Request for information (RFI) | pre-tender |
| 意見招請 | いけんしょうせい | Request for comments on draft spec | pre-tender |
| オープンカウンター | | Open counter (quick quotation) | small procurements |
| 見積書 | みつもりしょ | Quotation | |
| 委任状 | いにんじょう | Power of attorney | |
| 甲 / 乙 | こう / おつ | Party A / Party B | in contracts; usually 甲 = client |
| 発注者 / 受注者 | はっちゅうしゃ / じゅちゅうしゃ | Client / Contractor | |
| 法務省 | ほうむしょう | Ministry of Justice | issuer name (D-91) |
| 厚生労働省 | こうせいろうどうしょう | Ministry of Health, Labour and Welfare | issuer name |
| 総務省 | そうむしょう | Ministry of Internal Affairs and Communications | issuer name |
| 内閣府 | ないかくふ | Cabinet Office | issuer name |
| 農林水産省 | のうりんすいさんしょう | Ministry of Agriculture, Forestry and Fisheries | issuer name |
| 国土交通省 | こくどこうつうしょう | Ministry of Land, Infrastructure, Transport and Tourism | issuer name |
| 気象庁 | きしょうちょう | Japan Meteorological Agency | issuer name |
| 出入国在留管理庁 | しゅつにゅうこくざいりゅうかんりちょう | Immigration Services Agency of Japan | issuer name |

The eight issuer names are shown on the Issuer card only when the whole extracted issuer is one of them (a bureau, a prefecture or any other body shows its Japanese). The list is closed: none is added without a decision.

The Ministry of Justice's standard legal term dictionary (see sources.md) is the reference when a term isn't here. Prefer its renderings for legal terms.

---

## 6. Phrasing that changes meaning

These are the patterns where a small model is most likely to get the meaning backwards. Each one needs prompt guidance and test cases.

**SEM-1. Obligation strength in specs.**
- `〜すること` = shall (requirement)
- `〜ものとする` = shall / is to
- `〜しなければならない` = must
- `〜できる` / `〜ことができる` = may
- `〜が望ましい` = desirable (optional, not a requirement)
- `原則として` = in principle (exceptions exist)
Mark requirements vs preferences separately in eligibility and spec fields.

**SEM-2. Inclusive vs exclusive bounds.**
- `以上` = or more (inclusive), `以下` = or less (inclusive)
- `超` / `を超える` = more than (exclusive), `未満` = less than (exclusive)
`3年以上` = 3 years or more. `100万円未満` = under 1 million yen.

**SEM-3. Negatively phrased eligibility.** Eligibility is often written as "persons who do NOT fall under the following":
`次の各号のいずれにも該当しない者であること` = "must be a person who falls under none of the following".
The listed items below are **disqualifications**, not requirements. Extracting them as requirements inverts the meaning. Detect the parent clause and carry its polarity to the child items.

**SEM-4. Provisos.** `ただし、〜` = "however, ..." introduces an exception to the previous sentence. Keep it attached to the clause it modifies.

**SEM-5. Layered "and" / "or".** Legal Japanese uses a hierarchy:
- `及び` joins smaller items, `並びに` joins bigger groups ("A及びB並びにC" = "(A and B) and C")
- `若しくは` joins smaller items, `又は` joins bigger groups ("A若しくはB又はC" = "(A or B) or C")
Matters for eligibility conditions with multiple branches.

**SEM-6. Exclusions and indifference.** `〜を除く` = excluding, `〜を問わない` = regardless of, `〜に限る` = limited to.

**SEM-7. Omitted subjects.** Japanese drops the subject constantly. In specs, the actor is usually the contractor (`受注者`), but clauses about the agency (`発注者`, `当省`, `本学`) also appear without a subject. When a field depends on who does something (who provides equipment, who bears costs), cite the sentence and don't guess the actor if it's not stated nearby.

**SEM-8. Reference phrases.** `別紙のとおり` / `別添` = "as per the attachment", `仕様書による` = "per the specification", `入札説明書による` = "per the bid instructions". When a notice field just points elsewhere, the field's value is in another document of the bundle. Mark it as `see_other_document` rather than `not_found` and record which document.

---

## 7. Rule -> module map

| Rules | Module |
|---|---|
| TXT-1 to TXT-5, TXT-8, TXT-14 to TXT-17 | normalize |
| TXT-18, DOC-6 (scanned, outlined) | ocr |
| TXT-6, DOC-1, DOC-2, DOC-3 (Summary) | segment, html_ingest |
| DOC-6 | ingest, extract_text, clean |
| NUM-*, DATE-* | value_normalize, verify |
| DOC-3, DOC-4, DOC-5 | locate (heading cues), field_schema.md |
| Section 5 | glossary |
| SEM-* | llm_extract prompts, verify, eval test cases |
