# ruff: noqa: E501
"""Providers, limits, paths and versions for the silver-label pipeline (D-42 to D-50)."""

from dataclasses import dataclass
from pathlib import Path

# Bump on any change to the prompt, the response schema or the chunking: cached raw
# answers are keyed by it, and every label records it.
PROMPT_VERSION = "sv4"
# The local labeler's prompt version (D-53 kept the mechanism; sv4 brings every labeler
# back to one version, D-54). With LOCAL_FOCUSED (`--local-focused`) the local labeler
# asks its list fields and contact one per call, under LOCAL_PROMPT_VERSION +
# FOCUSED_SUFFIX, so those answers are cached apart. Every pre_labelers entry records
# its own labeler's version.
LOCAL_PROMPT_VERSION = "sv4"
FOCUSED_SUFFIX = "-l1"
LOCAL_FOCUSED = False
CACHE = Path(
    "data/cache/labeling"
)  # gitignored: raw answers hold restricted-document text
SPOT_CHECK_SEED = 20261004
SPOT_CHECK_PERCENT = 5
# The two voices of every consensus (sv3, D-50): A is a cloud provider (Gemini for open
# documents, Groq for the rest), B the local model. pipeline.assign fills them.
SLOTS = ("A", "B")
CHUNK_OVERLAP = 2  # sentences repeated when one top-level section has to be split


@dataclass(frozen=True)
class ProviderCfg:
    name: str
    model: str
    family: str  # model family; the local fallback must differ from the remaining one
    may_train_on_inputs: bool | None  # D-42; None = unknown
    # Free-tier limits. None = not published by the provider (see `published`).
    rpm: int
    tpm: int
    rpd: int
    tpd: int | None
    published: bool
    request_cap: int  # largest input + output the provider accepts in one request
    max_out: int  # max_completion_tokens / maxOutputTokens sent
    # False: JSON mode, the answer shape is described in the prompt and checked by our
    # code, with one repair request (D-49). True: the provider's strict schema mode.
    strict_schema: bool = True
    # Share of max_out one answer's estimated output may use (est_output). Fields are
    # cut into groups until every group fits.
    out_share: float = 1.0
    # Our shape check (checks.shape_errors) runs on every answer, and an answer with
    # problems gets one repair request (D-49 for Gemini, D-52 for the local model).
    repair: bool = False
    # The time zone of the provider's quota day (D-57). Google resets the Gemini API's
    # free daily quota at midnight Pacific time: on 2026-10-03 (Pacific) the 22nd
    # request got the daily-quota 429, with 21 requests across two UTC days.
    quota_tz: str = "UTC"
    # Tries per request on 503 / other 5xx, per-minute 429 and network errors, with the
    # pipeline's BACKOFF waits between them. Gemini: 3, since failed requests count
    # against its 20 a day (D-57, D-58).
    max_tries: int = 5


PROVIDERS: dict[str, ProviderCfg] = {
    "gemini": ProviderCfg(
        "gemini", "gemini-3.8-flash", "google", True,
        # ASSUMED: Google's docs only point to the AI Studio dashboard. Override in
        # data/cache/labeling/limits.json once you have read your own numbers.
        rpm=10, tpm=250_000, rpd=250, tpd=None, published=False,
        request_cap=200_000, max_out=16_384,
        # strict mode refused the 21- and 23-field schemas with HTTP 400 (D-48)
        strict_schema=False, repair=True, quota_tz="America/Los_Angeles", max_tries=3,
    ),
    "groq": ProviderCfg(
        "groq", "openai/gpt-oss-120b", "openai", False,
        # console.groq.com/docs/rate-limits, free plan. The account's own limits page is
        # authoritative.
        rpm=30, tpm=8_000, rpd=1_000, tpd=200_000, published=True,
        request_cap=8_000, max_out=4_000,
    ),
}  # fmt: skip

# Local fallback (D-45): first model whose family differs from the remaining provider's.
LOCAL_MODELS = (
    ("Qwen3.5-9B-Q4_K_M.gguf", "qwen"),
    ("gemma-4-E4B-it-Q4_K_M.gguf", "google"),
)
LOCAL_CTX = 32_768
# Output cap of one local answer, lowered further when the context has less room
# (pipeline.max_out_for). 8,192 fits every dev document (largest input ~22k estimated
# tokens) and bounds a runaway answer to ~22 min at 6 tokens/s.
LOCAL_MAX_OUT = 8_192
LOCAL_OUT_SHARE = 0.6  # an answer's estimated output stays under 60% of the cap (D-50)

# Tier 1 fields come first in the review export (they cost the bidder the most).
TIER1 = (
    "deadlines", "submission_modes", "bid_bond", "performance_bond", "eligibility",
    "unified_qualification", "tax_basis", "spec_access", "procurement_type",
    "award_method",
)  # fmt: skip

# Fuzzy thresholds for text agreement (difflib ratio on normalized text), D-43.
FUZZY_SHORT = 0.85  # title, issuer_org, delivery_location, names, list item names
FUZZY_LONG = 0.60  # scope_summary, eligibility item text

# The pilot (open dev documents only; doc id prefixes). dev has no open notice from a PDF
# source, so the third notice is a 和歌山県 tender page saved as HTML (D-43).
PILOT = (
    "f19cddbd4cba",  # notice, p-portal HTML, English Summary (法務省)
    "563042df9941",  # notice, p-portal HTML, no Summary (内閣府)
    "4b0b9d8229c7",  # notice, 和歌山県 HTML (no PDF-source open notice in dev)
    "28ad40ea4b1f",  # bid_instructions, 和歌山県 PDF
    "4c40bbd831fe",  # spec, 和歌山県 PDF (long enough to be split for Groq)
)
