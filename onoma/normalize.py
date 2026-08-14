"""Deterministic normalization — the layer everything else builds on.

Separated from matching on purpose. Normalization answers "what is the
comparable form of this string", matching answers "are these the same
entity". Conflating them is how the implementations this library
replaces ended up mutually incompatible: each folded a slightly
different set of transformations into its own match function, so two
callers comparing the same pair could disagree.
"""

from __future__ import annotations

import re
import unicodedata

from unidecode import unidecode

# Tokens that carry no identifying signal in an organisation name. A
# shared token from this set is not evidence two names refer to the same
# entity — "COLLINS FOR VICTORY" and "COLLINS FOR SENATOR" share "for"
# and a surname without being the same committee.
GENERIC_ORG_TOKENS = frozenset({
    "the", "of", "for", "and", "a", "an",
    "committee", "commitee", "cmte", "pac", "fund", "funds",
    "political", "action", "campaign", "victory", "leadership",
    "friends", "citizens", "people", "americans", "our",
    "inc", "llc", "llp", "lp", "ltd", "corp", "corporation", "co",
    "association", "assn", "society", "group", "trust",
})

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def fold(text: str | None) -> str:
    """Casefold, strip diacritics and punctuation, collapse whitespace.

    Diacritics are folded because sources disagree about them for the
    same person — a legislator recorded as "Luján" in one system appears
    as "Lujan" in another, and neither is wrong.
    """
    if not text:
        return ""
    # NFKC first so composed and decomposed forms agree before transliteration.
    text = unicodedata.normalize("NFKC", text)
    text = unidecode(text)
    text = _PUNCT.sub(" ", text.lower())
    return _SPACE.sub(" ", text).strip()


def tokens(text: str | None) -> list[str]:
    """Folded tokens, order preserved, single characters dropped.

    Single characters are dropped because they are almost always middle
    initials, which vary by source for the same person and would
    otherwise defeat an exact comparison.
    """
    return [t for t in fold(text).split() if len(t) > 1]


def is_generic_org_token(token: str) -> bool:
    return token in GENERIC_ORG_TOKENS
