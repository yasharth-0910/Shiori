"""Shared collector steps, offline: dedupe, bundle limit, dry run, manifest checks."""

import io
import json
import zipfile
from pathlib import Path
from typing import TypedDict

import pytest
from pydantic import ValidationError

from collector import collect
from collector.collect import (
    Candidate,
    classify_doc_type,
    classify_page,
    clean_link_text,
    extract_pdfs,
    is_it_title,
    it_and_spec_first,
    parse_notice_date,
    run,
)
from collector.manifest import ManifestRow, read_bundles, read_rows

REPO_ROOT = Path(__file__).resolve().parent.parent
PDF_A = b"%PDF-1.7 a"
PDF_B = b"%PDF-1.7 b"


class FakeClient:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.fetched: list[str] = []

    def get_page(self, url: str) -> bytes:
        self.fetched.append(url)
        return self.files[url]

    def get_bytes(self, url: str) -> bytes:
        return self.get_page(url)


def cand(url: str, bundle: str, fmt: str = "pdf", title: str = "仕様書") -> Candidate:
    return Candidate.model_validate(
        {
            "url": url,
            "landing_url": "https://x.test/page",
            "issuer_org": "テスト市",
            "title_ja": title,
            "doc_type": classify_doc_type(title),
            "notice_date": None,
            "format": fmt,
            "bundle_id": bundle,
            "bundle_title": bundle,
            "license_note": "test",
            "license_class": "restricted",
        }
    )


class Paths(TypedDict):
    documents_path: Path
    bundles_path: Path
    raw_dir: Path


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Paths:
    # Fake PDFs have no pages; PyMuPDF is covered by the real run, not here.
    monkeypatch.setattr(collect, "page_info", lambda path: (3, "full"))
    return {
        "documents_path": tmp_path / "documents.jsonl",
        "bundles_path": tmp_path / "bundles.jsonl",
        "raw_dir": tmp_path / "raw",
    }


def test_same_bytes_under_two_urls_give_one_row(paths: Paths) -> None:
    client = FakeClient(
        {"https://x.test/a.pdf": PDF_A, "https://x.test/copy.pdf": PDF_A}
    )
    cands = [cand("https://x.test/a.pdf", "b1"), cand("https://x.test/copy.pdf", "b2")]
    run("t", cands, client, limit=10, dry_run=False, log=lambda _: None, **paths)
    rows = read_rows(paths["documents_path"])
    assert len(rows) == 1
    bundles = read_bundles(paths["bundles_path"])
    assert bundles["b1"].doc_ids == bundles["b2"].doc_ids == [rows[0].doc_id]


def test_url_already_in_manifest_is_not_downloaded_but_joins_bundle(
    paths: Paths,
) -> None:
    client = FakeClient({"https://x.test/a.pdf": PDF_A})
    run(
        "t",
        [cand("https://x.test/a.pdf", "b1")],
        client,
        10,
        False,
        lambda _: None,
        **paths,
    )
    client.fetched.clear()
    run(
        "t",
        [cand("https://x.test/a.pdf", "b9")],
        client,
        10,
        False,
        lambda _: None,
        **paths,
    )
    assert client.fetched == []
    assert len(read_rows(paths["documents_path"])) == 1
    assert set(read_bundles(paths["bundles_path"])) == {"b1", "b9"}


def test_limit_takes_whole_bundles_in_order(paths: Paths) -> None:
    files = {f"https://x.test/{i}.pdf": f"%PDF {i}".encode() for i in range(6)}
    cands = [cand(f"https://x.test/{i}.pdf", f"b{i // 2}") for i in range(6)]
    cands.append(
        cand("https://x.test/f.docx", "b0", fmt="docx")
    )  # skipped, not counted
    plan = run("t", cands, FakeClient(files), 5, False, lambda _: None, **paths)
    assert [b[0].bundle_id for b in plan.take] == ["b0", "b1"]
    assert [b[0].bundle_id for b in plan.later] == ["b2"]
    assert len(read_rows(paths["documents_path"])) == 4


def test_dry_run_writes_nothing(paths: Paths) -> None:
    client = FakeClient({})
    plan = run(
        "t",
        [cand("https://x.test/a.pdf", "b1")],
        client,
        10,
        True,
        lambda _: None,
        **paths,
    )
    assert len(plan.take) == 1
    assert client.fetched == []
    assert not any(
        paths[k].exists() for k in ("documents_path", "bundles_path", "raw_dir")
    )


def test_non_pdf_bytes_are_skipped(paths: Paths) -> None:
    client = FakeClient({"https://x.test/a.pdf": b"<html>error page</html>"})
    run(
        "t",
        [cand("https://x.test/a.pdf", "b1")],
        client,
        10,
        False,
        lambda _: None,
        **paths,
    )
    assert read_rows(paths["documents_path"]) == []


def locked_pdf() -> bytes:
    """A one-page PDF that needs an open password, like the Niigata file in
    bundle niigata_pref:r08tenpikannsouikeitaku12 (part E)."""
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner"
    )


def test_password_locked_pdf_is_skipped(paths: Paths) -> None:
    client = FakeClient({"https://x.test/a.pdf": locked_pdf()})
    run("t", [cand("https://x.test/a.pdf", "b1")], client, 10, False, print, **paths)
    assert read_rows(paths["documents_path"]) == []
    assert not list(paths["raw_dir"].rglob("*.pdf"))  # nothing written either


def test_html_notice_is_saved_without_pages(paths: Paths) -> None:
    page = "<html><body>公募公告</body></html>".encode()
    client = FakeClient({"https://x.test/page": page})
    cands = [cand("https://x.test/page", "b1", fmt="html", title="公募公告")]
    run("t", cands, client, 10, False, lambda _: None, **paths)
    (row,) = read_rows(paths["documents_path"])
    assert (row.format, row.doc_type, row.pages, row.text_layer) == (
        "html",
        "notice",
        None,
        None,
    )
    assert row.path.endswith(".html")
    assert Path(row.path).read_bytes() == page


def test_saved_row_gets_is_it_from_the_bundle_title(paths: Paths) -> None:
    client = FakeClient({"https://x.test/a.pdf": PDF_A, "https://x.test/b.pdf": PDF_B})
    cands = [
        cand("https://x.test/a.pdf", "会計システム更改"),
        cand("https://x.test/b.pdf", "庁舎清掃"),
    ]
    run("t", cands, client, 10, False, lambda _: None, **paths)
    assert [r.is_it for r in read_rows(paths["documents_path"])] == [True, False]


def test_committed_manifest_rows_are_valid() -> None:
    rows = read_rows(REPO_ROOT / "data/manifests/documents.jsonl")
    assert rows, "manifest is empty"
    assert {r.source: r.license_class for r in rows}.get("funabashi") == "restricted"


def test_row_with_bad_license_class_is_rejected() -> None:
    line = (
        (REPO_ROOT / "data/manifests/documents.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    data = json.loads(line) | {"license_class": "public"}
    with pytest.raises(ValidationError):
        ManifestRow.model_validate(data)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # Invented titles shaped like municipal tender attachments
        ("架空市図書予約システム導入業務仕様書", "spec"),
        (
            "架空市図書予約システム導入業務に関するプロポーザル実施要領",
            "bid_instructions",
        ),
        ("架空市図書予約システム導入業務事業者評価基準", "evaluation_criteria"),
        ("架空市図書予約システム導入業務に係る質問回答", "qa"),
        ("プロポーザル評価結果", "result"),
        ("【別記1】契約書（案）", "draft_contract"),
        ("様式1 参加申込書", "forms"),
        ("応募要領", "bid_instructions"),
        # digital 744a1fec-... and d0d9097f-... (公募 detail pages)
        ("申請書記載要領（新規）", "bid_instructions"),
        ("架空市営住宅管理システム評価項目及び配点（別紙4）", "evaluation_criteria"),
        # rules for the evaluation committee, not bid instructions
        ("評価委員会設置要領", "other"),
        # koriyama:183557, selection criteria for a proposal
        ("選定基準", "evaluation_criteria"),
        # hokkaido:267662, the ZIP member that serves as the spec [verify]
        ("【契約】02_業務処理要領", "spec"),
        ("別紙1 再委託承認申請書", "forms"),
        ("誓約書（様式2）", "forms"),
        # a form attached to the 実施要領
        (
            "架空市観光案内サイト構築及び運用保守業務に関するプロポーザル実施要領（第1号様式-質問票）",
            "forms",
        ),
    ],
)
def test_classify_doc_type(title: str, expected: str) -> None:
    assert classify_doc_type(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # qa. koriyama:154103, answers to bidders' questions
        ("質問回答書", "qa"),
        # asahikawa:d079752, Q&A posted on 2024-06-04
        ("質疑応答（令和6年6月4日更新）", "qa"),
        # asahikawa:d079752 ZIP: the blank forms, including the question form
        ("提出書類（参加表明書、企画提案書、質疑応答書）", "forms"),
        # result. koriyama:131705, okayama_pref:1058476, nara_city:270694
        ("入札結果表（公表用）", "result"),
        ("一般競争入札（条件付）結果", "result"),
        ("開札録", "result"),
    ],
)
def test_classify_doc_type_qa_and_result(title: str, expected: str) -> None:
    assert classify_doc_type(title) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # asahikawa:d078407, the text of the public call (the notice)
        ("(1)公募文", "notice"),
        # hokkaido:270635, criteria for deciding the winner of a 総合評価 tender
        ("02-3_落札者決定基準", "evaluation_criteria"),
        # koriyama:107265, a declaration the bidder fills in (spot check, part E)
        ("入札参加資格審査申請に係る申告調書", "forms"),
        # doc 0919784f6eb4 (Koriyama), a past-performance record form
        ("施行実績調書", "forms"),
        # docs 52bba5f9b15b and e8ca985baaa7 (Hokkaido), proposal instructions
        ("02-1_企画提案指示書", "bid_instructions"),
        ("02_企画提案指示書（衛星データ利活用実証事業）", "bid_instructions"),
    ],
)
def test_classify_doc_type_part_f_cues(title: str, expected: str) -> None:
    assert classify_doc_type(title) == expected


def test_is_it_uses_strict_cues_on_title_or_bundle_title() -> None:
    # p-portal: 構築 alone is not IT under D-27; システム in the bundle title is.
    assert not is_it_title("高松国税総合庁舎本館外10施設の昇降機設備保守業務")
    assert not is_it_title("令和８年度国境離島の合理的・効果的な状況把握手法構築業務")
    assert is_it_title("仕様書", "旭川市災害時緊急情報配信システム整備業務委託")


@pytest.mark.parametrize(
    ("title", "has_pdf_notice", "expected"),
    [
        # tender_page. okayama_pref:1057597, the PDF 入札公告 is the notice
        (
            "工業技術センター　LANシステム 賃貸借に係る"
            "一般競争入札（条件付）の実施について",
            True,
            "tender_page",
        ),
        # koriyama:188011: 結果 inside the tender's name is not a result page
        (
            "セーフコミュニティ市民意識調査結果データ作成業務委託に係る制限付一般競争入札について",
            True,
            "tender_page",
        ),
        # wakayama_pref:d00222518: a status tag; the page still holds the notice
        (
            "【審査結果掲載】和歌山県・市町村被災者生活支援システム構築業務委託に係る公募型プロポーザルの実施について",
            False,
            "notice",
        ),
        # result. nara_city:270694 and okayama_pref:1058476 only announce results
        (
            "介護認定審査会ペーパーレス化システムに係る一般競争入札の結果について",
            False,
            "result",
        ),
        (
            "岡山県高度防災情報ネットワーク整備事業被災状況監視システム整備業務に係る一般競争入札（条件付）結果の公表について",
            False,
            "result",
        ),
        # qa. nara_city:268651, answers to questions about an RFI
        (
            "校務教育系システム更改に係る情報提供依頼書（RFI）に関する質問への回答を公開します",
            False,
            "qa",
        ),
    ],
)
def test_classify_page(title: str, has_pdf_notice: bool, expected: str) -> None:
    assert classify_page(title, has_pdf_notice) == expected


def test_clean_link_text() -> None:
    assert clean_link_text(
        "3.架空市図書予約システム導入業務仕様書（ＰＤＦ形式486キロバイト）"
    ) == ("架空市図書予約システム導入業務仕様書")
    assert clean_link_text("仕様書（PDF／2,088KB）") == "仕様書"
    assert (
        clean_link_text("公告第999号 [PDFファイル／321KB]") == "公告第999号"
    )  # group B
    assert clean_link_text("関係書類 (ZIP 1.46MB)") == "関係書類"  # Hokkaido
    assert clean_link_text("1プロポーザル実施要領") == "プロポーザル実施要領"
    assert clean_link_text("2026年度 仕様書") == "2026年度 仕様書"


def test_parse_notice_date_uses_gregorian_year() -> None:
    assert str(parse_notice_date("公告日：令和8年（2026年）2月13日")) == "2026-02-13"
    assert parse_notice_date("令和8年5月13日") is None


def make_zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def make_cp932_zip(name: str, data: bytes) -> bytes:
    """A ZIP whose member name is raw CP932 bytes without the UTF-8 flag, as Japanese
    Windows tools write it. zipfile can't write that, so write an ASCII placeholder
    of the same byte length and swap the bytes in (names are not covered by the CRC).
    """
    raw = name.encode("cp932")
    placeholder = b"X" * (len(raw) - 4) + b".pdf"
    archive = make_zip({placeholder.decode(): data})
    assert archive.count(placeholder) == 2  # local header and central directory
    return archive.replace(placeholder, raw)


def test_zip_pdfs_get_rows_with_extracted_from(paths: Paths) -> None:
    archive = make_zip(
        {"docs/仕様書.pdf": PDF_A, "様式.docx": b"PK", "readme.txt": b"x"}
    )
    client = FakeClient({"https://x.test/all.zip": archive})
    cands = [cand("https://x.test/all.zip", "b1", fmt="zip", title="関連書類")]
    run("t", cands, client, 10, False, lambda _: None, **paths)
    rows = {r.format: r for r in read_rows(paths["documents_path"])}
    assert set(rows) == {"zip", "pdf"}  # docx and txt inside the ZIP are skipped
    pdf = rows["pdf"]
    assert pdf.extracted_from == rows["zip"].doc_id
    assert (pdf.title_ja, pdf.doc_type) == ("仕様書", "spec")
    assert pdf.url == "https://x.test/all.zip#docs/仕様書.pdf"
    # The ZIP keeps its row for provenance; only the PDF joins the bundle.
    assert read_bundles(paths["bundles_path"])["b1"].doc_ids == [pdf.doc_id]


def test_zip_member_names_in_cp932_are_decoded() -> None:
    archive = make_cp932_zip("架空市仕様書.pdf", PDF_A)
    assert [name for name, _ in extract_pdfs(archive, lambda _: None)] == [
        "架空市仕様書.pdf"
    ]


def test_zip_slip_members_are_skipped() -> None:
    archive = make_zip({"../../evil.pdf": PDF_A, "/abs.pdf": PDF_A, "ok.pdf": PDF_B})
    assert [name for name, _ in extract_pdfs(archive, lambda _: None)] == ["ok.pdf"]


def test_zip_over_size_limit_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collect, "MAX_ZIP_UNCOMPRESSED", 5)
    archive = make_zip({"a.pdf": PDF_A})  # 10 bytes uncompressed, over the limit of 5
    assert extract_pdfs(archive, lambda _: None) == []


def test_it_bundles_come_before_spec_bundles() -> None:
    cands = [
        cand("https://x.test/taxi.pdf", "タクシーの供給"),  # spec, not IT
        cand("https://x.test/plan.pdf", "システム調査", title="計画"),  # IT, no spec
        cand("https://x.test/dev.pdf", "システム開発"),  # IT with spec
    ]
    ordered = it_and_spec_first(cands, ("システム",))
    assert [c.bundle_id for c in ordered] == [
        "システム開発",
        "システム調査",
        "タクシーの供給",
    ]


def test_bundle_cap_counts_only_bundles_with_new_files(paths: Paths) -> None:
    files = {f"https://x.test/{i}.pdf": f"%PDF {i}".encode() for i in range(4)}
    client = FakeClient(files)
    run(
        "t",
        [cand("https://x.test/0.pdf", "b0")],
        client,
        99,
        False,
        lambda _: None,
        **paths,
    )
    cands = [cand(f"https://x.test/{i}.pdf", f"b{i}") for i in range(4)]
    plan = run("t", cands, client, 99, True, lambda _: None, max_bundles=2, **paths)
    # b0 is already collected, so it doesn't use up the cap of 2.
    assert [b[0].bundle_id for b in plan.take] == ["b0", "b1", "b2"]
    assert [b[0].bundle_id for b in plan.later] == ["b3"]


def test_candidate_split_follows_org_shares_and_balances_docs() -> None:
    from collector.report import candidate_split

    org_docs = {
        f"org{i:02d}": n for i, n in enumerate([50, 30, 20, 12, 10, 8, 6, 5, 4, 3])
    }
    split = candidate_split(org_docs)
    counts = {k: list(split.values()).count(k) for k in ("train", "dev", "test")}
    assert counts == {"train": 6, "dev": 2, "test": 2}
    assert split["org00"] == "train"  # the biggest org lands in train
    assert candidate_split(org_docs) == split  # deterministic
