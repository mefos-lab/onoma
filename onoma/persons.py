"""Person names — titles, given-name variants, comparison.

The variant problem has two distinct halves that need different
treatment, and collapsing them is why a single heuristic kept failing:

- **Truncations** ("Chris" for "Christopher") are prefix relationships,
  reachable by rule.
- **Nicknames** ("Bob" for "Robert", "Lizzie" for "Elizabeth") are not.
  No rule derives one from the other; it needs a lookup table.

Prefix matching alone silently loses the second half.
"""

from __future__ import annotations

import re
from functools import lru_cache

from nameparser import HumanName
from nicknames import NickNamer

from .normalize import fold, tokens

_PREFIX_MIN = 3
_EDIT_MIN_LEN = 5


def _within_one_edit(a: str, b: str) -> bool:
    """True if one insertion, deletion or substitution turns a into b."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = sum(1 for x, y in zip(a, b) if x != y)
        return diffs == 1
    long, short = (a, b) if len(a) > len(b) else (b, a)
    i = j = 0
    skipped = False
    while i < len(long) and j < len(short):
        if long[i] != short[j]:
            if skipped:
                return False
            skipped = True
            i += 1
            continue
        i += 1
        j += 1
    return True

# Titles nameparser does not strip on its own. It handles "Sen." and
# "The Honorable"; spelled-out legislative forms it parses as name
# tokens, which then defeat comparison.
_EXTRA_TITLES = (
    # Longest first: "majority leader" must be stripped before "leader"
    # could match its tail.
    "assistant democratic leader", "assistant republican leader",
    "u s representative", "us representative", "representative",
    "u s senator", "us senator", "senator",
    # Abbreviated forms survive folding as "u s rep" / "u s sen",
    # so they need their own entries.
    "u s rep", "us rep", "u s sen", "us sen",
    "speaker of the house", "majority leader", "minority leader",
    "majority whip", "minority whip", "president pro tempore",
    "congressman", "congresswoman", "delegate",
    "resident commissioner", "speaker", "leader", "whip", "chairman",
    "chairwoman", "chair", "governor", "candidate",
)


@lru_cache(maxsize=1)
def _namer() -> NickNamer:
    return NickNamer()


_ANNOTATION = re.compile(
    r"\s*\([^)]*\)"          # "(D-CA-38)" — party and district
    r"|\s*,\s*(?:u\.?s\.?\s*)?(?:senate|house|congressional)\b.*$"
    r"|\s*,\s*candidate\b.*$"   # ", Candidate for U.S. House..."
    r"|\s*,\s*(?:d|r|i)-[a-z]{2}\b.*$",  # ", D-CA"
    re.IGNORECASE,
)


def _drop_annotations(name: str) -> str:
    """Remove trailing role and district annotations.

    Filings append context to a name — a party/district code, or the
    office someone is separately seeking. It is not part of the name and
    defeats parsing when left in place.
    """
    return _ANNOTATION.sub("", name).strip(" ,")


@lru_cache(maxsize=8192)
def strip_titles(name: str) -> str:
    """Remove honorifics and offices, returning the personal name.

    Parses before folding. nameparser identifies abbreviated titles by
    their trailing period ("Sen.", "Rep."), so folding punctuation away
    first makes them unrecognisable and they survive as name tokens.

    Cached because callers compare one query against a whole corpus, so
    the same strings recur constantly. HumanName parsing dominates the
    cost of this module, and it is pure, so caching is free correctness-
    wise. A second parse pass was removed for the same reason: the
    spelled-out office prefixes are stripped from the folded string
    directly rather than by re-parsing it.
    """
    name = _drop_annotations(name or "")
    parsed = HumanName(name)
    kept = " ".join(p for p in (parsed.first, parsed.middle, parsed.last) if p)
    folded = fold(kept) if kept else fold(name)
    for title in _EXTRA_TITLES:
        if folded.startswith(title + " "):
            return folded[len(title) + 1:]
    return folded


@lru_cache(maxsize=8192)
def _variants_cached(given: str) -> frozenset[str]:
    """Cached inner form; see :func:`given_name_variants`."""
    namer = _namer()
    out = {given}
    out |= {fold(x) for x in namer.canonicals_of(given)}
    out |= {fold(x) for x in namer.nicknames_of(given)}
    return frozenset(x for x in out if x)


def given_name_variants(given: str) -> set[str]:
    """A given name plus its documented nickname/canonical equivalents."""
    g = fold(given)
    return set(_variants_cached(g)) if g else set()


def given_names_match(a: str, b: str) -> bool:
    """True if two given names plausibly denote the same person.

    Accepts exact match, a shared nickname/canonical form, or a prefix
    relationship of at least three characters. Prefix length is floored
    to keep initials and very short fragments from matching broadly.
    """
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return False
    if fa == fb:
        return True
    # Direct linkage only: one name must be a recorded nickname *of the
    # other*. Intersecting the two variant sets instead would make any
    # two nicknames of a shared canonical equivalent — "Tina" and
    # "Chris" are both nicknames of "Christina", which would wrongly
    # equate Tina Smith with Chris Smith. Sharing a canonical is not
    # identity.
    namer = _namer()
    if fb in {fold(x) for x in namer.canonicals_of(fa)}:
        return True
    if fa in {fold(x) for x in namer.canonicals_of(fb)}:
        return True
    if fb in {fold(x) for x in namer.nicknames_of(fa)}:
        return True
    if fa in {fold(x) for x in namer.nicknames_of(fb)}:
        return True
    long, short = (fa, fb) if len(fa) >= len(fb) else (fb, fa)
    if len(short) >= _PREFIX_MIN and long.startswith(short):
        return True
    # Single-character spelling variance in a given name, e.g.
    # "Shelly"/"Shelley" or "Lindsay"/"Lindsey". Sources disagree on
    # these for the same person. Admitted only for names long enough
    # that one edit is a small proportion of the string, and callers
    # reach this only when the surname already matched exactly, which
    # is what keeps it from being loose.
    if min(len(fa), len(fb)) >= _EDIT_MIN_LEN and _within_one_edit(fa, fb):
        return True
    return False


def same_person(a: str, b: str) -> bool:
    """Compare two personal names after stripping titles.

    Requires the surname to match exactly. Surnames are the stable part
    of a person's name across sources; given names vary far more, so
    relaxing the surname is where false positives come from.
    """
    ta, tb = tokens(strip_titles(a)), tokens(strip_titles(b))
    if not ta or not tb:
        return False
    if ta[-1] != tb[-1]:
        return False
    if len(ta) == 1 or len(tb) == 1:
        return True          # surname-only on one side: as much as can be said
    return given_names_match(ta[0], tb[0])
