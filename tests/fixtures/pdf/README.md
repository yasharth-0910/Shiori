# PDF fixtures

Pages cut from collected documents whose `license_class` is `open` (D-22), so they may
be committed. Cut with PyMuPDF `insert_pdf` and saved with `garbage=4, deflate=True`;
only the producer field is kept in the metadata. Licenses as recorded in
`data/manifests/documents.jsonl`. Attribution: the issuing organization named per row.

| file | doc_id | source pages | license | covers |
|---|---|---|---|---|
| `digital_text.pdf` | `2a4dacf5624b6341f80d80993d33bdc141a6b6c1f8777b444ac5a8c6ad9a655d` | 3, 22 | Digital Agency, PDL1.0 | normal text page, real spaces in `令和 2 年 12 月 25 日` (TXT-9), PUA bullets U+F09F (TXT-11), page numbers |
| `wakayama_table.pdf` | `0caedcbd73553be4aa2fd5b4d554a743798b04663ef2ff1af85258e886ad7915` | 1 | Wakayama Prefecture, site terms (CC BY 4.0 compatible) | table page (evaluation items and points) |
| `jma_spaced_digits.pdf` | `209ff2190e47b6d02169d1d985f8e1c3f04354a4166ec42d45e2e8a626800a4f` | 1 | JMA, PDL1.0 | TXT-9 `1 6 日` case |
| `wakayama_paren_numbers.pdf` | `0f7b9667dcd5826bbc24418d68fcf3931b9d80d17fbc178330366bb838fa5ae4` | 6 | Wakayama Prefecture, site terms (CC BY 4.0 compatible) | `⑴ ⑵ ⑶` at line starts (TXT-13) |
| `okayama_scanned.pdf` | `7fb45ac7dec4a28fe8a308b3592213b6c51c860463e9e84aa6028da5a464cf09` | 1 | Okayama Prefecture, PDL1.0 | scanned page (image only, D-23) |
| `okayama_rotated_vertical.pdf` | `6b36d69abc0d311de1b79374fdbd2947508cd13a4ba0ea015e06cb8452177685` | 6, 9 | Okayama Prefecture, PDL1.0 | page with /Rotate 90; stacked vertical text with mis-mapped vertical-form glyphs |
| `jma_notice.pdf` | `2aa7506afc0882cdbe20dfe37fd643ab19099247fc0450613da07c427a81973c` | 2, 3, 4, 5 | JMA, PDL1.0 | national notice numbering `1` / `(1)`, sentences across page breaks, tax clause (NUM-6) |
| `jma_split_line.pdf` | `209ff2190e47b6d02169d1d985f8e1c3f04354a4166ec42d45e2e8a626800a4f` | 4 | JMA, PDL1.0 | one visual line extracted as two lines (`（令和８年３月` / `31日付官報）`) |
| `wakayama_contract.pdf` | `0f7b9667dcd5826bbc24418d68fcf3931b9d80d17fbc178330366bb838fa5ae4` | 1 | Wakayama Prefecture, site terms (CC BY 4.0 compatible) | contract `第N条`, unnumbered first paragraph then `２` `３`, `⑴` items, blank form amounts |
| `okayama_table_spec.pdf` | `3fc2a22e507dba9e6954e2adcb64bd58a1554a08e4fd7ee21b8cf2378dc6929b` | 2, 3, 4, 5 | Okayama Prefecture, PDL1.0 | spec laid out as a table numbered `1.` / `1.1` in cells; table header row repeated on every page (D-30) |
| `digital_draft_header.pdf` | `75a0c52799f9c6659d339437fe7e760aabca72e83835e827e88c9926e7e3557f` | 1, 2, 3 | Digital Agency, PDL1.0 | `（案）` header on every page (D-30), `第1章` / `第N条` |
| `hokkaido_notice.pdf` | `fb226cbdd14be7ca28cb17e8eb71e8695cbcb12c6df77b88c7fd8d6f59660354` | 2 | Hokkaido, CC BY | local notice numbering; a one-row phantom table around a heading (D-31) |
| `wakayama_qa_table.pdf` | `3f8e4597411756d463e647ad24f4a1522a61d983e393c3b3b9b94164c52d4a58` | 1 | Wakayama Prefecture, site terms (CC BY 4.0 compatible) | Q&A table whose cells come out of the PDF interleaved |
| `wakayama_summary.pdf` | `2f2f5bd332965253eed43d739e56e7859b149afa0d157ea3c89dfdd7d0d8b419` | 1 to 4 (whole notice) | Wakayama Prefecture, site terms (CC BY 4.0 compatible) | WTO notice with an English Summary (`14 Summary`): English sentences and their section path, wrapped English lines (`andlease`, unclosed bracket, `JapanTEL`), `FAX` / `e-mail` label lines (D-37) |
| `hokkaido_bid_notice.pdf` | `fb226cbdd14be7ca28cb17e8eb71e8695cbcb12c6df77b88c7fd8d6f59660354` | 1, 3 (cut pages are `p1` and `p2`) | Hokkaido, CC BY | bid date and time `(2) 入札日時` (D-34 answer, weekday checks), `委託業務処理要領による`, fused heading and body `(10)入札の取りやめ又は延期この入札は…` (known limitation) |
