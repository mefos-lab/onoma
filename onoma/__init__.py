"""onoma — name normalization and matching for public-records entity resolution.

Name matching is not one problem. It is at least four, with different
correct solutions, and treating it as one function is why callers that
should agree end up disagreeing:

1. **Normalization** — case, punctuation, diacritics. Deterministic.
2. **Person names** — titles, and given-name variants split between
   truncations (rule-derivable) and nicknames (table-derivable).
3. **Organisation names** — legal and political entity types, and the
   distinction between shared identifying words and shared filler.
4. **Scoring** — for what survives the above.

The API exposes these as separate operations rather than a single
`match(a, b)` that has to guess which problem it is looking at.

Deliberately pure-Python. Every dependency installs without a C
toolchain, so this stays usable by anyone who can run pip.
"""

from .normalize import fold, tokens, is_generic_org_token, GENERIC_ORG_TOKENS
from .persons import (
    strip_titles, given_name_variants, given_names_match, same_person,
)
from .kind import NameKind, classify, is_person
from .orgs import (
    strip_entity_types, distinctive_tokens, compare_orgs, OrgMatch,
    same_org, DEFAULT_THRESHOLD,
)

__version__ = "0.1.0"

__all__ = [
    "NameKind", "classify", "is_person",
    "fold", "tokens", "is_generic_org_token", "GENERIC_ORG_TOKENS",
    "strip_titles", "given_name_variants", "given_names_match", "same_person",
    "strip_entity_types", "distinctive_tokens", "compare_orgs", "OrgMatch",
    "same_org", "DEFAULT_THRESHOLD",
    "__version__",
]
