# City and prefecture survey (Phase 1, part C)

Date: 2026-10-02. Goal: find local governments that add issuing organizations to the corpus, preferably with an `open` license (D-16) and some IT procurement.

How it was done: the collector's `PoliteClient` (our User-Agent, robots.txt checked, at most 1 request per 3 s per host), plus one plain GET of `/robots.txt` per surveyed host to record its rules. About 700 requests in total. Starting points were JETRO's core-city index (`links-local.html`; its links go through a translation proxy, so the real city URLs were taken out of the `url=` parameter and visited directly) and prefecture homepages.

Three steps:
1. **License screen of 108 governments** (all 42 prefectures not already checked, plus 66 core cities): homepage, then its copyright or site-policy page. Result: 58 reserve all rights, 46 had no terms link on the homepage or no clear wording ("unknown"), 3 open or partly open, 1 failed (Kishiwada: DNS error). Web search found a few more leads, each checked on the live site.
2. **Detailed survey of 25 governments** (the table below): a short crawl of up to 8 tender pages each, recording attachment URL patterns, file types and IT titles.
3. **Samples**: at most 2 PDFs per site, 27 in total, saved to `data/raw/_samples/<source>/` with manifest rows and the right `license_class`. Text layer checked with PyMuPDF.

No site returned 403 to our User-Agent. No login, form or CAPTCHA was touched.

## Results

"IT seen" lists IT titles found in the short crawl, not a full count. Tender counts are rough and come from listing pages.

| # | Government (region, type) | robots.txt | Terms -> license_class | How tenders are published | IT seen, rough volume | Layout group | Samples (text layer) |
|---|---|---|---|---|---|---|---|
| 1 | 北海道 (Hokkaido, prefecture) | 3 unrelated disallows | "原則、全てのページがオープンデータ", CC BY -> **open** | Central 契約マネジメントセンター list; each tender page has the 告示 (notice) as PDF and the rest as one 関係書類 ZIP. Documents disappear after bid opening; only results stay | RPA環境提供, デジタル活用人材育成研修. ~14 active consignment tenders | G (`/fs/1/3/.../_/`) | 告示 + ZIP (4 PDFs extracted), all `full` |
| 2 | 和歌山県 (Wakayama, prefecture) | none (404) | 和歌山県ホームページ公開情報利用規約, CC BY 4.0 compatible -> **open** | One all-tenders page (`whatsnew/nyusatsu.html`), one HTML page per tender with direct PDFs: 告示, 入札公告, 入札説明書, 仕様書, 契約条項 | 財務会計システム構築, 旅費システム構築, 庶務事務システム RFI, ウェブサイト制作. ~284 links, ~46 with IT words | A (`d<id>_d/fil/`) | 入札公告, 入札説明書, both `full` |
| 3 | 岡山県 (Okayama, prefecture) | none (404) | PDL1.0 for all content unless marked -> **open** | Category lists, including 入札公告（情報・通信サービス）; tender pages with 入札公告, 入札説明書, 仕様書 as PDFs, forms as docx, some ZIPs | 防災情報ネットワーク, 情報教室 電子計算組織, iPad管理ツール. Dozens active across ~10 categories | B (`/site/<n>/<id>.html` + `/uploaded/attachment|life/`) | 入札公告, 仕様書, both `full` |
| 4 | 大阪市 (Osaka, designated city) | none (404) | 政府標準利用規約-style rules, commercial use allowed -> **open** | Per-bureau category pages with long HTML notice text and no attachments. From July 2026 new notices are in a JavaScript system (`osaka.city.beneproc.com`, no links in its HTML), which is out of scope | デジタル統括室 has a listing; IT not checked further | H (`/<bureau>/page/<10 digits>.html`) | none (no files on the pages) |
| 5 | 福井市 (Fukui, core city) | none (404) | All rights reserved except content showing a CC mark -> restricted unless marked | 入札の広場 pages; tender documents not reached in the crawl | not seen | not identified | none |
| 6 | 倉敷市 (Kurashiki, core city) | **disallows all PDFs/xls under `/_res/projects/.../*.pdf`** | CC BY only for content showing a CC mark -> restricted unless marked | Tender pages with attached PDFs and docs | proposals seen, IT not seen | D (`/_res/projects/default_project/_page_/`) | none (robots.txt forbids the PDFs) |
| 7 | 旭川市 (Asahikawa, Hokkaido, core city) | 2 disallows (`/500/574/`, `/kanri/`) | No reuse or reproduction without permission -> restricted | Per-category lists; tender pages with 公示文 + 仕様書 PDFs | 人材マネジメントシステム構築. Open-counter notices weekly | A (`d<id>_d/fil/`) | 公示文, 仕様書, both `full` |
| 8 | 秋田市 (Akita, core city) | 1 unrelated disallow | Copyright belongs to the city, no reuse terms -> restricted | Notice pages; tender documents not reached in the crawl | not seen | D | none |
| 9 | 郡山市 (Koriyama, Fukushima, core city) | none (404) | No terms page found -> unknown | 入札・契約ポータル; proposal pages with 公告 + 実施要領 + 仕様書 PDFs | not seen in crawl; ふるさと納税 and 健康 proposals | B | 公告第215号, 仕様書, both `full` |
| 10 | 川口市 (Kawaguchi, Saitama, core city) | none (404) | Terms page found but wording not conclusive -> unknown | Contract division pages: open counter lists with one 仕様書 PDF per item, proposal pages | 電子契約サービス proposal | C (`/material/files/group/`) | 試行要領, 仕様書, both `full` |
| 11 | 八王子市 (Hachioji, Tokyo, core city) | 684 disallows (recruitment pages), tender pages allowed | No use, reproduction or republication without permission -> restricted | Monthly 公告案件一覧表 PDFs (lists of notices); proposal index page | not seen | A (`p<id>_d/fil/`, same CMS as Funabashi) | 公告案件一覧表, `full` |
| 12 | 横須賀市 (Yokosuka, Kanagawa, core city) | 2 unrelated disallows | No reproduction without permission -> restricted | Proposal pages per department with 募集要領 + 仕様書 PDFs; 工事/物品 on かながわ電子入札共同システム | オフィス・スマート化, カメラ式駐車場導入. Many proposals | E (`/documents/`) | 募集要領, 仕様書, both `full` |
| 13 | 富山市 (Toyama, core city) | 3 cgi disallows | about page has no copyright wording -> unknown | Notice pages, proposal list page | not seen | D | 市有財産売り払い募集要領: **`none`**, see below |
| 14 | 金沢市 (Kanazawa, core city) | 1 unrelated disallow | No reproduction or reuse without permission -> restricted | Department pages with 公告文 + 仕様書 PDFs (some 17 MB) | 1 IT title | C | 2 公告文, both `full` |
| 15 | 長野市 (Nagano, core city) | none (404) | No reproduction without permission -> restricted | Tenders in 電子入札・入札情報システム; site only has guides | not seen on the site | E | none (only guides on the site) |
| 16 | 豊田市 (Toyota, Aichi, core city) | 2 cgi disallows | Copyright belongs to the city, quotes need permission -> restricted | Proposal and tender index pages; documents not reached in 8 pages | not seen | D-like (`/<n>/index.html`) | none |
| 17 | 豊中市 (Toyonaka, Osaka, core city) | none (404) | No reproduction without permission -> restricted | Index pages; documents not reached in 8 pages | not seen | F (`.files/`) | none |
| 18 | 奈良市 (Nara, core city) | none (404) | No reproduction without permission -> restricted | Department pages with 入札公告 + 仕様書 PDFs, forms as .doc | 介護認定審査会ペーパーレス化システム, 保育ICTシステム | B | 入札公告, 仕様書, both `full` |
| 19 | 松江市 (Matsue, Shimane, core city) | none (404) | No use or reproduction without permission -> restricted | Tenders in 島根県電子調達共同利用システム; the site posts monthly case-list PDFs | 2 IT mentions | C | 見積案件情報 list, `full` |
| 20 | 高松市 (Takamatsu, Kagawa, core city) | none (404) | No reuse or quotation without permission -> restricted | Proposal guideline and index; documents not reached | not seen | F | none |
| 21 | 高知市 (Kochi, core city) | none (404) | No terms page found -> unknown | Proposal index (学校情報通信ネットワーク整備); documents not reached in 8 pages; 電子入札・入札情報システム | 学校情報通信ネットワーク環境 | B-like (`/life/<n>/<n>/`) | none |
| 22 | 鹿児島市 (Kagoshima, core city) | 1 unrelated disallow | No reuse without permission -> restricted | 発注情報 pages, forms PDFs; 電子入札 | 学校事務用端末リース | E | 入札書 form, `full` |
| 23 | 那覇市 (Naha, Okinawa, core city) | 3 unrelated disallows | No use or reproduction without permission -> restricted | Year-by-year index pages; documents not reached in 8 pages | 1 IT mention | D-like | none |
| 24 | 新潟県 (Niigata, prefecture) | none (404) | No reproduction without permission -> restricted | Office-by-office pages with 入札公告 + 仕様書 PDFs | 1 IT mention | B | 入札公告, 仕様書, both `full` |
| 25 | 滋賀県 (Shiga, prefecture) | 1 unrelated disallow | Private copying only, unless a page says otherwise -> restricted | Tender pages not reached; crawl ended in 募集 (calls) pages | not seen | E (`/documents/<n>/`) | none |

Also checked, not in the table: 札幌市 and 世田谷区 (restricted), 宇都宮市 (TLS certificate expired, not fetched), 盛岡市 and 枚方市 (JETRO links 404; Morioka restricted), 古河市 (a small city whose open-data rules cover "当ホームページ", but whose site copyright page reserves rights, so unknown), うるま市 and 河内長野市 (CC BY or 政府標準 rules, but only for their open-data catalogs, so restricted for tender files).

## License findings

- **Open local governments are rare.** Of about 130 checked, 4 are clearly open for all site content: 北海道 (CC BY), 和歌山県 (CC BY 4.0 compatible rules), 岡山県 (PDL1.0), 大阪市 (政府標準利用規約-style rules). Two more (福井市, 倉敷市) apply CC BY only to content marked with a CC icon, and tender PDFs are not marked.
- Most "unknown" results in the screen are sites whose homepage links no terms page. Every unknown that was followed up turned out to be restricted, so unknown -> restricted (D-16) is the right default.
- **Outside this survey's scope, but promising:** national regional branch offices state PDL1.0 for their whole sites. Checked: 近畿地方整備局 (`www.kkr.mlit.go.jp/link.html`). Search results show the same for other MLIT and labour-bureau sites. Each regional bureau is its own issuing organization (its own 支出負担行為担当官). But Kinki's 物品・役務 notice page holds mostly an xlsx list, and construction notices go through PPI and GEPS, so whether they post usable PDFs needs its own survey.

## Layout groups

Grouped by how attachments and tender pages are addressed. One adapter per group could cover several governments, with only the listing URL changing.

| Group | Fingerprint | Members (license) | Notes |
|---|---|---|---|
| A | tender page `p<id>.html` or `d<id>.html`, files under `<page>_d/fil/` | 船橋市 (restricted, existing adapter), **和歌山県 (open)**, 旭川市 (restricted), 八王子市 (restricted) | The Funabashi adapter's parsing (link to `_d/fil/`, dedupe, clean titles) carries over. The listing pages differ per site |
| B | pages under `/site/<n>/` or `/life/<n>/<n>/`, files under `/uploaded/attachment/<n>.pdf` or `/uploaded/life/<n>_<n>_misc.pdf` | **岡山県 (open)**, 郡山市 (unknown), 奈良市 (restricted), 新潟県 (restricted); 高知市, 鳥取市 and 上越市 have the same page paths | Link text carries the file type and size (`入札公告 [PDFファイル／193KB]`), which `clean_link_text` already strips |
| C | files under `/material/files/group/<n>/` | 川口市, 金沢市, 松江市 (all restricted), 古河市 (unknown) | |
| D | files under `/_res/projects/default_project/_page_/001/...` | 倉敷市 (robots.txt forbids the PDFs), 秋田市, 富山市 (restricted/unknown); 豊田市 and 那覇市 have similar page paths | Kurashiki shows a site can block attachments for bots even when the pages are crawlable |
| E | files under `<page dir>/documents/` | 横須賀市, 長野市, 鹿児島市, 滋賀県 (all restricted) | Loose pattern. These may be several different CMSes |
| F | files under `<page>.files/` | 豊中市, 高松市 (restricted) | |
| G | `/fs/1/3/2/.../_/<name>.pdf` | **北海道 (open)** | One site only. Uses ZIPs for everything except the notice |
| H | `/<bureau>/page/<10 digits>.html`, `/category/<n>-<n>-...html`, `cmsfiles/contents/` | **大阪市 (open)**; JETRO lists 八尾市, 東大阪市 and 姫路市 with the same category URLs | Osaka City notices are HTML only |

## Scanned PDFs

None of the 27 samples is a raster scan. Together with the 62 earlier PDFs that makes 0 of 89.

One sample has no text layer at all: 富山市's 市有財産売り払い募集要領 (doc `7c76af66d35dec3e4a82f4a7ef985809119e2d6230641c9a57dd99fc68e4a5e6`, 11 pages, producer "Microsoft: Print To PDF"). It has **no images either**: the text is drawn as vector outlines (about 36,000 path segments on page 1). For the pipeline it behaves like a scan and needs OCR, but an image-count check would not flag it. Noted in `docs/modules.md` (ingest).

Every office in this survey publishes Word or Excel exports. Scans will not turn up by sampling current tenders; the 15 needed will have to come from a targeted search. Possible places: older archives (平成-era notices), result sheets with seals, small towns, or files picked by hand.

## Other findings for the pipeline

- New Japanese text rules and evidence: TXT-9 counterexample (Yokosuka, `５ １次選考`), TXT-11 narrowed, TXT-12 (外字 as Private Use Area characters, Nara City `都祁`). See `docs/japanese_rules.md`.
- The first real ZIP (Hokkaido, 19 members) worked with the D-21 code: 4 PDFs extracted, 10 docx and 3 folder entries skipped. Its member names carried the UTF-8 flag, so the CP932 name path is still tested only offline.
- Hokkaido's spec equivalent is called 業務処理要領 ("work handling procedure"). The doc_type cues file it as `bid_instructions`. I'm not sure that's right (see open questions in `docs/decisions.md`).

## Proposal: next adapters

Ranked by open-license organizations added, with IT content as a tiebreak. None is built yet.

1. **`wakayama_pref` (group A).** Open, one listing page with ~284 tender links and ~46 IT titles (system builds and RFIs), direct PDFs for notice, instructions and spec. Build it by generalizing the Funabashi adapter into a group-A parser configured per site (listing URL, link regex), which also makes 旭川市 and 八王子市 cheap to add later as restricted orgs.
2. **`okayama_pref` (group B).** Open (PDL1.0), full bundles (入札公告 + 入札説明書 + 仕様書) as PDFs, a dedicated IT category. The same parser covers 郡山市, 奈良市 and 新潟県 (restricted) with a config change.
3. **`hokkaido` (group G).** Open (CC BY), IT tenders present, but the bundle is notice PDF + ZIP, and documents are removed after bid opening. So it only pays off if the collector is run every few weeks. ZIP extraction (D-21) is ready for it.
4. **`osaka_city` (group H, html only).** Open, but notices are HTML text with no attachments, like p-portal (D-18). Lower value per document; worth it mainly as one more open org for the test split.
5. **Survey, not an adapter yet: MLIT regional bureaus.** If they post notice PDFs on their own sites, one adapter could add up to ~9 open organizations, more than all local governments found here.

Org count: the corpus now has 17 issuing organizations (survey samples included), but only 5 of them are open (デジタル庁, 気象衛星センター, 北海道, 和歌山県, 岡山県); 大阪市 would be the sixth once collected. Since only open documents can be published (D-16), the test split should probably be drawn from open organizations. Adapters 1 to 4 would give 6 open orgs with real volume, which is tight for a ~20% test share. That's why item 5 matters.
