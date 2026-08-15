"""Is this string a person, an organisation, or neither?

Corpora of "names" are rarely uniformly people. A field nominally
holding a legislator's name also holds party committees (DCCC),
caucus PACs (Congressional Black Caucus PAC), fundraising vehicles
("Friends of David Schweikert"), events ("1.29.25 DSCC Event") and
placeholders ("General Fund").

Attempting person matching on those and reporting the failures as an
unresolved rate measures the wrong thing: they are not unmatched
people, they are not people. Classifying first lets a caller report
"of N names, X were organisations and Y of the remaining Z people
resolved", which is the honest denominator.

This is heuristic and intentionally conservative. UNKNOWN is a real
answer and callers should treat it as "try person matching, but do not
be surprised by a miss".
"""

from __future__ import annotations

from enum import Enum

from .normalize import fold

# Tokens that only appear in organisation names in this domain.
_ORG_MARKERS = frozenset({
    "pac", "committee", "commitee", "cmte", "caucus", "party", "fund",
    "association", "council", "coalition", "alliance", "institute",
    "society", "federation", "union", "conference", "foundation",
    "corporation", "corp", "inc", "llc", "llp", "ltd", "company",
    "dccc", "dscc", "nrcc", "nrsc", "dnc", "rnc", "actblue", "winred",
    "event", "reception", "dinner", "breakfast", "luncheon",
    "women", "men", "leaders", "majority", "democrats", "republicans",
})

# Multi-word shapes that mark a campaign or fundraising vehicle rather
# than a person, even though a person's name is embedded in them.
_ORG_PHRASES = (
    "friends of", "committee to elect", "people for", "citizens for",
    "for congress", "for senate", "for america", "for maryland",
    "victory fund", "leadership pac", "campaign committee",
    "members of", "democratic members", "republican members",
    "elect ", "re elect", "vote for",
)

# Words marking a person who holds or seeks office but is described
# rather than named — still a person, just not necessarily seated.
_PERSON_MARKERS = frozenset({
    "sen", "senator", "rep", "representative", "congressman",
    "congresswoman", "gov", "governor", "delegate", "candidate",
    "hon", "honorable", "dr", "mr", "mrs", "ms",
})


class NameKind(str, Enum):
    PERSON = "person"
    ORGANISATION = "organisation"
    UNKNOWN = "unknown"


def classify(name: str | None) -> NameKind:
    """Best-effort classification of a name string.

    Organisation markers win over person markers, because a name can
    contain both — "Democratic Members of House Committee on Ways and
    Means" and "Friends of David Schweikert" each embed person-ish
    language inside something that is plainly not one person.
    """
    folded = fold(name)
    if not folded:
        return NameKind.UNKNOWN

    if any(phrase in folded for phrase in _ORG_PHRASES):
        return NameKind.ORGANISATION

    tokens = set(folded.split())
    if tokens & _ORG_MARKERS:
        return NameKind.ORGANISATION

    # A leading date or number is a filing artefact, not a name.
    first = folded.split()[0]
    if any(ch.isdigit() for ch in first):
        return NameKind.ORGANISATION

    if tokens & _PERSON_MARKERS:
        return NameKind.PERSON

    # Two or three plain words is the shape of a personal name.
    words = folded.split()
    if 2 <= len(words) <= 4:
        return NameKind.PERSON

    return NameKind.UNKNOWN


def is_person(name: str | None) -> bool:
    """True when the name looks like an individual rather than an entity."""
    return classify(name) is NameKind.PERSON
