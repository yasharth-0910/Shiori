# ruff: noqa: E501
"""Silver-label pipeline: per document and labeler one call (or several parts) for
every applicable field, auto checks, agreement, accepted / flagged (D-43 to D-50).

Cloud answers are cached by (doc_id, extractor_version, schema_version, provider, model,
prompt_version), so a re-run costs nothing and a run stopped by a daily cap resumes
where it left off. The cache holds restricted-document text and is gitignored.
"""

import hashlib
import json
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError
from shiori_core.fields import BY_ID, FIELD_IDS, SCHEMA_VERSION
from shiori_core.models import EXTRACTOR_VERSION, Sentence

from collector.manifest import ManifestRow
from eval.label_format import LabelLine
from eval.silver import config
from eval.silver.agree import agree, union_items
from eval.silver.checks import (
    BLOCKING,
    SHORT_CUE,
    cue_at_heading,
    cue_is_heading,
    failed,
    run_checks,
    shape_errors,
)
from eval.silver.config import (
    LOCAL_CTX,
    LOCAL_MAX_OUT,
    LOCAL_MODELS,
    LOCAL_OUT_SHARE,
    LOCAL_PROMPT_VERSION,
    PROMPT_VERSION,
    PROVIDERS,
    ProviderCfg,
)  # fmt: skip
from eval.silver.keys import get_key, redact
from eval.silver.limiter import DailyCap, Ledger, Limiter
from eval.silver.model import Candidate, from_row
from eval.silver.prompt import (
    EXAMPLES,
    applicable_fields,
    est_output,
    est_tokens,
    field_form,
    focused_fields,
    line,
    local_system_prompt,
    local_user_prompt,
    overhead,
    response_schema,
    rows_of,
    split_document,
    system_prompt,
    user_prompt,
)  # fmt: skip
from eval.silver.providers import (
    Completion,
    Gemini,
    Groq,
    Local,
    Provider,
    ProviderError,
)

EVAL_DIR = Path("data/eval")
PRIVATE_DIR = Path("data/eval_private")
LOCAL_CFG = ProviderCfg(
    "local", "", "local", False, rpm=10**6, tpm=10**9, rpd=10**9, tpd=None,
    published=True, request_cap=LOCAL_CTX, max_out=LOCAL_MAX_OUT,
    out_share=LOCAL_OUT_SHARE, repair=True,
)  # fmt: skip
TIMING_KEYS = ("cache_n", "prompt_n", "prompt_ms", "predicted_n", "predicted_ms")
CTX_MARGIN = 512  # tokens of the local context kept free for the chat template


# --- who labels a document -------------------------------------------------------------


@dataclass(frozen=True)
class Assignment:
    """slot (A, B) -> labeler key: a cloud provider's name, or "local:<gguf>"."""

    keys: dict[str, str]

    @property
    def overlap(self) -> bool:
        return any(k.startswith("local:") for k in self.keys.values())


def local_model_for(remaining_family: str) -> str:
    return next(g for g, fam in LOCAL_MODELS if fam != remaining_family)


def assign(row: ManifestRow) -> Assignment | str:
    """Provider policy (D-44, D-50). Side A is Gemini for an open document and Groq for
    any other; side B is the local model, of a different family than A. A document
    that is not `open` never goes to a provider whose may_train_on_inputs is true or
    unknown, checked here before every document: if Groq's flag ever stops being
    false, restricted documents are skipped (the local model alone would be one vote,
    not two). Returns the reason when skipped."""
    cloud = "gemini" if row.license_class == "open" else "groq"
    if (
        row.license_class != "open"
        and PROVIDERS[cloud].may_train_on_inputs is not False
    ):
        return f"{cloud} is not allowed for a {row.license_class} document and only one local vote is possible"  # fmt: skip
    return Assignment({"A": cloud, "B": "local:" + local_model_for(PROVIDERS[cloud].family)})  # fmt: skip


# --- chunk planning --------------------------------------------------------------------


def cfg_for(key: str) -> ProviderCfg:
    return LOCAL_CFG if key.startswith("local:") else PROVIDERS[key]


def max_out_for(cfg: ProviderCfg, n_fields: int, est_in: int = 0) -> int:
    if cfg.name == "local":  # the cap, or what the context leaves when that is less
        return min(cfg.max_out, cfg.request_cap - est_in - CTX_MARGIN)
    if cfg.request_cap >= 50_000:  # Gemini: thinking tokens count against the cap
        return cfg.max_out
    return min(cfg.max_out, int(est_output(n_fields) * 1.3))


MIN_TEXT = 800  # estimated tokens of document text a request must have room for
BACKOFF = (
    30,
    60,
    120,
    240,
)  # seconds between tries on 503, 429 or network errors (ProviderCfg.max_tries: 5, Gemini 3)


@dataclass
class Part:
    """One request: a group of fields asked about one chunk of the document."""

    field_ids: list[str]
    sentences: list[Sentence]
    max_out: int
    overhead: int

    def est_in(self) -> int:
        return self.overhead + sum(est_tokens(line(s)) + 2 for s in self.sentences)


def field_groups(ids: list[str], k: int) -> list[list[str]]:
    """`ids` cut into k runs of nearly equal length, order kept."""
    n, out, start = len(ids), [], 0
    for g in range(k):
        end = start + n // k + (g < n % k)
        out.append(ids[start:end])
        start = end
    return out


def plan_parts(row: ManifestRow, ja: list[Sentence], cfg: ProviderCfg) -> list[Part]:
    """The requests one labeler needs for one document: `best_grouping` (sv4: one
    grouped call per document for every labeler that has room, D-54). Only with
    config.LOCAL_FOCUSED does the local labeler get its list fields and contact one per
    call, then one grouped call for the rest (sv3-l1, D-53). The grouped call goes
    last: Qwen3.5 is a hybrid model, so llama-server restores a cached prompt only from
    a checkpoint, which it saves about 512 tokens before the end of each prompt. After
    a short single-field call that point is still inside the shared document; after
    the long grouped field list it would not be."""
    ids = applicable_fields(row.doc_type)
    if cfg.name != "local" or not config.LOCAL_FOCUSED:
        return best_grouping(ids, ja, cfg)
    single = focused_fields(ids)
    rest = [f for f in ids if f not in single]
    return [p for f in single for p in best_grouping([f], ja, cfg)] + (
        best_grouping(rest, ja, cfg) if rest else []
    )


def best_grouping(ids: list[str], ja: list[Sentence], cfg: ProviderCfg) -> list[Part]:
    """The fields are cut into k groups and each group sees every chunk. A grouping is
    possible when every group's estimated answer fits `out_share` of the output cap
    (local model: 60%, so an answer longer than estimated is not cut off; Gemini: the
    whole cap) and every request has room for at least MIN_TEXT tokens of text (Groq's
    8,000 tokens per request). k is the smallest-cost choice: fewest estimated tokens in
    total, so Gemini and the local model get k = 1 unless their answer would not fit."""
    local = cfg.name == "local"
    best: tuple[int, list[Part]] | None = None
    for k in range(1, len(ids) + 1):
        parts: list[Part] = []
        for g in field_groups(ids, k):
            need = est_output(len(g))
            if need > cfg.max_out * cfg.out_share:
                break
            oh = overhead(g)
            mo = math.ceil(need / cfg.out_share) if local else max_out_for(cfg, len(g))
            budget = int((cfg.request_cap - oh - mo) * 0.95)
            if budget < MIN_TEXT:
                break
            for c in split_document(ja, budget):
                p = Part(g, c, mo, oh)
                if local:  # raise the cap as far as this request's context allows
                    p.max_out = max_out_for(cfg, len(g), p.est_in())
                parts.append(p)
        else:
            cost = sum(p.est_in() + p.max_out for p in parts)
            if best is None or cost < best[0]:
                best = (cost, parts)
            if len(parts) == k:  # one chunk per group: more groups only add overhead
                break
    if best is None:
        raise ValueError(f"{cfg.name}: no room for text in any field grouping")
    return best[1]


# --- raw cache -------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def prompt_for(provider: str) -> str:
    """The prompt version of a labeler's requests (D-53: the local one has its own;
    with focused calls it carries config.FOCUSED_SUFFIX, D-54)."""
    if provider != "local":
        return PROMPT_VERSION
    return LOCAL_PROMPT_VERSION + (
        config.FOCUSED_SUFFIX if config.LOCAL_FOCUSED else ""
    )


def raw_path(doc_id: str, provider: str, model: str, prompt: str | None = None) -> Path:
    prompt = prompt or prompt_for(provider)
    safe = re.sub(r"[^A-Za-z0-9.\-]+", "_", model)
    name = f"{provider}__{safe}__{prompt}__{EXTRACTOR_VERSION}__{SCHEMA_VERSION}.json"
    return config.CACHE / "raw" / doc_id / name


def load_raw(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {"chunks": {}}


class OutOfCalls(Exception):
    pass


def repair_message(errors: list[str]) -> str:
    listed = "\n".join(f"- {e}" for e in errors[:40])
    return (f"Your answer does not fit the required form:\n{listed}\n"
            "Return the whole answer again as one JSON object in the same form, with these "
            "problems fixed and every other entry unchanged.")  # fmt: skip


def plain_repair_message(errors: list[str]) -> str:
    """The local labeler's repair message (sv3-l1, D-53): per field, what is wrong in
    plain words, the field's form and a one-line example, instead of the validator's
    own message ("Input should be a valid dictionary or instance of Deadlines")."""
    out = []
    for e in errors[:40]:
        f, _, why = e.partition(": ")
        if f not in BY_ID:  # the whole answer: not JSON, not the answer shape
            out.append(f"- {e}")
            continue
        if why == "missing from fields":
            what = f'there is no entry for {f} in "fields"; add one.'
        elif BY_ID[f].model is not None and "valid dictionary" in why:
            what = (f"its status is present but normalized.{f} is empty. Give the value in "
                    "the form below, or say absent if the document does not state it.")  # fmt: skip
        elif "at least one citation" in why:
            what = ("its status is present but it has no citations. Cite the ids of the "
                    "sentences that contain the value, or answer absent if no sentence states it.")  # fmt: skip
        else:
            what = f"normalized.{f} does not have the form below."
        ex = EXAMPLES.get(f)
        out.append(f"- {f}: {what} Form: {field_form(f)}." + (f" Example: {ex}" if ex else ""))  # fmt: skip
    return ("Some entries of your answer are not in the required form:\n" + "\n".join(out)
            + "\nReturn the whole answer again as one JSON object in the same form, with "
            "these entries fixed and every other entry unchanged.")  # fmt: skip


def valid_answer(text: str) -> list[dict] | None:
    """One row per field, or None when the text is not an answer (sv1 or sv2 shape)."""
    try:
        d = json.loads(text)
    except ValueError:
        return None
    return rows_of(d) if isinstance(d, dict) else None


def request_texts(row: ManifestRow, parts: list[Part], i: int, local: bool) -> tuple[str, str, str]:  # fmt: skip
    """System prompt, user prompt and part tag of part i. Every labeler gets the same
    prompt (sv4, D-54). With focused calls (config.LOCAL_FOCUSED, sv3-l1, D-53) the
    local labeler gets the same system prompt in every call, the document before the
    fields, and a tag that counts chunks of the document, not requests, so that every
    call on the same chunk starts with the same bytes (llama-server's prompt cache)."""
    part = parts[i]
    if not (local and config.LOCAL_FOCUSED):
        tag = f" (part {i + 1} of {len(parts)})" if len(parts) > 1 else ""
        return system_prompt(part.field_ids), user_prompt(row.doc_type, part.sentences, tag), tag  # fmt: skip
    chunks = list(dict.fromkeys(tuple(s.id for s in p.sentences) for p in parts))
    n = chunks.index(tuple(s.id for s in part.sentences))
    tag = f" (part {n + 1} of {len(chunks)})" if len(chunks) > 1 else ""
    return local_system_prompt(), local_user_prompt(row.doc_type, part.sentences, tag, part.field_ids), tag  # fmt: skip


# --- the pipeline ----------------------------------------------------------------------


def _default_factory(key: str) -> Provider:
    if key.startswith("local:"):
        return Local(key[6:])
    k = get_key(key)
    if not k:
        raise ProviderError("auth", f"no key for {key}")
    return Gemini(k) if key == "gemini" else Groq(k)


class Pipeline:
    def __init__(
        self,
        factory: Callable[[str], Provider] = _default_factory,
        ledger: Ledger | None = None,
        now: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        say: Callable[[str], None] = print,
    ) -> None:
        self.factory, self.now, self.sleep, self.say = factory, now, sleep, say
        self.ledger = ledger or Ledger()
        self._providers: dict[str, Provider] = {}
        self._limiters: dict[str, Limiter] = {}
        self.down: set[str] = set()  # cloud providers out for the rest of this run
        self.calls_left = 10**9

    def provider(self, key: str) -> Provider:
        if key not in self._providers:
            self._providers[key] = self.factory(key)
        return self._providers[key]

    def close(self) -> None:
        """Stop the local llama-server, if one was started."""
        for prov in self._providers.values():
            if isinstance(prov, Local):
                prov.close()

    def limiter(self, key: str) -> Limiter:
        if key not in self._limiters:
            cfg = cfg_for(key)
            self._limiters[key] = Limiter(cfg, self.ledger, self.now, self.sleep)
        return self._limiters[key]

    def _call(self, key: str, system: str, user: str, schema: dict | None, part: Part,
              first: Completion | None = None) -> dict:  # fmt: skip
        """One request with the retry rules. 503 / other 5xx, a per-minute 429 and
        network errors back off 30, 60, 120, 240 s (or the server's Retry-After) for up
        to ProviderCfg.max_tries tries (Gemini 3, others 5), then the chunk is `provider_unavailable` and the run moves on; the
        next run retries it. A daily-quota 429 stops the provider for the day. An
        answer cut off by the output cap fails at once (temperature 0: the same request
        gives the same answer). Without the shape check, an answer that is not JSON is
        asked once more. With it (`cfg.repair`: Gemini in JSON mode, D-49, and the local
        model, D-52) an answer with problems gets one repair request that sends them
        back, and the answer with fewer problems is kept. `first` is an answer already
        in the cache: it is checked like a fresh one and costs no request. Every try is
        a ledger line."""
        prov, lim = self.provider(key), self.limiter(key)
        tries = invalid = tok_in = tok_out = 0
        repair: tuple[str, str] | None = None  # (first answer, its problems)
        first_errors: list[str] = []

        timings: list[dict] = []  # llama-server's, one per request answered

        def done(text: str, **extra) -> dict:
            return {"status": "ok", "response": redact(text), "tokens_in": tok_in,
                    "tokens_out": tok_out, "attempts": tries, **extra,
                    **({"timings": timings} if timings else {})}  # fmt: skip

        def give_up(status: str, error: str) -> dict:
            if repair:  # the repair request failed: keep the first answer
                return done(repair[0], repair={"errors": first_errors, "failed": error})
            return {"status": status, "error": error, "attempts": tries}

        while True:
            if first is not None:
                c, first = first, None
            else:
                if self.calls_left <= 0:
                    raise OutOfCalls
                try:
                    lim.before(part.est_in() + part.max_out)
                except ValueError as e:  # one sentence too long for the provider
                    return give_up("failed", str(e))
                self.calls_left -= 1
                tries += 1
                try:
                    c = prov.complete(system, user, schema, part.max_out, repair)
                except ProviderError as e:
                    lim.record(prov.model, 0, 0, e.outcome)
                    if e.kind == "daily_quota":
                        lim.block_today()
                        raise DailyCap(key) from None
                    if e.kind not in ("server", "network", "rate_limit"):
                        return give_up("failed", str(e))
                    if tries >= min(cfg_for(key).max_tries, len(BACKOFF) + 1):
                        return give_up("provider_unavailable", str(e))
                    self.sleep(e.retry_after if e.retry_after else BACKOFF[tries - 1])
                    continue
                lim.record(prov.model, c.tokens_in, c.tokens_out, "ok")
            tok_in, tok_out = tok_in + c.tokens_in, tok_out + c.tokens_out
            if c.timings:
                timings.append({k: c.timings.get(k) for k in TIMING_KEYS})
            if c.truncated:
                r = give_up("failed", f"truncated at {c.tokens_out} output tokens (cap {part.max_out})")  # fmt: skip
                return {**r, "truncated": True, "tokens_out_cut": c.tokens_out}
            if cfg_for(key).repair:
                errs = shape_errors(c.text, part.field_ids)
                if errs and repair is None:
                    msg = plain_repair_message if prov.local else repair_message
                    first_errors, repair = errs, (c.text, msg(errs))
                    continue
                if repair is None:
                    return done(c.text)
                fixed_ok, first_ok = valid_answer(c.text) is not None, valid_answer(repair[0]) is not None  # fmt: skip
                if not (fixed_ok or first_ok):
                    return {"status": "failed", "error": "invalid JSON after repair", "attempts": tries}  # fmt: skip
                better = len(errs) <= len(first_errors) or not first_ok
                keep = c.text if fixed_ok and better else repair[0]
                return done(keep, repair={"errors": first_errors, "errors_after": errs,
                                          "kept": "repair" if keep is c.text else "first",
                                          "first_response": redact(repair[0])})  # fmt: skip
            if valid_answer(c.text) is not None:
                return done(c.text)
            invalid += 1  # answer discarded
            if invalid == 2:
                return {"status": "failed", "error": "invalid JSON", "attempts": tries}

    def split_retry(self, key: str, row: ManifestRow, part: Part, tag: str, first: dict) -> dict:  # fmt: skip
        """Groq answered `json_validate_failed` (its output broke the schema): ask once
        more as two requests with half the fields each (D-50). Each half keeps the
        whole part's output cap, so it has twice the room per field. The halves'
        answers are joined into one; if a half fails, the part fails with its error."""
        halves = []
        for g in field_groups(part.field_ids, 2):
            sub = Part(g, part.sentences, part.max_out, overhead(g))
            h = self._call(key, system_prompt(g), user_prompt(row.doc_type, part.sentences, tag),
                           response_schema(g), sub)  # fmt: skip
            halves.append(h)
            if h["status"] != "ok":
                break
        info = [{k: h.get(k) for k in ("status", "error", "tokens_in", "tokens_out", "attempts")} for h in halves]  # fmt: skip
        out = {"split_retry": {"first_error": first.get("error"), "halves": info},
               "attempts": first["attempts"] + sum(h["attempts"] for h in halves)}  # fmt: skip
        if len(halves) < 2 or halves[-1]["status"] != "ok":
            bad = halves[-1]
            return {**out, "status": bad["status"], "error": "split retry: " + str(bad.get("error"))}  # fmt: skip
        merged: dict = {"fields": {}, "normalized": {}}
        for h in halves:
            d = json.loads(h["response"])
            merged["fields"].update(d.get("fields") or {})
            merged["normalized"].update(d.get("normalized") or {})
        return {**out, "status": "ok", "response": json.dumps(merged, ensure_ascii=False),
                "tokens_in": sum(h["tokens_in"] for h in halves),
                "tokens_out": sum(h["tokens_out"] for h in halves)}  # fmt: skip

    def label(self, row: ManifestRow, ja: list[Sentence], key: str,
              retry_failed: bool = False) -> dict:  # fmt: skip
        """Run (or resume) one labeler over one document. Returns the raw cache dict.
        Parts that are ok are never asked again; `provider_unavailable` parts are
        always retried, `failed` ones (invalid JSON, bad request) only with
        retry_failed. A Groq part that failed by truncation and was never split is
        split straight from the cache by the next run (D-59), without asking the
        whole part again."""
        prov = self.provider(key)
        cfg = cfg_for(key)
        path = raw_path(row.doc_id, "local" if prov.local else prov.name, prov.model)
        raw = load_raw(path)
        parts = plan_parts(row, ja, cfg)
        raw.update(provider=cfg.name, model=prov.model, n_chunks=len(parts),
                   prompt_version=prompt_for(cfg.name))  # fmt: skip
        for i, part in enumerate(parts):
            done = raw["chunks"].get(str(i))
            pending_split = bool(done) and splittable(cfg, part, done)
            if done and not pending_split and (done["status"] == "ok" or (done["status"] == "failed" and not retry_failed)):  # fmt: skip
                continue
            system, user, tag = request_texts(row, parts, i, prov.local)
            t0 = time.monotonic()
            schema = response_schema(part.field_ids) if cfg.strict_schema else None
            r = done if pending_split else self._call(key, system, user, schema, part)
            assert r is not None
            if splittable(cfg, part, r):
                r = self.split_retry(key, row, part, tag, r)
            r["seconds"] = round(time.monotonic() - t0, 1)  # waits and retries included
            r["max_out"] = part.max_out
            r["sentence_ids"] = [s.id for s in part.sentences]
            r["field_ids"] = part.field_ids
            r["date"] = datetime.fromtimestamp(self.now(), UTC).date().isoformat()
            raw["chunks"][str(i)] = r
            _write(path, json.dumps(raw, ensure_ascii=False))
            self.say(f"  {row.doc_id[:12]} {cfg.name} part {i + 1}/{len(parts)} "
                     f"{r['status']} in={r.get('tokens_in', '-')} out={r.get('tokens_out', '-')}")  # fmt: skip
            if r["status"] == "provider_unavailable" and not prov.local:
                # one document spent the whole backoff: more tries would only burn the
                # daily request budget, so the provider sits out the rest of this run
                self.down.add(key)
                self.say(f"{key}: backoff used up, paused for the rest of this run (the other provider goes on)")  # fmt: skip
                break
        return raw

    def repair_cached(self, row: ManifestRow, ja: list[Sentence], key: str) -> list[dict]:  # fmt: skip
        """Run the shape check on answers cached before it existed and send the repair
        request where it finds problems (D-52): no full re-run. A part that already
        went through the check (it has `repair` or `shape_checked`) is skipped. Returns
        one dict per part checked: fields with problems before and after, kept, seconds."""
        prov = self.provider(key)
        path = raw_path(row.doc_id, "local" if prov.local else prov.name, prov.model)
        raw = load_raw(path)
        parts = plan_parts(row, ja, cfg_for(key))
        out = []
        for i, part in enumerate(parts):
            ch = raw["chunks"].get(str(i))
            if (
                not ch
                or ch["status"] != "ok"
                or "repair" in ch
                or ch.get("shape_checked")
            ):
                continue
            assert ch["field_ids"] == part.field_ids, "the plan changed since this answer was cached"  # fmt: skip
            system, user, _ = request_texts(row, parts, i, prov.local)
            schema = (
                response_schema(part.field_ids) if cfg_for(key).strict_schema else None
            )
            t0 = time.monotonic()
            r = self._call(key, system, user, schema, part,
                           Completion(ch["response"], ch["tokens_in"], ch["tokens_out"]))  # fmt: skip
            secs = round(time.monotonic() - t0, 1)
            if "repair" in r:  # what the repair request alone cost
                r["repair"].update(seconds=secs, tokens_in=r["tokens_in"] - ch["tokens_in"],
                                   tokens_out=r["tokens_out"] - ch["tokens_out"])  # fmt: skip
                ch = {**ch, **r, "attempts": ch.get("attempts", 1) + r["attempts"],
                      "seconds": ch.get("seconds", 0) + secs}  # fmt: skip
            else:
                ch = {**ch, "shape_checked": True}
            raw["chunks"][str(i)] = ch
            _write(path, json.dumps(raw, ensure_ascii=False))
            rep = ch.get("repair", {})
            out.append({"part": i, "before": sorted({e.split(":")[0] for e in rep.get("errors", [])}),
                        "after": sorted({e.split(":")[0] for e in rep.get("errors_after", rep.get("errors", []))}),
                        "kept": rep.get("kept", rep.get("failed", "-")), "seconds": secs})  # fmt: skip
        return out


def splittable(cfg: ProviderCfg, part: Part, r: dict) -> bool:
    """A failed Groq part that gets the half-split retry (D-50): its answer broke the
    schema (json_validate_failed) or was cut off by the output cap (truncated, D-59).
    Each half keeps the whole part's cap, so it has twice the room per field. Not for
    a part already split, nor for Gemini or the local model."""
    return (
        cfg.name == "groq"
        and r.get("status") == "failed"
        and len(part.field_ids) > 1
        and "split_retry" not in r
        and (
            "json_validate_failed" in str(r.get("error", ""))
            or bool(r.get("truncated"))
        )
    )


def raw_state(raw: dict) -> str:
    """complete | failed | unavailable | pending"""
    chunks = raw.get("chunks", {})
    states = {c["status"] for c in chunks.values()}
    if "failed" in states:
        return "failed"
    if "provider_unavailable" in states:
        return "unavailable"
    return (
        "complete"
        if raw.get("n_chunks") and len(chunks) == raw["n_chunks"]
        else "pending"
    )


def answers(raw: dict, labeler: str, field_ids: list[str], by_id: dict[str, Sentence] | None = None) -> dict[str, Candidate]:  # fmt: skip
    """Merge the part answers of one labeler into one candidate per field. `by_id`
    (the document's sentences) lets a scalar conflict be settled by heading cues."""
    per: dict[str, list[Candidate]] = {f: [] for f in field_ids}
    known = set(FIELD_IDS)
    for i in sorted(raw["chunks"], key=int):
        ch = raw["chunks"][i]
        if ch["status"] != "ok":
            continue
        seen: set[str] = set()
        for r in valid_answer(ch["response"]) or []:
            f = r.get("field")
            if f in known and f not in seen:
                seen.add(f)
                per.setdefault(f, []).append(from_row(r, labeler))
    return {f: merge(f, cs, labeler, by_id or {}) for f, cs in per.items()}


def cue_score(c: Candidate, by_id: dict[str, Sentence]) -> int:
    """How many of the field's heading cues stand at a heading of a cited sentence."""
    cited = [by_id[i] for i in c.citations if i in by_id]
    return sum(any(cue_at_heading(k, s) for s in cited) for k in BY_ID[c.field].cues)


def merge(field: str, cs: list[Candidate], labeler: str, by_id: dict[str, Sentence] | None = None) -> Candidate:  # fmt: skip
    """One candidate per field from the answers of the parts (chunks) of a document.

    - Absent in one part and present in another is present.
    - List fields: the union of the parts' items, deduplicated by citation overlap
      and value (agree.item_same).
    - Scalars: parts that agree are one answer; the one whose citations sit under the
      field's heading cues best is kept (ties: the earlier part). Parts that disagree
      are kept as `alternatives`, and the field is flagged for review. That is never a
      schema failure. A part whose answer did not parse is ignored when another part
      gave a clean answer."""
    if not cs:
        return Candidate(
            field, parse_error="field missing from the answer", labeler=labeler
        )
    live = [c for c in cs if c.status != "absent"]
    if not live:
        return cs[0]
    live = [c for c in live if not c.parse_error] or live
    if len(live) == 1:
        return live[0]
    if BY_ID[field].kind == "list" and all(c.status == "present" for c in live):
        items = union_items(
            field, [(c.normalized or {}).get("items", []) for c in live]
        )
        return from_row({"field": field, "status": "present", "normalized": {"items": items},
                         "value_ja": "", "value_en": live[0].value_en or "", "citations": [],
                         "reason": live[0].reason}, labeler)  # fmt: skip
    ranked = sorted(
        live, key=lambda c: -cue_score(c, by_id or {})
    )  # stable: earlier part wins ties
    distinct: list[Candidate] = []
    for c in ranked:
        if not any(agree(c, d)[0] for d in distinct):
            distinct.append(c)
    best = distinct[0]
    best.alternatives = distinct[1:]
    return best


# --- resolution ------------------------------------------------------------------------


def cue_present(sentences: list[Sentence], field: str) -> str | None:
    """A heading cue of the field that makes "both absent" doubtful: at a section title
    or the first 15 characters of a Japanese sentence, not inside a longer word
    (担当 in 支出負担行為担当官). Cues of 3 characters or fewer (担当, 質問, 概要) count
    only when they are the whole heading."""
    for cue in BY_ID[field].cues:
        short = len(cue) <= SHORT_CUE
        for s in sentences:
            if s.language != "ja":
                continue
            if cue_is_heading(cue, s) if short else cue_at_heading(cue, s):
                return cue
    return None


def spot_checked(doc_id: str, field: str) -> bool:
    h = hashlib.sha256(f"{config.SPOT_CHECK_SEED}:{doc_id}:{field}".encode()).digest()
    return h[0] * 256 + h[1] < 65536 * config.SPOT_CHECK_PERCENT / 100


@dataclass
class Resolved:
    field: str
    state: str  # accepted | flagged | rule_absent
    line: dict | None  # label line when accepted / rule_absent
    reasons: list[str]
    sides: list[dict]  # [{labeler, candidate, checks}] for the review export
    agreement: bool | None
    spot: bool = False


def cand_dict(c: Candidate) -> dict:
    d = {"status": c.status, "value_ja": c.value_ja, "value_en": c.value_en,
         "normalized": c.normalized, "citations": c.citations,
         "labeler": c.labeler, "parse_error": c.parse_error}  # fmt: skip
    if c.alternatives:
        d["alternatives"] = [cand_dict(x) for x in c.alternatives]
    return d


def label_line(row: ManifestRow, c: Candidate | None, field: str, prov: dict) -> dict:
    base = {"doc_id": row.doc_id, "extractor_version": EXTRACTOR_VERSION,
            "schema_version": SCHEMA_VERSION, "field": field}  # fmt: skip
    if c is None or c.status == "absent":
        return {**base, "status": "absent", "value_ja": None, "normalized": None,
                "value_en": None, "citations": [], "provenance": prov}  # fmt: skip
    return {**base, "status": c.status, "value_ja": c.value_ja, "normalized": c.normalized,
            "value_en": c.value_en, "citations": c.citations, "provenance": prov}  # fmt: skip


def provenance(labelers: list[tuple[str, ...]], agreement: bool | None,
               checks: list[tuple[str, bool]], overlap: bool, **kw) -> dict:  # fmt: skip
    """`labelers`: (provider, model, date, prompt_version) per pre-labeler; the
    version is each labeler's own (D-54). A 3-tuple (an item stored before D-54) gets
    the line's prompt_version."""
    line_prompt = kw.get("prompt_version", PROMPT_VERSION)
    return {
        "pre_labelers": [
            {
                "provider": x[0],
                "model": x[1],
                "date": x[2],
                "prompt_version": x[3] if len(x) > 3 else line_prompt,
            }
            for x in labelers
        ],  # fmt: skip
        "agreement": agreement,
        "auto_checks": [{"name": n, "passed": v} for n, v in checks],
        "reviewed_by": kw.get("reviewed_by"),
        "review_note": kw.get("review_note"),
        "final_state": kw.get("final_state", "silver_consensus"),
        "prompt_version": line_prompt,
        "labeler_overlap": overlap,
        "reviewed_choice": kw.get("reviewed_choice"),
    }


def resolve(
    row: ManifestRow,
    sentences: list[Sentence],
    cands: list[dict[str, Candidate]],
    labelers: list[tuple[str, ...]],
    overlap: bool,
    rules: frozenset[str] | None = None,
) -> list[Resolved]:
    """One decision per v1 field. `cands` has one dict per slot, in SLOTS order: A is the
    cloud provider, B the local model (sv3; in sv1 and sv2 A was gemini, B groq). `rules`: agreement relaxations,
    agree.ACTIVE when None (the replay passes others)."""
    by_id = {s.id: s for s in sentences}
    en_text = " ".join(s.text_orig for s in sentences if s.language == "en")
    out: list[Resolved] = []
    for f in FIELD_IDS:
        if row.doc_type not in BY_ID[f].applies_to:
            extras = [d[f] for d in cands if f in d and d[f].status != "absent"]
            if extras:
                sides = [{"labeler": c.labeler, "candidate": cand_dict(c), "checks": []} for c in extras]  # fmt: skip
                out.append(Resolved(f, "flagged", None, [f"answered for a field that does not apply to {row.doc_type}"], sides, None))  # fmt: skip
                continue
            prov = provenance([], None, [("field_not_applicable_rule", True)], False, final_state="silver_unreviewed")  # fmt: skip
            out.append(Resolved(f, "rule_absent", label_line(row, None, f, prov), [], [], None))  # fmt: skip
            continue
        a, b = (d[f] for d in cands)
        checks = [run_checks(c, row, by_id, en_text) for c in (a, b)]
        ok, why = agree(a, b, rules)
        reasons = [] if ok else [f"disagree: {why}"]
        for name, c in (("A", a), ("B", b)):
            if c.alternatives:
                reasons.append(f"{name}: parts of the document give different answers")
        for name, c, ch in (("A", a, checks[0]), ("B", b, checks[1])):
            reasons += [f"{name} failed {n}" + (f" ({c.check_notes['schema_valid']})" if n == "schema_valid" and c.check_notes.get("schema_valid") else "") for n in failed(ch, BLOCKING)]  # fmt: skip
        if ok and a.status == "absent" and not reasons:
            cue = cue_present(sentences, f)
            if cue:
                reasons.append(f"both absent but heading cue {cue} is in the document")
        sides = [{"labeler": c.labeler, "candidate": cand_dict(c), "checks": ch}
                 for c, ch in zip((a, b), checks, strict=True)]  # fmt: skip
        if reasons:
            out.append(Resolved(f, "flagged", None, reasons, sides, ok))
            continue
        pick, pc = (a, checks[0]) if not failed(checks[0], BLOCKING) else (b, checks[1])
        prov = provenance(labelers, True, pc, overlap)
        line_ = label_line(row, pick, f, prov)
        try:
            LabelLine.model_validate(line_)
        except ValidationError as e:
            out.append(Resolved(f, "flagged", None, ["label invalid: " + e.errors()[0]["msg"]], sides, ok))  # fmt: skip
            continue
        out.append(
            Resolved(f, "accepted", line_, [], sides, True, spot_checked(row.doc_id, f))
        )
    return out


# --- stores ----------------------------------------------------------------------------


def resolved_path(doc_id: str) -> Path:
    return config.CACHE / "resolved" / f"{doc_id}.jsonl"


def decisions_path(doc_id: str) -> Path:
    return config.CACHE / "decisions" / f"{doc_id}.json"


def read_resolved(doc_id: str) -> dict[str, dict]:
    p = resolved_path(doc_id)
    if not p.exists():
        return {}
    lines = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    return {ln["field"]: ln for ln in lines}


def labeled_by_earlier_prompt(doc_id: str) -> bool:
    """The document has labels made with another prompt version. Such a document is
    never resolved again by this version; run compares instead (comparison mode)."""
    return any(
        ln["provenance"].get("prompt_version") != PROMPT_VERSION
        for ln in read_resolved(doc_id).values()
    )


def write_resolved(doc_id: str, lines: dict[str, dict]) -> None:
    ordered = [lines[f] for f in FIELD_IDS if f in lines]
    _write(resolved_path(doc_id), "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in ordered))  # fmt: skip


def label_file(row: ManifestRow, splits: dict[str, str]) -> Path:
    """D-24: open documents under data/eval/, the rest under data/eval_private/."""
    root = EVAL_DIR if row.license_class == "open" else PRIVATE_DIR
    return root / splits[row.issuer_org] / "labels" / f"{row.doc_id}.jsonl"


def materialize(row: ManifestRow, splits: dict[str, str]) -> Path | None:
    """Write the label file once all 23 fields are resolved; None until then."""
    lines = read_resolved(row.doc_id)
    if set(lines) != set(FIELD_IDS):
        return None
    path = label_file(row, splits)
    _write(
        path,
        "".join(json.dumps(lines[f], ensure_ascii=False) + "\n" for f in FIELD_IDS),
    )
    return path


def rebuild_flagged() -> int:
    """data/cache/labeling/flagged.jsonl = every document's open flagged / spot items."""
    items: list[str] = []
    for p in sorted((config.CACHE / "decisions").glob("*.json")):
        d = json.loads(p.read_text())
        items += [json.dumps(x, ensure_ascii=False) for x in d["items"]]
    _write(config.CACHE / "flagged.jsonl", "".join(x + "\n" for x in items))
    return len(items)


def store_resolution(row: ManifestRow, res: list[Resolved], labelers: list, splits: dict) -> Path | None:  # fmt: skip
    """Accepted and rule-absent lines go to the resolved store (never over a reviewed
    line); flagged fields and 5% of accepted ones become review items."""
    have = read_resolved(row.doc_id)
    items = []
    for r in res:
        prev = have.get(r.field, {}).get("provenance", {})
        if prev.get("reviewed_by"):
            continue  # a reviewed line is never replaced by a re-run
        if r.line:
            have[r.field] = r.line
        else:
            have.pop(r.field, None)
        if r.state == "flagged" or r.spot:
            items.append({"doc_id": row.doc_id, "field": r.field,
                          "kind": "flagged" if r.state == "flagged" else "spot",
                          "reasons": r.reasons or ["consensus spot-check"],
                          "sides": r.sides, "agreement": r.agreement,
                          "labelers": labelers, "prompt_version": PROMPT_VERSION})  # fmt: skip
    write_resolved(row.doc_id, have)
    _write(decisions_path(row.doc_id), json.dumps({"items": items}, ensure_ascii=False))
    rebuild_flagged()
    return materialize(row, splits)
