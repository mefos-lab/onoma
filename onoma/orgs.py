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

    __slots__ = ("score", "shared", "a_tokens", "b_tokens")

    def __init__(self, score: float, shared: set[str],
                 a_tokens: set[str], b_tokens: set[str]):
        self.score = score
        self.shared = shared
        self.a_tokens = a_tokens
        self.b_tokens = b_tokens

    @property
    def weak(self) -> bool:
        """True when the match rests on a single shared token.

        Weak matches are common and often correct — an abbreviation
        usually shares exactly one distinctive word with its expansion.
        They are also where the false positives live, because two
        committees of the same candidate share exactly as much. Treat a
        weak match as a candidate to corroborate, not a conclusion.
        """
        return len(self.shared) < 2

    def __bool__(self) -> bool:
        return self.score >= DEFAULT_THRESHOLD

    def __repr__(self) -> str:
        return (f"OrgMatch(score={self.score:.2f}, "
                f"shared={sorted(self.shared)}, weak={self.weak})")


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
    """
    da, db = distinctive_tokens(a), distinctive_tokens(b)
    if not da or not db:
        return OrgMatch(0.0, set(), da, db)
    shared = da & db
    score = len(shared) / min(len(da), len(db)) if shared else 0.0
    return OrgMatch(score, shared, da, db)


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
