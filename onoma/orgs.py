"""Organisation names — legal and political entity types, comparison.

`cleanco` covers corporate legal suffixes (LLC, Inc, GmbH). It does not
cover the political committee vocabulary that dominates campaign-finance
data, and neither does OpenSanctions' `rigour`: both are built for
corporate and sanctions entities. `PAC`, `POLITICAL ACTION COMMITTEE`,
victory funds and leadership PACs are left intact by both, which is the
gap this module fills.
"""

from __future__ import annotations

import re

from cleanco import basename

from .normalize import fold, is_generic_org_token, tokens

# Political entity types, longest first so multi-word forms are removed
# before their abbreviations can match a fragment.
_POLITICAL_TYPES = (
    "political action committee",
    "joint fundraising committee",
    "leadership pac",
    "victory committee",
    "victory fund",
    "campaign committee",
    "principal campaign committee",
    "super pac",
    "pac",
)

# Share of the shorter name's distinctive tokens that must be shared.
# Compared against the shorter name so an abbreviation is not penalised
# for the longer form's extra words.
DEFAULT_THRESHOLD = 0.6


def strip_entity_types(name: str) -> str:
    """Remove corporate and political entity types from an org name."""
    folded = fold(name)
    for t in _POLITICAL_TYPES:
        folded = re.sub(rf"\b{re.escape(t)}\b", " ", folded)
    # cleanco handles the corporate side; re-fold since it may reintroduce
    # punctuation or casing from its own tables.
    return fold(basename(folded))


def distinctive_tokens(name: str) -> set[str]:
    """Tokens that actually identify an organisation.

    Generic vocabulary is excluded because sharing it is not evidence.
    This is the check that separates a real abbreviation match from two
    unrelated committees that merely share a surname and a preposition.
    """
    return {t for t in tokens(strip_entity_types(name)) if not is_generic_org_token(t)}


class OrgMatch:
    """The evidence behind an organisation-name comparison.

    Deliberately not just a boolean. Two names can be indistinguishable
    by name alone while referring to different entities, and a caller
    holding an identifier, an amount or a date can resolve what a string
    comparison cannot. Returning the evidence lets them.
    """

    __slots__ = ("score", "shared", "a_tokens", "b_tokens", "exact")

    def __init__(self, score: float, shared: set[str],
                 a_tokens: set[str], b_tokens: set[str],
                 exact: bool = False):
        self.score = score
        self.shared = shared
        self.a_tokens = a_tokens
        self.b_tokens = b_tokens
        #: The two names are identical once entity types are stripped.
        self.exact = exact

    @property
    def weak(self) -> bool:
        """True when the match rests on a single shared token.

        Weak matches are common and often correct — an abbreviation
        usually shares exactly one distinctive word with its expansion.
        They are also where the false positives live, because two
        committees of the same candidate share exactly as much. Treat a
        weak match as a candidate to corroborate, not a conclusion.

        An exact match is never weak, however few tokens it has. A
        one-word organisation compared against itself was previously
        reported weak purely because one shared token is fewer than two,
        which made ``require_strong`` reject identical names.
        """
        if self.exact:
            return False
        return len(self.shared) < 2

    def __bool__(self) -> bool:
        return self.score >= DEFAULT_THRESHOLD

    def __repr__(self) -> str:
        return (f"OrgMatch(score={self.score:.2f}, "
                f"shared={sorted(self.shared)}, "
                f"exact={self.exact}, weak={self.weak})")


def compare_orgs(a: str, b: str) -> OrgMatch:
    """Compare two organisation names, returning score and evidence.

    Overlap is measured on *distinctive* tokens against the shorter
    name, so an abbreviation is not penalised for its expansion's extra
    words. Generic vocabulary is excluded because sharing it is not
    evidence.

    A raw fuzzy ratio cannot do this job: measured on real committee
    names, token-set similarity scored a genuine abbreviation match only
    marginally above a known false pair, leaving no separating
    threshold.

    A name can reduce to nothing distinctive — "AT&T" is entirely a
    preposition and a dropped initial. Such a name cannot be compared by
    overlap at all, so it falls back to equality of the stripped form.
    That keeps it matching itself and its suffixed variants while
    refusing to match a longer name that merely contains the word.
    """
    stripped_a = strip_entity_types(a)
    exact = bool(stripped_a) and stripped_a == strip_entity_types(b)

    da, db = distinctive_tokens(a), distinctive_tokens(b)
    if not da and not db:
        return OrgMatch(1.0 if exact else 0.0, set(), da, db, exact)
    if not da or not db:
        # One side has something to identify it and the other has
        # nothing, so there is no evidence either way. Reporting no match
        # is the honest answer rather than the confident one.
        return OrgMatch(0.0, set(), da, db, exact)
    shared = da & db
    score = len(shared) / min(len(da), len(db)) if shared else 0.0
    return OrgMatch(score, shared, da, db, exact)


def same_org(a: str, b: str, threshold: float = DEFAULT_THRESHOLD,
             require_strong: bool = False) -> bool:
    """Boolean form of :func:`compare_orgs`.

    Set *require_strong* to reject matches resting on a single shared
    token. That is the conservative choice, and it rejects some genuine
    abbreviation matches along with the false ones — the two are not
    separable by name. Prefer :func:`compare_orgs` and corroborate with
    an identifier where one exists.

    **Known limit.** Sibling committees of the same candidate — a
    principal campaign committee and a joint fundraising committee, say —
    share a surname and nothing else distinctive, which is structurally
    identical to a valid abbreviation match. No threshold separates
    them. This is a property of the names, not of the implementation.
    """
    m = compare_orgs(a, b)
    if require_strong and m.weak:
        return False
    return m.score >= threshold
