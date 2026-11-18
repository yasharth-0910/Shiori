# ruff: noqa: E501
"""Model extractor for the three list fields: eligibility, deadlines, required_documents
(Phase 4). Rules answer everything else (rules.py).

    found = extract_lists(doc_type, sentences, client.complete, stats)

Per field: (1) retrieval, the sentences under sections whose heading holds one of the
field's cues (fields.py, docs/field_schema.md) or that start with a cue, plus a fixed
window around them, numbered with their ids; (2) one call to a local llama-server on
127.0.0.1 with JSON-schema output built from fields.py; (3) deterministic normalization
(dates and times through value_normalize, flags from the cited wording); (4) a citation
check in code: every id must exist, every value must appear in its cited sentences,
otherwise that item is dropped. Nothing left means not found. The model never writes page
numbers or boxes.

Only the loopback address is accepted (`Client`); nothing else is ever contacted (D-69).
No document text is logged: `CallStat` holds counts and seconds only.
"""

import json
import re
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dc_field

from pydantic import BaseModel, ValidationError

from shiori_core.extract.rules import (
    Extracted,
    Joined,
    submission_modes,
    value_in_citation,
)
from shiori_core.fields import BY_ID, validate_normalized
from shiori_core.models import Sentence
from shiori_core.normalize import normalize
from shiori_core.value_normalize import find_dates, find_deadline_flags, find_times

LIST_FIELDS = ("eligibility", "deadlines", "required_documents")
HOST = "127.0.0.1"
WINDOW = 3  # sentences kept on each side of a cue hit
BUDGET = 7000  # characters sent per call, at most
MAX_OUT = 2048  # tokens
TIMEOUT = 300.0  # seconds a call may take (the server answers once, at the end)
MAX_ITEMS = 40  # most items the grammar allows in one answer
MAX_CITES = 8  # most ids the grammar allows in one citations list

# What each item needs, as (the text key in the item, the other keys the model must not write).
TEXT_KEY = {"eligibility": "text_ja", "required_documents": "name_ja"}
DROP_PROPS = ("text_en", "name_en")  # translation is a later stage

# --- the prompt: the field's guide rules and one real example each ---------------------

RULES = {
    "eligibility": """One item per qualification rule a bidder must meet (競争参加資格, 参加資格, 暴力団関係事業者, 指名停止).
- kind: unified_qualification (全省庁統一資格 and its grades), legal (laws and orders, 暴力団関係事業者), suspension (指名停止), experience, certification, other.
- polarity: requirement or disqualification. When text_ja keeps its negation (...ないこと) the polarity is requirement. Disqualification only when text_ja describes the bad state itself.
- A なお or ただし sentence about 未成年者, 被保佐人 or 被補助人 who have the needed consent stays inside the same item: same item, same text_ja, and both sentence ids in citations.
- text_ja: copied exactly from the sentence, without the leading number such as (2). Never shorten it with an ellipsis.""",
    "deadlines": """One item per dated event (入札日時, 入札書の受領期限, 提出期限, 受付期間, 開札日時, 質問, 入札説明会).
- kind: bid_in_person (handed in at a place and time), mail_arrival (sent by mail, with an arrival time), electronic (through an electronic system), bid_opening (開札), question, briefing (説明会), document_request, other.
- A bid receipt deadline on an electronic notice is electronic. mail_arrival only when mail is said (必着, 到着). When the sentence does not say how bids are received, use other.
- datetime: YYYY-MM-DD when the text gives no time, else YYYY-MM-DDTHH:MM:00+09:00 (Japan time). 令和N年 is the year 2018+N. relative_text: only for a rule that is not a calendar date (入札説明書の交付後7日以内); then datetime is null. Exactly one of the two.
- One sentence can hold two events (a bid time and, in brackets, a mail arrival time): one item each, each with its own date and time.""",
    "required_documents": """One item per document the bidder must hand in (提出書類, 提出物, 必要書類).
- name_ja: the document's name, copied exactly from the sentence.
- Include 入札書 whenever the notice mentions submitting a bid form in any way (入札書を提出, 入札書に記載, a receipt deadline for bids), plus every document named with a submission deadline or a duty to submit.
- Do not add 入札書 for a proposal competition that never mentions one.
- Go through a numbered list of documents in order, one item per entry, and do not skip entries in the middle. Do not merge several documents into one item.""",
}

EXAMPLES = {
    "eligibility": (
        [("h_s44", "(4)　内閣府本府における物品等の契約に係る指名停止等措置要領に基づく指名停止を受けている期間中の者でないこと。")],
        {"items": [{"kind": "suspension", "polarity": "requirement", "text_ja": "内閣府本府における物品等の契約に係る指名停止等措置要領に基づく指名停止を受けている期間中の者でないこと。", "citations": ["h_s44"]}]},
    ),
    "deadlines": (
        [("h_s45", "(4)　入札書の受領期限　令和８年10月15日13時30分（ただし、郵送による入札は、令和８年10月14日16時00分必着）")],
        {"items": [
            {"kind": "other", "datetime": "2026-10-15T13:30:00+09:00", "relative_text": None, "citations": ["h_s45"]},
            {"kind": "mail_arrival", "datetime": "2026-10-14T16:00:00+09:00", "relative_text": None, "citations": ["h_s45"]},
        ]},
    ),
    "required_documents": (
        [("h_s46", "(3)　入札書の提出期限　令和８年10月14日17時00分までの平日又は電子調達システム")],
        {"items": [{"name_ja": "入札書", "citations": ["h_s46"]}]},
    ),
}  # fmt: skip

SYSTEM = (
    "You read part of a Japanese public tender document. Each sentence is written as "
    "[id] text. Answer in JSON for one field only. Use only what the sentences say, "
    "and cite the ids of the sentences each item comes from, exactly as shown. "
    "When the field is not stated, answer with an empty items list."
)


def one_line(s: Sentence) -> str:
    return re.sub(r"\s*\n\s*", " ", s.text_orig).strip()


def numbered(ss: list[Sentence]) -> str:
    return "\n".join(f"[{s.id}] {one_line(s)}" for s in ss)


def prompt(fld: str, ss: list[Sentence]) -> str:
    ex_in, ex_out = EXAMPLES[fld]
    ex = "\n".join(f"[{i}] {t}" for i, t in ex_in)
    return (
        f"Field: {fld}\n\nRules:\n{RULES[fld]}\n\n"
        f"Example sentences:\n{ex}\nExample answer:\n{json.dumps(ex_out, ensure_ascii=False)}\n\n"
        f"Sentences to read:\n{numbered(ss)}\n\nAnswer for {fld}:"
    )


def schema_for(fld: str) -> dict:
    """The field's pydantic schema, with an empty list allowed (the grammar must be able
    to say "nothing found"), without the translation keys and the flags, and with every
    array bounded."""
    model = BY_ID[fld].model
    assert model is not None
    s = model.model_json_schema()
    s["properties"]["items"]["minItems"] = 0
    s["properties"]["items"]["maxItems"] = MAX_ITEMS
    for d in s.get("$defs", {}).values():
        props = d.get("properties", {})
        for k in (*DROP_PROPS, "flags"):  # flags are set in code from the cited wording
            props.pop(k, None)
        if "citations" in props:  # an unbounded array let the model loop (58f13b9c)
            props["citations"]["maxItems"] = MAX_CITES
    return s


# --- retrieval --------------------------------------------------------------------------


# required_documents also reads the deadlines cues: the guide takes every document named
# with a submission deadline (入札書の受領期限 makes 入札書 an item). Added after the first
# 2-document run found nothing under the three required_documents cues (D-69).
EXTRA_CUES = {"required_documents": "deadlines"}
# Headings only (first two levels): the sections where required_documents label items sat
# outside the window in the v2 diagnostic (32 of 51). 書類 is the 提出書類, 必要書類,
# 企画提案書類 style heading; 入札方法 and 入札者に要求される事項 are the national notice
# headings that list the bid form and the documents to hand in (D-69 addendum).
HEADING_CUES = {"required_documents": ("書類", "入札方法", "入札者に要求される事項")}


def retrieve(fld: str, ss: list[Sentence]) -> list[Sentence]:
    """Sentences under a section whose heading (first two levels) holds a cue of the
    field, or that start with a cue, plus WINDOW sentences each side, in document order,
    cut at BUDGET characters."""
    cues = BY_ID[fld].cues + (BY_ID[EXTRA_CUES[fld]].cues if fld in EXTRA_CUES else ())
    heading_cues = cues + HEADING_CUES.get(fld, ())
    hits = [
        i
        for i, s in enumerate(ss)
        if any(c in t for t in s.section_titles[:2] for c in heading_cues)
        or any(c in s.text_norm[:30] for c in cues)
    ]
    keep = sorted({j for i in hits for j in range(max(0, i - WINDOW), min(len(ss), i + WINDOW + 1))})  # fmt: skip
    out, n = [], 0
    for j in keep:
        n += len(ss[j].text_orig)
        if n > BUDGET:
            break
        out.append(ss[j])
    return out


# --- the client (loopback only) -----------------------------------------------------------


class Truncated(ValueError):
    """The answer hit the token cap, so it is cut mid-JSON. The same request at
    temperature 0 gives the same cut, so it is not retried."""


class Client:
    """llama-server's OpenAI-style chat endpoint on 127.0.0.1. Any other host is refused
    when the client is made, so no document can be sent anywhere else (privacy.md)."""

    def __init__(self, port: int, host: str = HOST, timeout: float = TIMEOUT) -> None:
        if host != HOST:
            raise ValueError(f"only {HOST} is allowed, not {host!r}")
        self.url = f"http://{HOST}:{port}/v1/chat/completions"
        self.timeout = timeout

    def complete(self, system: str, user: str, schema: dict, max_out: int) -> str:
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
            "max_tokens": max_out,
            "cache_prompt": True,
            "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "strict": True, "schema": schema}},
        }  # fmt: skip
        req = urllib.request.Request(
            self.url, json.dumps(body).encode(), {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            choice = json.load(r)["choices"][0]
        if choice.get("finish_reason") == "length":
            raise Truncated("answer cut at the token cap")
        return choice["message"]["content"] or ""


Complete = Callable[[str, str, dict, int], str]


# --- checks and normalization --------------------------------------------------------------


@dataclass
class CallStat:
    """Counts and seconds of one call. No text."""

    field: str
    seconds: float = 0.0
    sentences_sent: int = 0
    proposed: int = 0
    kept: int = 0
    dropped: dict[str, int] = dc_field(default_factory=dict)  # reason -> items
    call_failed: str | None = None  # error type, never a message
    retries: int = 0
    recovered: int = 0  # deadline items whose date was read from the cited sentence
    polarity_set: int = 0  # eligibility items whose polarity was set by the guide rule
    merged: int = (
        0  # なお/ただし sentences merged into the eligibility item before them
    )
    kind_set: int = 0  # eligibility items set to kind other by the 第73条 rule (D-71)
    copies: int = 0  # eligibility items dropped as copies of a merged item (D-73)
    cue_kind_set: int = (
        0  # deadline items set from other to electronic by the cue (D-73)
    )
    # For the diagnostic (eval/hybrid.py), in memory only: the ids sent, and every item
    # the model proposed with its verdict ("kept" or the reason it was dropped).
    retrieved: list[str] = dc_field(default_factory=list)
    trace: list[tuple[dict, str]] = dc_field(default_factory=list)


MAIL = "郵送"
# A requirement written with its negation kept (…ないこと, …でないこと, …がない者であること):
# docs/labeling_guide.md, eligibility rule. Same pattern as eval/silver/agree.py (core cannot import eval).
NEGATION_END = re.compile(r"(?:では|で|が)?ない(?:者であること|こと|者)$")


@dataclass
class Span:
    """A date in one sentence and the text that belongs to it: up to the next date or the
    next 郵送, so "11時 ... （郵送による場合は ... 午前９時30分必着）" is two spans."""

    date: str
    start: int
    end: int
    mail: bool  # a 郵送 clause came right before this date
    times: set[str]
    text: str  # the span's own wording (for 必着 and 消印有効)


def spans_of(text: str) -> list[Span]:
    dates = [f for f in find_dates(text) if f.value]
    times = [f for f in find_times(text) if f.value]
    marks = sorted([(f.start, "d") for f in dates] + [(m.start(), "m") for m in re.finditer(MAIL, text)])  # fmt: skip
    out = []
    for f in dates:
        before = [m for m in marks if m[0] < f.start]
        end = min((m[0] for m in marks if m[0] > f.start), default=len(text))
        assert f.value is not None
        out.append(Span(
            f.value.isoformat(), f.start, end, bool(before) and before[-1][1] == "m",
            {t.value.strftime("%H:%M") for t in times if t.value and f.start <= t.start < end},
            text[f.start : end],
        ))  # fmt: skip
    return out


def _deadline_when(item: dict, cited: list[Sentence]) -> tuple[str, str] | None:
    """(datetime, wording the flags are read from), or None when the item does not hold.
    The date must be one a cited sentence gives, and its time must sit in the same
    sentence inside that date's own span (not anywhere in the cited sentences). A mail
    arrival item reads the mail spans, any other kind the other spans, so a mail time in
    brackets cannot pass for the bid opening. A lone time in the span is added when the
    model left it out."""
    when, mail_kind = item["datetime"], item["kind"] == "mail_arrival"
    found = [
        (sp, s) for s in cited for sp in spans_of(s.text_norm) if sp.date == when[:10]
    ]
    if not found:
        return None
    pref = [x for x in found if x[0].mail == mail_kind] or found
    if len(when) > 10:
        hit = next((x for x in pref if when[11:16] in x[0].times), None)
    else:
        every = {t for sp, _ in pref for t in sp.times}
        if len(every) == 1:
            when = f"{when}T{next(iter(every))}:00+09:00"
        hit = pref[0]
    if hit is None:
        return None
    sp, sent = hit
    # flags: this span's wording, plus the other cited sentences (a 必着 on its own line)
    return when, sp.text + "".join(s.text_norm for s in cited if s is not sent)


def _recover_date(it: dict, by_id: dict[str, Sentence]) -> str | None:
    """The date of a deadline the model gave without datetime or relative_text, read from
    its cited sentences with the normalizer, or None. Only a date the wording makes
    certain: one distinct date among the spans that fit the kind (mail spans for
    mail_arrival, the others for any other kind). Two dates or none means None; nothing
    is guessed. `_check` then runs its usual date and time checks on the result."""
    ids = it.get("citations")
    if not ids or any(i not in by_id for i in ids):
        return None
    mail_kind = it.get("kind") == "mail_arrival"
    spans = [sp for i in ids for sp in spans_of(by_id[i].text_norm)]
    pref = [sp for sp in spans if sp.mail == mail_kind] or spans
    dates = {sp.date for sp in pref}
    return dates.pop() if len(dates) == 1 else None


def _polarity(it: dict) -> str:
    """The guide's rule: a text_ja that keeps its negation is a requirement. The other half
    (negation stripped means disqualification) is not applied: a text without a negation can
    be a plain requirement, so the model's answer stays."""
    text = re.sub(r"[。．.]+$", "", it["text_ja"])
    return "requirement" if NEGATION_END.search(text) else it["polarity"]


# D-71: 第73条 plus 支出負担行為担当官が定める資格 is the agency's own qualification: kind other.
ART73 = re.compile(r"^予算決算及び会計令第73条")
OWN_QUALIFICATION = "支出負担行為担当官が定める資格"
PROVISO = re.compile(r"^(?:なお|ただし)")


def _kind(it: dict) -> str:
    text = normalize(it["text_ja"].strip())[0]
    return "other" if ART73.match(text) and OWN_QUALIFICATION in text else it["kind"]


def _merge_provisos(kept: list[dict], by_id: dict[str, Sentence], stat: CallStat) -> list[dict]:  # fmt: skip
    """A sentence that starts with なお or ただし right after an item's last cited sentence
    belongs to that item (docs/labeling_guide.md, minors exception): text_ja gets it on a new
    line, citations get its id. An item that only cites such a sentence is then dropped
    (counted as merged in the trace). With no item before it, the sentence stays as it is.
    "Right after" means the next sentence sent; the windows have no gaps inside a run."""
    order = list(by_id)
    pos = {i: n for n, i in enumerate(order)}
    is_proviso = lambda i: bool(PROVISO.match(by_id[i].text_norm.strip()))  # noqa: E731
    merged: set[str] = set()
    grew: list[dict] = []
    for it in kept:
        ids = it["citations"]
        last = max((pos[i] for i in ids), default=-1)
        if (
            not ids
            or last + 1 >= len(order)
            or is_proviso(min(ids, key=pos.__getitem__))
        ):
            continue
        nxt = order[last + 1]
        if nxt in ids or nxt in merged or not is_proviso(nxt):
            continue
        it["text_ja"] += "\n" + one_line(by_id[nxt])
        it["citations"] = [*ids, nxt]
        merged.add(nxt)
        grew.append(it)
    gone = [it for it in kept if it["citations"] and set(it["citations"]) <= merged]
    gone_ids = {id(it) for it in gone}
    stat.trace[:] = [(p, "merged" if id(p) in gone_ids else v) for p, v in stat.trace]
    stat.merged = len(merged)
    kept = [it for it in kept if id(it) not in gone_ids]
    # D-73: an item that now says what a merged item says (same polarity and the same
    # text, or citations inside the merged item's) is a copy of it; the merged item stays.
    one = lambda t: t.replace("\n", "")  # noqa: E731
    copies = {
        id(c)
        for g in grew
        for c in kept
        if c is not g
        and not any(c is x for x in grew)
        and c["polarity"] == g["polarity"]
        and (
            one(c["text_ja"]) == one(g["text_ja"])
            or set(c["citations"]) <= set(g["citations"])
        )  # fmt: skip
    }
    stat.trace[:] = [
        (p, "merged_copy" if id(p) in copies else v) for p, v in stat.trace
    ]
    stat.copies = len(copies)
    return [it for it in kept if id(it) not in copies]


# D-72: the kinds a deadline sentence's own heading allows (docs/labeling_guide.md, bid receipt kind).
# The first cue found in the sentence wins, so a 入札書の提出期限 line that mentions 開札 later is a bid line.
DEADLINE_CUES = (
    (re.compile(r"提出書類等"), frozenset({"other"})),
    (
        re.compile(r"入札書の(?:提出|受領)期限"),
        frozenset({"electronic", "bid_in_person"}),
    ),
    (re.compile(r"開札"), frozenset({"bid_opening"})),
)


BID_RECEIPT = frozenset({"electronic", "bid_in_person"})


def _receipt_kind(it: dict, by_id: dict[str, Sentence]) -> str:
    """D-73: a deadline the model called other, on a sentence whose own cue is 入札書の
    受領期限 or 入札書の提出期限, is the bid receipt: kind electronic (docs/labeling_guide.md
    line 124, for an electronic notice; the caller checks that). Any other kind stays."""
    if it["kind"] != "other":
        return it["kind"]
    cue = _cue_kinds(" ".join(by_id[i].text_norm for i in it["citations"]))
    return "electronic" if cue == BID_RECEIPT else "other"


def _cue_kinds(text: str) -> frozenset[str] | None:
    hits = [(m.start(), kinds) for rx, kinds in DEADLINE_CUES if (m := rx.search(text))]
    return min(hits, key=lambda h: h[0])[1] if hits else None


def _drop_same_sentence_copies(kept: list[dict], by_id: dict[str, Sentence], stat: CallStat) -> list[dict]:  # fmt: skip
    """Items with the same datetime and the same cited sentences are one event said twice
    with different kinds. Keep the one whose kind the sentence's own cue allows; drop the
    rest. No cue, or no item (or more than one) matching it: keep the group as it is,
    nothing is guessed. Items that cite different sentences are never grouped."""
    groups: dict[tuple, list[dict]] = {}
    for it in kept:
        if it.get("datetime"):
            groups.setdefault((it["datetime"], tuple(sorted(it["citations"]))), []).append(it)  # fmt: skip
    gone: set[int] = set()
    for (_, ids), grp in groups.items():
        cue = _cue_kinds(" ".join(by_id[i].text_norm for i in ids))
        fit = [it for it in grp if cue and it["kind"] in cue]
        if len(grp) > 1 and len(fit) == 1:
            gone |= {id(it) for it in grp if it is not fit[0]}
    stat.trace[:] = [
        (p, "same_sentence" if id(p) in gone else v) for p, v in stat.trace
    ]
    if gone:
        stat.dropped["same_sentence"] = len(gone)
    return [it for it in kept if id(it) not in gone]


def _check(fld: str, it: dict, by_id: dict[str, Sentence]) -> tuple[dict | None, str]:
    """(the item, "") when it passes, else (None, reason)."""
    ids = it.get("citations") or []
    if any(i not in by_id for i in ids):
        return None, "unknown_id"
    cited = [by_id[i] for i in ids]
    if fld in TEXT_KEY:
        it[TEXT_KEY[fld]] = it[TEXT_KEY[fld]].replace("\n", "").strip()
        if not value_in_citation(it[TEXT_KEY[fld]], cited):
            return None, "value_not_in_citation"
        if fld == "eligibility":
            it["polarity"] = _polarity(it)
            it["kind"] = _kind(it)
        return it, ""
    if it.get("relative_text") is not None:
        if not value_in_citation(it["relative_text"], cited):
            return None, "value_not_in_citation"
        text = Joined(cited).text
    else:
        got = _deadline_when(it, cited)
        if got is None:
            return None, "date_or_time_not_in_citation"
        it["datetime"], text = got
    it["flags"] = sorted({f.value for f in find_deadline_flags(text) if f.value})
    return it, ""


def _item_key(fld: str, it: dict) -> tuple:
    if fld in TEXT_KEY:
        return (it.get("kind"), it[TEXT_KEY[fld]])
    return (it["kind"], it.get("datetime"), it.get("relative_text"))


def _value_ja(fld: str, items: list[dict], by_id: dict[str, Sentence]) -> str:
    if fld in TEXT_KEY:
        return "\n".join(it[TEXT_KEY[fld]] for it in items)
    ids = dict.fromkeys(i for it in items for i in it["citations"])
    return "\n".join(by_id[i].text_orig for i in ids)


def read_items(
    fld: str,
    raw: str,
    by_id: dict[str, Sentence],
    stat: CallStat,
    electronic: bool = False,
) -> list[dict]:
    """The model's answer as the items that pass every check; the rest are counted in
    `stat.dropped` by reason."""
    items = json.loads(raw).get("items", [])
    item_model = _item_model(fld)
    stat.proposed = len(items)
    kept: list[dict] = []
    seen: set[tuple] = set()
    for it in items:
        try:
            it = item_model.model_validate(it).model_dump(exclude_none=False)
            it = {k: v for k, v in it.items() if k not in DROP_PROPS}
        except ValidationError:
            fixed = _recovered(fld, it, item_model, by_id)
            if fixed is None:
                stat.dropped["schema"] = stat.dropped.get("schema", 0) + 1
                stat.trace.append((it, "schema"))
                continue
            it = fixed
            stat.recovered += 1
        raw_pol = it.get("polarity")
        ok, why = _check(fld, dict(it), by_id)
        if ok is not None and fld == "deadlines" and electronic:
            kind = _receipt_kind(ok, by_id)
            stat.cue_kind_set += kind != ok["kind"]
            ok["kind"] = kind
        if ok is not None and raw_pol is not None and ok["polarity"] != raw_pol:
            stat.polarity_set += 1
        if ok is not None and fld == "eligibility" and ok["kind"] != it["kind"]:
            stat.kind_set += 1
        if ok is None:
            stat.dropped[why] = stat.dropped.get(why, 0) + 1
            stat.trace.append((it, why))
        elif (k := _item_key(fld, ok)) in seen:
            stat.dropped["duplicate"] = stat.dropped.get("duplicate", 0) + 1
            stat.trace.append((ok, "duplicate"))
        else:
            seen.add(k)
            kept.append(ok)
            stat.trace.append((ok, "kept"))
    if fld == "eligibility":
        kept = _merge_provisos(kept, by_id, stat)
    if fld == "deadlines":
        kept = _drop_same_sentence_copies(kept, by_id, stat)
    stat.kept = len(kept)
    return kept


def _recovered(fld: str, it: dict, item_model: type[BaseModel], by_id: dict[str, Sentence]) -> dict | None:  # fmt: skip
    """A deadline that has a kind and citations but neither datetime nor relative_text,
    with the date read from the cited sentences; None when it is not that case, the
    sentences do not give one date, or the result is still not a valid item."""
    if fld != "deadlines" or it.get("datetime") or it.get("relative_text"):
        return None
    when = _recover_date({**it}, by_id)
    if when is None:
        return None
    try:
        got = item_model.model_validate({**it, "datetime": when, "relative_text": None})
    except ValidationError:
        return None
    return {k: v for k, v in got.model_dump(exclude_none=False).items() if k not in DROP_PROPS}  # fmt: skip


def _item_model(fld: str) -> type[BaseModel]:
    model = BY_ID[fld].model
    assert model is not None
    return model.model_fields["items"].annotation.__args__[0]  # type: ignore[union-attr]


# --- the extractor ---------------------------------------------------------------------------


def extract_lists(
    doc_type: str,
    sentences: list[Sentence],
    complete: Complete,
    stats: list[CallStat] | None = None,
) -> dict[str, Extracted]:
    """The list fields the model found and the checks kept. A field with no retrieved
    sentence makes no call; a failed call or an answer with nothing left is not found."""
    ss = [s for s in sentences if s.language == "ja"]
    by_id = {s.id: s for s in ss}
    out: dict[str, Extracted] = {}
    modes = submission_modes(ss)
    electronic = modes is not None and modes[0]["modes"] == ["electronic"]
    for fld in LIST_FIELDS:
        if doc_type not in BY_ID[fld].applies_to:
            continue
        sent = retrieve(fld, ss)
        stat = CallStat(fld, sentences_sent=len(sent), retrieved=[s.id for s in sent])
        if stats is not None:
            stats.append(
                stat
            )  # a field with nothing retrieved is recorded, with 0 sentences
        if not sent:
            continue
        t0 = time.monotonic()
        items: list[dict] = []
        for attempt in (0, 1):  # one retry, then not found
            stat.retries = attempt
            stat.trace.clear()
            stat.dropped.clear()
            stat.proposed = stat.kept = 0
            try:
                raw = complete(SYSTEM, prompt(fld, sent), schema_for(fld), MAX_OUT)
                items = read_items(fld, raw, {s.id: s for s in sent}, stat, electronic)
                stat.call_failed = None
                break
            except (OSError, ValueError, KeyError, TypeError) as e:
                stat.call_failed = type(e).__name__
                if isinstance(
                    e, Truncated
                ):  # same request, same cut: no use asking again
                    break
        stat.seconds = time.monotonic() - t0
        if not items:
            continue
        normalized = {"items": items}
        try:
            validate_normalized(fld, normalized)
        except ValidationError:
            continue
        ids = list(dict.fromkeys(i for it in items for i in it["citations"]))
        out[fld] = Extracted(field=fld, value_ja=_value_ja(fld, items, by_id), normalized=normalized, citations=ids)  # fmt: skip
    return out
