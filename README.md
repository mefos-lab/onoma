# onoma

Name normalization and matching for public-records entity resolution.

*ónoma* (ὄνομα) — Greek for "name".

Cross-referencing public records means deciding whether two records name
the same thing. The records disagree constantly: one system writes
`Sen. Marsha Blackburn`, another `Marsha Blackburn`; one has
`Ben Ray Luján`, another `Ben Ray Lujan`; one has
`ARKANSAS LEADERSHIP PAC`, another
`ARKANSAS FOR LEADERSHIP POLITICAL ACTION COMMITTEE (ARKPAC)`.

## Name matching is not one problem

Treating it as one function is why independent implementations that
should agree end up disagreeing. It is at least four problems:

| Problem | Nature | Approach |
|---|---|---|
| Normalization | Deterministic | Case, punctuation, diacritics |
| Person names | Two sub-kinds | Titles; truncations by rule, nicknames by table |
| Organisation names | Domain-specific | Entity types; distinctive vs. filler tokens |
| Scoring | Statistical | For what survives the above |

`onoma` exposes these as separate operations rather than one
`match(a, b)` that has to guess which problem it is looking at.

## Usage

```python
import onoma

onoma.fold("Ben Ray Luján")                    # 'ben ray lujan'
onoma.strip_titles("Sen. Marsha Blackburn")    # 'marsha blackburn'

onoma.same_person("Bob Latta", "Robert E. Latta")        # True  (nickname)
onoma.same_person("Chris Coons", "Christopher A. Coons") # True  (truncation)
onoma.same_person("Max Miller", "Mary E. Miller")        # False (surname only)

onoma.same_org("ARKANSAS LEADERSHIP PAC",
               "ARKANSAS FOR LEADERSHIP POLITICAL ACTION COMMITTEE (ARKPAC)")
# True

onoma.same_org("COLLINS FOR VICTORY", "COLLINS FOR SENATOR")
# False — shares only a surname and filler words
```

## Design notes

**Pure Python, by constraint.** Every dependency installs without a C
toolchain. This matters for a tool intended to be usable by anyone who
can run pip.

**Built on existing libraries where they fit.** `nameparser` for person
name structure, `nicknames` for given-name equivalences, `cleanco` for
corporate legal suffixes, `rapidfuzz` for scoring, `Unidecode` for
diacritics. What this library adds is the domain layer none of them
cover.

**Why not OpenSanctions `rigour`.** It was evaluated first, since it is
maintained and well-matched to sanctions and corporate data. It handles
corporate suffixes and some honorifics well, but does not strip
legislative titles (`Sen.`, `Rep.`), does not treat `PAC` or
`POLITICAL ACTION COMMITTEE` as entity types, does not fold diacritics
in its normalizer, and has no nickname handling — all of which are
central here. It also requires `PyICU`, hence the ICU C library, which
would put a build step between a researcher and a working install. Good
library; different domain.

**Why not a fuzzy ratio alone.** Measured on real committee names,
token-set similarity scored a genuine abbreviation match only slightly
above a known false pair — too narrow a margin for a safe threshold.
Requiring a shared *distinctive* token separates them, where a raw
similarity score does not.

**Surnames are required to match exactly** in person comparison. They
are the stable part of a name across sources; given names vary far more.
Relaxing the surname is where false positives come from.

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
threshold distinguishes them — this is a property of the names, not of
the implementation.

So `compare_orgs` returns the evidence, not just a verdict:

```python
m = onoma.compare_orgs(a, b)
m.score     # 1.0
m.shared    # {'collins'}
m.weak      # True — rests on a single shared token
```

A caller holding an identifier, an amount or a date can resolve what a
string comparison cannot. Prefer identifier joins wherever the data
offers them, and treat a weak match as a candidate to corroborate rather
than a conclusion. `same_org(..., require_strong=True)` rejects
single-token matches outright, at the cost of losing genuine
abbreviations along with the false ones.

## Correctness bias

False positives are the expensive error. Wrongly merging two people
makes a factual claim about a real person, and is worse than failing to
merge — a missed match is a gap, a wrong match is an assertion. The
defaults are set accordingly.

## License

MIT
