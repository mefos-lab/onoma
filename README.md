# onoma

Name normalization and matching for public-records entity resolution.

*ónoma* (ὄνομα) — Greek for "name".

Cross-referencing public records means deciding whether two records name
the same thing, and the records disagree constantly. One system writes
`Sen. Marsha Blackburn`, another `Marsha Blackburn`. One has
`Ben Ray Luján`, another `Ben Ray Lujan`. One has
`ARKANSAS LEADERSHIP PAC`, another
`ARKANSAS FOR LEADERSHIP POLITICAL ACTION COMMITTEE (ARKPAC)`.

## Name matching is not one problem

Treating it as a single function is why independent implementations that
ought to agree end up disagreeing — each folds a slightly different set
of transformations into its own comparison. It is at least four
problems, with different correct solutions:

| Problem | Nature | Handled by |
|---|---|---|
| Normalization | Deterministic | Case, punctuation, diacritics |
| Person names | Two sub-kinds | Titles; truncations by rule, nicknames by table |
| Organisation names | Domain-specific | Entity types; distinctive vs. filler tokens |
| Classification | Prerequisite | Is this a person or an organisation at all? |

`onoma` exposes these as separate operations rather than one
`match(a, b)` that has to guess which problem it is looking at.

## Install

```bash
pip install onoma
```

Pure Python. Every dependency installs without a C toolchain — a
deliberate constraint, so that anyone who can run pip can run this.

## Quick start

```python
import onoma

# Classify before matching — see below for why this matters
onoma.is_person("Sen. Marsha Blackburn")   # True
onoma.is_person("Congressional Black Caucus PAC")  # False

onoma.same_person("Bob Latta", "Robert E. Latta")         # True  (nickname)
onoma.same_person("Chris Coons", "Christopher A. Coons")  # True  (truncation)
onoma.same_person("Max Miller", "Mary E. Miller")         # False (surname only)

onoma.same_org("ARKANSAS LEADERSHIP PAC",
               "ARKANSAS FOR LEADERSHIP POLITICAL ACTION COMMITTEE (ARKPAC)")
# True
```

## API

### Classification

| Function | Returns | Notes |
|---|---|---|
| `classify(name)` | `NameKind` | `PERSON`, `ORGANISATION` or `UNKNOWN` |
| `is_person(name)` | `bool` | Shorthand for `classify(...) is PERSON` |

`NameKind.UNKNOWN` is a real answer, not a failure — treat it as "try
person matching, but do not be surprised by a miss".

### Normalization

| Function | Returns | Notes |
|---|---|---|
| `fold(text)` | `str` | Casefold, strip diacritics and punctuation, collapse whitespace |
| `tokens(text)` | `list[str]` | Folded tokens; single characters dropped as middle initials |
| `is_generic_org_token(token)` | `bool` | Membership test against `GENERIC_ORG_TOKENS` |
| `GENERIC_ORG_TOKENS` | `frozenset[str]` | Words that carry no identifying signal in an org name |

### Person names

| Function | Returns | Notes |
|---|---|---|
| `same_person(a, b)` | `bool` | Full comparison; requires exact surname match |
| `strip_titles(name)` | `str` | Removes honorifics, offices and leadership titles |
| `given_names_match(a, b)` | `bool` | Given names only — exact, nickname, truncation, or one edit |
| `given_name_variants(given)` | `set[str]` | A given name plus its recorded nickname and canonical forms |

### Organisation names

| Function | Returns | Notes |
|---|---|---|
| `compare_orgs(a, b)` | `OrgMatch` | Score plus the evidence behind it — prefer this |
| `same_org(a, b, threshold=…, require_strong=False)` | `bool` | Boolean form |
| `strip_entity_types(name)` | `str` | Removes corporate and political entity types |
| `distinctive_tokens(name)` | `set[str]` | Tokens that actually identify the organisation |
| `DEFAULT_THRESHOLD` | `float` | Default overlap threshold for `same_org` |

`OrgMatch` carries `score`, `shared` (the shared distinctive tokens),
`a_tokens`, `b_tokens`, and `weak` — true when the match rests on a
single shared token. It is also truthy/falsy directly, so
`if compare_orgs(a, b):` works.

## Classify before matching

A field nominally holding people also holds party committees, caucus
PACs, fundraising vehicles, events and placeholders. Running person
matching on those and counting the failures measures the wrong thing —
they are not unmatched people, they are not people.

```python
people = [n for n in names if onoma.is_person(n)]
resolved = [n for n in people if lookup(n)]
# report len(resolved) / len(people), not / len(names)
```

Measured across several hundred real lobbying-disclosure honoree names,
roughly a tenth were organisations. Separating them changed the reported
resolution rate substantially, entirely through the denominator.

## A limit worth knowing about

Some organisation names are **not separable by name alone**, and the
library says so rather than guessing.

A candidate's joint fundraising committee and their principal campaign
committee share a surname and nothing else distinctive. That is
structurally identical to a genuine abbreviation match:

```
ARKANSAS LEADERSHIP PAC  ~  ARKANSAS FOR ... COMMITTEE (ARKPAC)
    distinctive: {arkansas}  vs  {arkansas, arkpac}   -> 1 shared

COLLINS FOR VICTORY      ~  COLLINS FOR SENATOR
    distinctive: {collins}   vs  {collins, senator}   -> 1 shared
```

Same shape, same score. The first is correct, the second is not, and no
threshold distinguishes them — a property of the names, not of the
implementation.

So `compare_orgs` returns the evidence rather than only a verdict:

```python
m = onoma.compare_orgs(a, b)
m.score     # 1.0
m.shared    # {'collins'}
m.weak      # True — rests on a single shared token
```

A caller holding an identifier, an amount or a date can resolve what a
string comparison cannot. **Prefer identifier joins wherever the data
offers them**, and treat a weak match as a candidate to corroborate
rather than a conclusion. `same_org(..., require_strong=True)` rejects
single-token matches outright, at the cost of losing genuine
abbreviations along with the false ones.

## Design notes

**Built on existing libraries where they fit.** `nameparser` for person
name structure, `nicknames` for given-name equivalences, `cleanco` for
corporate legal suffixes, `rapidfuzz` for scoring, `Unidecode` for
diacritics. What this adds is the domain layer none of them cover.

**Why not OpenSanctions `rigour`.** Evaluated first, since it is
maintained and well matched to sanctions and corporate data. It handles
corporate suffixes and some honorifics well, but does not strip
legislative titles (`Sen.`, `Rep.`), does not treat `PAC` or
`POLITICAL ACTION COMMITTEE` as entity types, does not fold diacritics
in its normalizer, and has no nickname handling — all central here. It
also requires `PyICU`, and therefore the ICU C library, which puts a
build step between a researcher and a working install. Good library,
different domain.

**Why not a fuzzy ratio alone.** Measured on real committee names,
token-set similarity scored a genuine abbreviation match only slightly
above a known false pair — too narrow a margin for a safe threshold.
Requiring a shared *distinctive* token separates them where a raw
similarity score does not.

**Nickname linkage is direct, not transitive.** Two nicknames of one
canonical are not the same name. "Tina" and "Chris" are both nicknames
of "Christina"; equating them would merge Tina Smith with Chris Smith.
A match requires one name to be a recorded nickname *of the other*.

**Surnames must match exactly** in person comparison. They are the
stable part of a name across sources; given names vary far more.
Relaxing the surname is where false positives come from. A
single-character difference is tolerated in the *given* name only, and
only above a minimum length, so `Shelly`/`Shelley` matches while
`Dan`/`Don` does not.

**Comparison is cached.** The access pattern is one query against the
same corpus repeatedly, so parsing results are memoised. This is a large
difference in practice, not a micro-optimisation.

## Correctness bias

False positives are the expensive error. Wrongly merging two people
makes a factual claim about a real person; failing to merge leaves a
gap. A gap is recoverable, an assertion is not. The defaults are set
accordingly, and where the data genuinely cannot decide, the API returns
evidence instead of a verdict.

## Development

```bash
pip install -e . pytest
pytest
```

Tests are drawn from name pairs that actually failed in the tools this
was extracted from, plus the negative cases those failures made visible.
When adding a case, prefer one observed in real data over an invented
one.

## License

MIT
