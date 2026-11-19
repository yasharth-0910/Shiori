# ruff: noqa: E501
"""Rules-only field extractor (Phase 4): heading cues, the value converters and
sentence ids. No model, no network. Not found is better than a wrong answer, so every
rule answers only when its wording is plain, and an answer that cannot be tied to its
cited sentences is dropped.

    found = extract(doc_type, sentences)   # {field: Extracted}; a missing key = not found

Every rule works on `text_norm` (normalize.py) and quotes `text_orig` through the offset
map, so `value_ja` is the original wording. A rule that finds two different answers in
one document answers nothing. Fields covered: notice_date, procurement_type, bid_bond,
performance_bond, tax_basis, unified_qualification, language_currency, wto_covered, and
(v4) award_method, spec_access, submission_modes, delivery_deadline, performance_period,
contracting_officer, and title and issuer_org (D-89). A pointer such as 仕様書のとおり is answered as see_other_document
(normalized {"ref": {...}}), the same way a label writes it.
"""

import re
from collections.abc import Callable, Iterator

from pydantic import BaseModel, ValidationError

from shiori_core.fields import BY_ID, SeeOtherRef, validate_normalized
from shiori_core.models import Sentence
from shiori_core.normalize import normalize
from shiori_core.value_normalize import find_dates, find_tax_basis


class Extracted(BaseModel):
    field: str
    value_ja: str  # the original wording, one line per sentence it spans
    normalized: dict
    citations: list[str]
    status: str = "present"  # or see_other_document, when normalized is {"ref": ...}


Hit = tuple[dict, str, list[str]]  # normalized, value_ja, sentence ids


class Joined:
    """Consecutive sentences read as one text (a sentence can end mid-phrase, so a cue
    and its value may sit in two of them). `cut` gives the original wording of a span of
    the joined normalized text and the ids of the sentences it touches."""

    def __init__(self, sents: list[Sentence]) -> None:
        self.sents = sents
        self.text = "".join(s.text_norm for s in sents)
        self.starts = [0]
        for s in sents:
            self.starts.append(self.starts[-1] + len(s.text_norm))

    def cut(self, a: int, b: int) -> tuple[str, list[str]]:
        parts, ids = [], []
        for k, s in enumerate(self.sents):
            lo, hi = max(a, self.starts[k]), min(b, self.starts[k + 1])
            if lo < hi:
                m = s.norm_to_orig
                parts.append(
                    s.text_orig[m[lo - self.starts[k]] : m[hi - 1 - self.starts[k]] + 1]
                )
                ids.append(s.id)
        return "\n".join(parts), ids


def windows(ss: list[Sentence]) -> Iterator[tuple[int, Joined, int]]:
    """(index, this sentence and the next read as one text, length of the first): a
    match that starts in the first part is reported once."""
    for i, s in enumerate(ss):
        yield i, Joined(ss[i : i + 2]), len(s.text_norm)


def one(hits: list[Hit]) -> Hit | None:
    """The first hit when every hit says the same, else nothing."""
    if hits and all(h[0] == hits[0][0] for h in hits):
        return hits[0]
    return None


# --- notice_date -------------------------------------------------------------------------

# Who signs a national notice. The notice date is the line of its own just above.
OFFICER = re.compile(r"支出負担行為担当官|契約担当官|契約責任者")


def notice_date(ss: list[Sentence]) -> Hit | None:
    """A sentence that is a date and nothing else, with an officer's title in one of the
    next three sentences (guide: "before the officer's name"). A portal date under its
    own label (公開開始日 and the like) has a short label sentence above it: not it."""
    hits: list[Hit] = []
    for i, s in enumerate(ss):
        t = s.text_norm.strip()
        ds = find_dates(t)
        if len(ds) != 1 or ds[0].value is None or ds[0].warning or ds[0].text != t:
            continue
        before = ss[i - 1].text_norm.strip() if i else ""
        if len(before) <= 12 and re.search(r"[日時間限]$", before):
            continue
        if any(OFFICER.search(x.text_norm) for x in ss[i + 1 : i + 4]):
            hits.append(
                ({"date": ds[0].value.isoformat()}, s.text_orig.strip(), [s.id])
            )
    return one(hits)


# --- procurement_type --------------------------------------------------------------------

TYPES = [
    ("open_competitive", re.compile(r"一般競争入札(?:に付|の入札公告|公告|を実施|により)")),
    ("designated_competitive", re.compile(r"指名競争入札(?:に付|の入札公告|公告|を実施|により|通知)")),
    ("proposal_competition", re.compile(r"公募型プロポーザル|プロポーザル方式|企画競争(?:に|を|の|により)")),
    ("open_counter", re.compile(r"オープンカウンター方式")),
]  # fmt: skip


def procurement_type(ss: list[Sentence]) -> Hit | None:
    """One type named in the document, by its plain wording (一般競争入札に付します,
    公募型プロポーザル, ...). Two different types: nothing. 公募 alone and 随意契約 have too
    many other uses to answer from."""
    hits: list[tuple[str, Hit]] = []
    for s in ss:
        for name, pat in TYPES:
            if m := pat.search(s.text_norm):
                j = Joined([s])
                q, ids = j.cut(m.start(), m.end())
                hits.append((name, ({"type": name}, q, ids)))
    if len({n for n, _ in hits}) != 1:
        return None
    # A statement (ends with 。) beats a title line that only names the procedure.
    return next((h for _, h in hits if h[1] and sentence_ends(h[2][0], ss)), hits[0][1])


def sentence_ends(sid: str, ss: list[Sentence]) -> bool:
    return any(s.id == sid and s.text_orig.rstrip().endswith("。") for s in ss)


# --- bid_bond, performance_bond ----------------------------------------------------------

_TAIL = re.compile(r"^(?:(?:及び|並びに|又は|、|・)(?:契約|入札)保証金|の?納付|の?額|について|に関する(?:事項|こと)|[\s:：\-ー・（）()])*")  # fmt: skip
_WAIVED = re.compile(r"^免除(?:す?る|とする|します)?[。.]?$")
_RATE = re.compile(r"100分の(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:%|パーセント)")


def bond(ss: list[Sentence], cue: str) -> Hit | None:
    """`入札保証金及び契約保証金　免除` (the value in the same sentence or alone in a
    short one below) is waived; a percentage of the price to be paid in (契約金額の100分
    の10以上を契約保証金として納付) is required with that rate. Anything with a
    condition (ただし, 場合) says neither."""
    hits: list[Hit] = []
    for i, s in enumerate(ss):
        t = s.text_norm
        for m in re.finditer(cue, t):
            rest = t[m.end() :][_TAIL.match(t[m.end() :]).end() :]  # type: ignore[union-attr]
            end, nxt = len(t), ss[i + 1 : i + 2]
            if not rest.strip(" 　。.:：") and nxt and len(nxt[0].text_norm) <= 30:
                rest, end = nxt[0].text_norm, len(t) + len(nxt[0].text_norm)
            if _WAIVED.match(rest.strip()):
                q, ids = Joined([s, *nxt]).cut(m.start(), end)
                hits.append(({"status": "waived", "rate_percent": None}, q, ids))
                continue
            rates = {a or b for a, b in _RATE.findall(t)}
            if len(rates) == 1 and "免除" not in t and re.search(r"以上|納付|相当", t):
                q, ids = Joined([s]).cut(0, len(t))
                hits.append(
                    ({"status": "required", "rate_percent": float(rates.pop())}, q, ids)
                )
    return one(hits)


def bid_bond(ss: list[Sentence]) -> Hit | None:
    return bond(ss, "入札保証金")


def performance_bond(ss: list[Sentence]) -> Hit | None:
    return bond(ss, "契約保証金")


# --- tax_basis ---------------------------------------------------------------------------

BASIS = {"tax_included": "bid_includes_tax", "tax_excluded": "bid_excludes_tax"}


def tax_basis(ss: list[Sentence]) -> Hit | None:
    """The converter's tax wording (NUM-6): the award clause that adds 10% to the bid,
    消費税を含む and so on. Two readings in one document: nothing."""
    hits: list[Hit] = []
    for _, j, n in windows(ss):
        for f in find_tax_basis(j.text):
            if f.start < n:
                q, ids = j.cut(f.start, f.end)
                hits.append(({"basis": BASIS[str(f.value)]}, q, ids))
    return one(hits)


# --- unified_qualification ---------------------------------------------------------------

_UQ = re.compile(r"全省庁統一資格\)?")
_CATEGORY = re.compile(
    r"[^「」。]{0,8}?(「[^「」]+」(?:(?:、|又は|若しくは|及び)「[^「」]+」)*)"
)
_GRADES = re.compile(r"((?:「?[A-D]」?(?:、|又は|若しくは|及び)?)+)の?等級")


def unified_qualification(ss: list[Sentence]) -> Hit | None:
    """`全省庁統一資格「役務の提供等」においてＡ又はＢの等級`: the business category in
    corner brackets, then the grades. Both must be there; the region is left out."""
    hits: list[Hit] = []
    for _, j, n in windows(ss):
        for m in _UQ.finditer(j.text):
            if m.start() >= n:
                continue
            rest = j.text[m.end() :]
            c = _CATEGORY.match(rest)
            g = _GRADES.search(rest, c.end(), c.end() + 60) if c else None
            if c and g:
                grades = sorted(set(re.findall("[A-D]", g.group(1))))
                q, ids = j.cut(m.start(), m.end() + g.end())
                hits.append(
                    ({"grades": grades, "category": c.group(1), "region": None}, q, ids)
                )
    return one(hits)


# --- language_currency -------------------------------------------------------------------

_LANG = re.compile(
    r"日本語(?:及び|と)日本(?:国通貨|円)|言語は日本語[^。]{0,10}通貨は日本(?:国通貨|円)"
)


def language_currency(ss: list[Sentence]) -> Hit | None:
    """Japanese and yen, said in one phrase (日本語及び日本国通貨). Nothing else is
    answered: a document that allows English gets no answer."""
    hits: list[Hit] = []
    for s in ss:
        if (m := _LANG.search(s.text_norm)) and not re.search(
            r"英語|外国", s.text_norm
        ):
            q, ids = Joined([s]).cut(m.start(), m.end())
            hits.append(({"language": "ja", "currency": "JPY"}, q, ids))
    return one(hits)


# --- wto_covered -------------------------------------------------------------------------

_WTO = re.compile(r"WTO対象(外)?")


def wto_covered(ss: list[Sentence]) -> Hit | None:
    """The portal's heading mark `（WTO対象）` or `（WTO対象外）`."""
    hits: list[Hit] = []
    for s in ss:
        if m := _WTO.search(s.text_norm):
            q, ids = Joined([s]).cut(m.start(), m.end())
            hits.append(({"covered": m.group(1) is None}, q, ids))
    return one(hits)


# --- v4: headed values, pointers ---------------------------------------------------------

_NUM = re.compile(r"^[\s(（]*(?:[0-9一二三四五六七八九十]{1,2}[)）.．、]?\s*)?")


def headed(ss: list[Sentence], heading: str) -> Iterator[tuple[str, str, list[str]]]:
    """(value in normalized text, value in the original wording, sentence ids) for every
    `(4) 履行期間　<value>` line, numbering allowed. When the heading stands alone in a
    short sentence, the value is the next sentence (both are cited)."""
    head = re.compile(heading)
    for i, s in enumerate(ss):
        t = s.text_norm
        n = _NUM.match(t)
        m = head.match(t, n.end()) if n else None
        if not m:
            continue
        rest = t[m.end() :].lstrip(" :：")
        if rest.strip():
            q, ids = Joined([s]).cut(len(t) - len(rest), len(t))
            yield rest.strip(), q.strip(), ids
        elif len(t) <= 20 and i + 1 < len(ss):
            nxt = ss[i + 1]
            yield nxt.text_norm.strip(), nxt.text_orig.strip(), [s.id, nxt.id]


_POINTER = re.compile(r"(?:別途|別紙)?「?(入札説明書|仕様書)」?(?:のとおり|による)。?")
_KIND = {"入札説明書": "bid_instructions", "仕様書": "spec"}


def pointer(value: str, orig: str) -> dict | None:
    """`仕様書のとおり。` / `入札説明書による。` and nothing else. Two documents named
    (入札説明書及び仕様書による) fit no single kind: nothing."""
    if m := _POINTER.fullmatch(value):
        return {"ref": {"kind": _KIND[m.group(1)], "text_ja": orig}}
    return None


# --- award_method ------------------------------------------------------------------------

_BEST = re.compile(r"総合評価落札方式(?:をもって|による)|総合評価の方法をもって")
_LOWEST = re.compile(r"最低価格をもって[^。]{0,20}落札者")


def award_method(ss: list[Sentence]) -> Hit | None:
    """総合評価落札方式をもって行う is best_value, 最低価格をもって…落札者とする is
    lowest_price. 総合評価のための書類 alone says neither. Both in one document: nothing."""
    hits: list[Hit] = []
    for _, j, n in windows(ss):
        for pat, method in ((_BEST, "best_value"), (_LOWEST, "lowest_price")):
            for m in pat.finditer(j.text):
                if m.start() < n:
                    q, ids = j.cut(m.start(), m.end())
                    hits.append(({"method": method}, q, ids))
    return one(hits)


# --- spec_access -------------------------------------------------------------------------

_PUBLIC = re.compile(r"(?:本公告の日から原則、?)?「?電子調達システム」?(?:にて|に)(?:公告日より)?(?:交付|掲載)する。?")  # fmt: skip
_COUNTER = re.compile(r"本公告の日から(?:上記\(\d\)の)?場所にて交付する。?")


def spec_access(ss: list[Sentence]) -> Hit | None:
    """How the bid documents are handed out, from the 入札説明書の交付方法 line: on the
    electronic system (public) or at the place named above (at_counter). A line of that
    heading that says anything else answers nothing, and then so does the 仕様 pointer.
    Without such a line, `(3) 仕様等　入札説明書による。` is see_other_document."""
    given = list(headed(ss, r"(?:入札説明書|仕様書)の交付方法"))
    if given:
        modes = []
        for v, q, ids in given:
            mode = "public" if _PUBLIC.fullmatch(v) else "at_counter" if _COUNTER.fullmatch(v) else None  # fmt: skip
            modes.append(({"mode": mode}, q, ids))
        return one(modes) if modes[0][0]["mode"] else None
    hits = [(p, q, ids) for v, q, ids in headed(ss, r"(?:調達案件の)?仕\s*様等?(?!書)") if (p := pointer(v, q))]  # fmt: skip
    return one(hits)


# --- submission_modes --------------------------------------------------------------------

_E_CUE = re.compile(r"電子(?:調達システム|入札)")
_E_VERB = re.compile(r"で行う|を利用して行う|を利用することができる|を利用した|利用対象|対象調達案件|対象案件|方式対象|システムによるが|システムによる。")  # fmt: skip
_E_NOT = re.compile(r"により難い|によりがたい|交付|掲載|電子契約")
_PAPER = re.compile(r"紙入札|紙による従来の応札")
_P_CUE = re.compile(r"直接持参する方法|持参又は郵(?:送|便)|郵(?:送|便)又は持参")
_M_CUE = re.compile(r"郵送による|郵送の場合|郵送又は持参|持参又は郵便|郵便により|郵便（|郵送（|郵便\(")  # fmt: skip
_M_NOT = re.compile(r"交付|返信用|郵便番号")
_REFUSED = re.compile(r"受け付けない|認めない|認められない")
_EMAIL = re.compile(
    r"(?:郵送|持参|郵便)[^。]{0,6}(?:又は|若しくは|、)\s*(?:電子)?メール|メールにより提出"
)


def submission_modes(ss: list[Sentence]) -> Hit | None:
    """The bidding ways the notice names in plain words: the electronic system (電子調達
    システムで行う), paper bids or bringing the bid (紙入札, 持参), mail (郵送による).
    A way never named is left out, as the labels do it (guide, gold wave 1). A refusal
    of mail (郵送等による入札は受け付けない) sets mail_not_allowed. A mail or e-mail
    choice (郵送又はメール) is not told apart from the system: nothing."""
    found: dict[str, list[Sentence]] = {"electronic": [], "in_person": [], "mail": []}
    refused: list[Sentence] = []
    for s in ss:
        t = s.text_norm
        if _EMAIL.search(t):
            return None
        if _REFUSED.search(t) and re.search(r"郵送|郵便", t):
            refused.append(s)
            continue
        if _E_CUE.search(t) and _E_VERB.search(t) and not _E_NOT.search(t):
            found["electronic"].append(s)
        if (_P_CUE.search(t) or _PAPER.search(t)) and not re.search(
            r"を除き|を除く", t
        ):
            found["in_person"].append(s)
        if _M_CUE.search(t) and not _M_NOT.search(t):
            found["mail"].append(s)
    if refused:
        found["mail"] = []
    if not found["electronic"]:
        # A paper bid named only as the way out of the system (紙入札方式に代える) says
        # nothing about the other ways when the system itself was not read.
        found["in_person"] = [x for x in found["in_person"] if not _PAPER.search(x.text_norm)]  # fmt: skip
    cited = sorted(
        {s.id: s for v in [*found.values(), refused] for s in v}.values(), key=ss.index
    )
    if not cited:
        return None
    modes = [k for k in ("in_person", "mail", "electronic") if found[k]]
    return (
        {"modes": modes, "mail_not_allowed": bool(refused)},
        "\n".join(s.text_orig.strip() for s in cited),
        [s.id for s in cited],
    )


# --- performance_period, delivery_deadline -----------------------------------------------

_PERIOD_HEAD = r"(?:履行期間|履行期限|契約期間|借入期間|業務期間)"
_FROM = re.compile(r"(契約締結(?:の日|日)?)(?:から|~)")


def _one_date(v: str):
    ds = find_dates(v)
    ok = len(ds) == 1 and ds[0].value is not None and not ds[0].warning
    return ds[0] if ok else None


def performance_period(ss: list[Sentence]) -> Hit | None:
    """After a 履行期間, 契約期間, 業務期間 or 履行期限 heading: a pointer, or
    `契約締結日から令和９年２月２６日まで` (relative_text 契約締結日, end the date), or
    `最長 令和9年9月末まで` (the whole phrase in relative_text, guide). The date must stand
    whole in one sentence: a date the segmenter cut in two is not read."""
    hits: list[Hit] = []
    for v, q, ids in headed(ss, _PERIOD_HEAD):
        if p := pointer(v, q):
            hits.append((p, q, ids))
        elif d := _one_date(v):
            pre, post = v[: d.start], v[d.end :]
            if (m := _FROM.fullmatch(pre)) and re.fullmatch(r"(?:まで)?。?", post):
                rel = m.group(1)
            elif re.fullmatch(r"最長\s*", pre) and re.fullmatch(r"まで。?", post):
                rel = v.rstrip("。")
            else:
                continue
            end = d.value.isoformat()  # type: ignore[union-attr]
            hits.append(({"start": None, "end": end, "relative_text": rel}, q, ids))
    return one(hits)


def delivery_deadline(ss: list[Sentence]) -> Hit | None:
    """A 納入期限 line (goods): a date alone (`令和９年３月３０日(火)とする`) or a pointer
    (`別途仕様書のとおり`). 履行期限 is not read here: on a services notice the label is
    absent, and the wording does not tell goods from services."""
    hits: list[Hit] = []
    for v, q, ids in headed(ss, r"(?:機器)?納入期限(?:については)?"):
        if p := pointer(v, q):
            hits.append((p, q, ids))
        elif (d := _one_date(v)) and not v[: d.start].strip() and re.fullmatch(r"(?:まで)?(?:とする|です)?。?", v[d.end :]):  # fmt: skip
            hits.append(({"date": d.value.isoformat()}, q, ids))  # type: ignore[union-attr]
    return one(hits)


# --- contracting_officer -----------------------------------------------------------------

_OFFICER_LINE = re.compile(r"(支出負担行為担当官|契約担当官)")
_POST = re.compile(r".*[長官）)]$")
_NAME = re.compile(r"[぀-ヿ一-鿿々]{1,6}(?:\s+[぀-ヿ一-鿿々]{1,4})?")


def contracting_officer(ss: list[Sentence]) -> Hit | None:
    """The officer's title alone in a sentence, then the post and the name: in one
    sentence (`出入国在留管理庁次長　内藤惣一郎`) or the post in the next and the name
    in the one after (`総務省政策統括官（…）` / `阪本　克彦`). Anything else (a post with
    no name, page text stuck to it) answers nothing."""
    hits: list[Hit] = []
    for i, s in enumerate(ss):
        m = _OFFICER_LINE.fullmatch(s.text_norm.strip())
        if not m or i + 1 >= len(ss):
            continue
        a = ss[i + 1]
        tok = a.text_orig.split()
        if len(tok) == 2 or (len(tok) == 3 and all(len(x) <= 4 for x in tok[1:])):
            post, name, used = tok[0], " ".join(tok[1:]), [s, a]
        elif len(tok) == 1 and i + 2 < len(ss) and (b := ss[i + 2]) and _NAME.fullmatch(b.text_orig.strip()):  # fmt: skip
            post, name, used = tok[0], " ".join(b.text_orig.split()), [s, a, b]
        else:
            continue
        if not _POST.match(normalize(post)[0]):
            continue
        hits.append(
            (
                {"title": f"{m.group(1)} {post}", "name": name},
                "\n".join(x.text_orig.strip() for x in used),
                [x.id for x in used],
            )
        )
    return one(hits)


def agreed(hits: list[Hit]) -> Hit | None:
    """A text field's answer when every hit says the same text (spaces and a trailing quantity such as 一式
    ignored): the longest wording, citing every sentence any hit used. A hit that is only the
    start of another (a line wrap cut it: 農林水産統計システ) agrees with it. Different
    texts: nothing."""

    def key(h: Hit) -> str:
        return re.sub(r"[0-9一]+(?:式|台)$", "", _strip(normalize(h[1])[0]))

    if not hits:
        return None
    best = max(hits, key=lambda h: len(key(h)))
    if not all(key(best).startswith(key(h)) for h in hits):
        return None
    ids = list(dict.fromkeys(i for h in hits for i in h[2]))
    return {}, best[1], ids


# --- title -------------------------------------------------------------------------------

# Labels in front of the title, as the dev scan found them (data/cache/rules_title_issuer_scan.txt):
# the portal header 調達案件名称, 案件名, (n) 購入等/借入等件名及び数量, (1) 件名, and in spec and
# bid-instruction documents 業務名, 委託業務名, 調達業務の名称. A label must end there: 調達件名の特質等
# is a different line. 契約件名 (the cover sheet of a notice) is not listed: it can disagree with the notice.
_TITLE_LABEL = r"(?:調達案件名称|案件名|(?:購入等|借入等|賃借等|調達)?件名(?:及び数量)?|(?:委託)?業務名|調達業務の名称)(?=\s|[:：]|$)"
_QTY = re.compile(
    r"[\s\u3000]+[0-9０-９一二三四五六七八九十]+(?:式|台)(?:[（(][^）)]*[）)])?$"
)  # "<title>　一式", "<title> ２式（電子入札対象案件）" after 件名及び数量: the quantity, not the name
_DEFINED = re.compile(
    r"[（(]以下[^）)]*[）)]$"
)  # "（以下「本整備業務」という。）" after a name
_CASE_NO = re.compile(
    r"^[0-9０-９]{2}-[0-9０-９]{3,}"
)  # a portal case number in front of the name: where the name ends is unclear
_NUMBERED = re.compile(r"^[(（]?[0-9一二三四五六七八九十]{1,2}[)）.．、]")


def _title_ok(v: str) -> bool:
    """A title is a name: not a numbered heading that follows an empty label, not a label."""
    return (
        len(v) >= 4
        and not _NUMBERED.match(v)
        and not _CASE_NO.match(v)
        and not re.fullmatch(_TITLE_LABEL, v)
    )


def title(ss: list[Sentence]) -> Hit | None:
    """The text after a title label (same line, or the next sentence when the label stands
    alone). Every label in the document must give the same text (spaces ignored); two
    different titles, such as a cover sheet and the notice itself, answer nothing."""
    hits: list[Hit] = []
    by = {s.id: s for s in ss}
    for norm_v, orig_v, ids in headed(ss, _TITLE_LABEL):
        if "及び数量" in by[ids[0]].text_norm and (m := _QTY.search(orig_v)):
            orig_v, norm_v = orig_v[: m.start()], _QTY.sub("", norm_v)
        if m := _DEFINED.search(orig_v):
            orig_v, norm_v = orig_v[: m.start()], _DEFINED.sub("", norm_v)
        if _title_ok(norm_v.strip()):
            hits.append(({}, orig_v.strip(), ids))
    return agreed(hits)


# --- issuer_org --------------------------------------------------------------------------

_ORG_END = r"(?:省|庁|府|院|委員会|県|都|道|市|区|町|村|機構)"
_ORG_LINE = re.compile(rf"\S{{2,20}}{_ORG_END}")
_ORG_PREFIX = re.compile(r"[^\s\u3000（(、。]{1,14}?(?:省|庁|府)")


def issuer_org(ss: list[Sentence]) -> Hit | None:
    """The body that issues the notice, from two places a national notice states it: the
    portal line under 調達機関, a bare name (省, 庁, 府, ...); or the line under the officer's
    title (支出負担行為担当官), where the name is the start of the post: 法務省大臣官房会計課長
    -> 法務省 (up to the first 省, 庁 or 府). A post that does not start with one of those
    names (気象衛星センター所長) answers nothing. Different names in one document: nothing."""
    hits: list[Hit] = []
    for norm_v, orig_v, ids in headed(ss, r"調達機関(?![番所])"):
        if len(ids) == 2 and _ORG_LINE.fullmatch(norm_v.strip()):
            hits.append(({}, orig_v.strip(), ids[1:]))
    for i, s in enumerate(ss[:-1]):
        if re.fullmatch(OFFICER.pattern, s.text_norm.strip()) and (m := _ORG_PREFIX.match(ss[i + 1].text_norm.strip())):  # fmt: skip
            nxt = ss[i + 1]
            off = len(nxt.text_norm) - len(nxt.text_norm.lstrip())
            q, ids = Joined([nxt]).cut(off + m.start(), off + m.end())
            hits.append(({}, q.strip(), ids))
    return agreed(hits)


# --- the extractor -----------------------------------------------------------------------

RULES: dict[str, Callable[[list[Sentence]], Hit | None]] = {
    "notice_date": notice_date,
    "procurement_type": procurement_type,
    "bid_bond": bid_bond,
    "performance_bond": performance_bond,
    "tax_basis": tax_basis,
    "unified_qualification": unified_qualification,
    "language_currency": language_currency,
    "wto_covered": wto_covered,
    "award_method": award_method,
    "spec_access": spec_access,
    "submission_modes": submission_modes,
    "delivery_deadline": delivery_deadline,
    "performance_period": performance_period,
    "contracting_officer": contracting_officer,
    "title": title,
    "issuer_org": issuer_org,
}


def _strip(s: str) -> str:
    return re.sub(r"\s+", "", s)


def value_in_citation(value_ja: str, cited: list[Sentence]) -> bool:
    """Every line of `value_ja`, normalized like the sentences, occurs in the cited
    sentences (spaces ignored), also across a join of them."""
    pools = [_strip(s.text_norm) for s in cited] + [
        "".join(_strip(s.text_norm) for s in cited)
    ]
    return all(_strip(normalize(p)[0]) in pool for p in value_ja.split("\n") if p for pool in pools[-1:])  # fmt: skip


def verified(field: str, hit: Hit, by_id: dict[str, Sentence]) -> Extracted | None:
    """The answer, or None when it cannot be tied to the sentences it cites."""
    normalized, value_ja, ids = hit
    cited = [by_id[i] for i in ids if i in by_id]
    if not ids or len(cited) != len(ids) or not value_ja.strip():
        return None
    if not value_in_citation(value_ja, cited):
        return None
    status = "present"
    try:
        if "ref" in normalized:
            status = "see_other_document"
            if set(normalized) != {"ref"}:
                return None
            SeeOtherRef.model_validate(normalized["ref"])
        else:
            validate_normalized(
                field, normalized or None
            )  # a text field has no normalized value: {}
    except ValidationError:
        return None
    return Extracted(
        field=field,
        value_ja=value_ja,
        normalized=normalized,
        citations=ids,
        status=status,
    )


def extract(doc_type: str, sentences: list[Sentence]) -> dict[str, Extracted]:
    """Every field the rules can answer for this document type. Japanese sentences only."""
    ss = [s for s in sentences if s.language == "ja"]
    by_id = {s.id: s for s in ss}
    out: dict[str, Extracted] = {}
    for field, rule in RULES.items():
        if doc_type not in BY_ID[field].applies_to:
            continue
        if (hit := rule(ss)) and (ans := verified(field, hit, by_id)):
            out[field] = ans
    return out
