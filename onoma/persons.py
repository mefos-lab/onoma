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

from functools import lru_cache

from nameparser import HumanName
from nicknames import NickNamer

from .normalize import fold, tokens

_PREFIX_MIN = 3

# Titles nameparser does not strip on its own. It handles "Sen." and
# "The Honorable"; spelled-out legislative forms it parses as name
# tokens, which then defeat comparison.
_EXTRA_TITLES = (
    "u s representative", "us representative", "representative",
    "u s senator", "us senator", "senator", "congressman",
    "congresswoman", "delegate", "resident commissioner",
)


@lru_cache(maxsize=1)
def _namer() -> NickNamer:
    return NickNamer()


def strip_titles(name: str) -> str:
    """Remove honorifics and offices, returning the personal name.

    Parses before folding. nameparser identifies abbreviated titles by
    their trailing period ("Sen.", "Rep."), so folding punctuation away
    first makes them unrecognisable and they survive as name tokens.
    """
    parsed = HumanName(name or "")
    kept = " ".join(p for p in (parsed.first, parsed.middle, parsed.last) if p)
    folded = fold(kept) if kept else fold(name)
    for title in _EXTRA_TITLES:
        if folded.startswith(title + " "):
            folded = folded[len(title) + 1:]
            break
    parsed = HumanName(folded)
    parts = [p for p in (parsed.first, parsed.middle, parsed.last) if p]
    # nameparser occasionally yields nothing useful for unusual inputs;
    # falling back to the folded string is better than returning empty.
    return " ".join(parts) if parts else folded


def given_name_variants(given: str) -> set[str]:
    """A given name plus its documented nickname/canonical equivalents."""
    g = fold(given)
    if not g:
        return set()
    namer = _namer()
    out = {g}
    out |= {fold(x) for x in namer.canonicals_of(g)}
    out |= {fold(x) for x in namer.nicknames_of(g)}
    return {x for x in out if x}


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
    if given_name_variants(fa) & given_name_variants(fb):
        return True
    long, short = (fa, fb) if len(fa) >= len(fb) else (fb, fa)
    return len(short) >= _PREFIX_MIN and long.startswith(short)


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
