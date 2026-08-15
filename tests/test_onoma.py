"""Tests for onoma.

The cases here are not invented. They are the name pairs that actually
failed in the tools this library was extracted from, plus the negative
cases those failures made visible.
"""

import pytest

import onoma as o


# =============================================================================
# Normalization
# =============================================================================

class TestFold:
    @pytest.mark.parametrize("raw,expected", [
        ("Ben Ray Luján", "ben ray lujan"),
        ("Linda T. Sánchez", "linda t sanchez"),
        # Hyphens and apostrophes join rather than split, so a compound
        # surname stays one token and compares against itself written
        # either way.
        ("O'Brien-Smith", "obriensmith"),
        ("  MIXED   Case  ", "mixed case"),
    ])
    def test_folds(self, raw, expected):
        assert o.fold(raw) == expected

    def test_empty_and_none(self):
        assert o.fold("") == ""
        assert o.fold(None) == ""

    def test_tokens_drop_single_characters(self):
        """Middle initials vary by source and would defeat comparison."""
        assert o.tokens("Max L. Miller") == ["max", "miller"]


# =============================================================================
# Person names
# =============================================================================

class TestStripTitles:
    @pytest.mark.parametrize("raw,expected", [
        ("Sen. Marsha Blackburn", "marsha blackburn"),
        ("Rep. Max Miller", "max miller"),
        ("The Honorable French Hill", "french hill"),
        ("U.S. Representative Linda Sanchez", "linda sanchez"),
        ("Christopher A. Coons", "christopher a coons"),
    ])
    def test_strips(self, raw, expected):
        assert o.strip_titles(raw) == expected


class TestSamePerson:
    @pytest.mark.parametrize("a,b", [
        ("Chris Coons", "Christopher A. Coons"),     # truncation
        ("Dan Meuser", "Daniel Meuser"),             # truncation
        ("Bob Latta", "Robert E. Latta"),            # nickname, not a prefix
        ("Lizzie Fletcher", "Elizabeth Fletcher"),   # nickname, not a prefix
        ("Ben Ray Lujan", "Ben Ray Luján"),          # diacritic
        ("Max Miller", "Max L. Miller"),             # middle initial
        ("Sen. Marsha Blackburn", "Marsha Blackburn"),
        ("U.S. Representative Linda Sanchez", "Linda T. Sánchez"),
    ])
    def test_matches(self, a, b):
        assert o.same_person(a, b), f"{a!r} should match {b!r}"

    @pytest.mark.parametrize("a,b", [
        ("Max Miller", "Mary E. Miller"),        # same surname, different person
        ("Carol D. Miller", "Max L. Miller"),
        ("Kevin Mullin", "Markwayne Mullin"),
        ("Chris Coons", "Chris Murphy"),         # same given name, different surname
    ])
    def test_rejects(self, a, b):
        assert not o.same_person(a, b), f"{a!r} must not match {b!r}"

    def test_surname_only_one_side(self):
        """As much as can be said without a given name."""
        assert o.same_person("Coons", "Christopher A. Coons")

    def test_empty(self):
        assert not o.same_person("", "Max Miller")


class TestGivenNames:
    def test_nickname_both_directions(self):
        assert o.given_names_match("bob", "robert")
        assert o.given_names_match("robert", "bob")

    def test_prefix_needs_minimum_length(self):
        """A two-character fragment would match far too broadly."""
        assert not o.given_names_match("jo", "jonathan")
        assert o.given_names_match("jon", "jonathan")


# =============================================================================
# Organisation names
# =============================================================================

class TestEntityTypes:
    @pytest.mark.parametrize("raw,gone", [
        ("Acme Holdings LLC", "llc"),
        ("ARKANSAS FOR LEADERSHIP POLITICAL ACTION COMMITTEE", "political action committee"),
        ("MICROSOFT STAKEHOLDERS VOLUNTARY PAC", "pac"),
    ])
    def test_removes_entity_type(self, raw, gone):
        assert gone not in o.strip_entity_types(raw)

    def test_generic_tokens_are_not_distinctive(self):
        assert o.distinctive_tokens("Friends of the Committee") == set()


class TestCompareOrgs:
    def test_abbreviation_matches(self):
        m = o.compare_orgs("ARKANSAS LEADERSHIP PAC",
                           "ARKANSAS FOR LEADERSHIP POLITICAL ACTION COMMITTEE (ARKPAC)")
        assert m.score > 0
        assert "arkansas" in m.shared

    def test_unrelated_orgs_score_zero(self):
        assert o.compare_orgs("MICROSOFT PAC", "GOOGLE PAC").score == 0.0

    def test_shared_filler_alone_is_not_a_match(self):
        assert not o.same_org("Friends of Jane Doe", "Friends of John Smith")

    def test_sibling_committees_are_flagged_weak_not_separated(self):
        """The documented limit: name alone cannot separate these.

        A candidate's joint fundraising committee and their principal
        campaign committee share a surname and nothing else distinctive
        — structurally identical to a real abbreviation match. The API
        reports the weakness rather than pretending to decide.
        """
        false_pair = o.compare_orgs("COLLINS FOR VICTORY", "COLLINS FOR SENATOR")
        true_pair = o.compare_orgs("ARKANSAS LEADERSHIP PAC",
                                   "ARKANSAS FOR LEADERSHIP POLITICAL ACTION COMMITTEE (ARKPAC)")
        assert false_pair.weak and true_pair.weak
        assert false_pair.score == true_pair.score   # genuinely indistinguishable

    def test_require_strong_rejects_single_token_matches(self):
        assert not o.same_org("COLLINS FOR VICTORY", "COLLINS FOR SENATOR",
                              require_strong=True)

    def test_bool_protocol(self):
        assert bool(o.compare_orgs("Acme Holdings LLC", "ACME HOLDINGS L.L.C."))
        assert not bool(o.compare_orgs("MICROSOFT PAC", "GOOGLE PAC"))


# =============================================================================
# Regressions found by running against a real corpus
#
# Each case below comes from measuring resolution across several hundred
# real LD-203 honoree names, not from imagination.
# =============================================================================

class TestTransitiveNicknameRejection:
    """Two nicknames of one canonical are not the same name.

    Found as a live false positive: "Tina" and "Chris" are both
    nicknames of "Christina", so intersecting variant sets equated Tina
    Smith with Chris Smith. Linkage must be direct — one name a recorded
    nickname *of the other* — not transitive through a shared canonical.
    """

    @pytest.mark.parametrize("a,b", [
        ("Tina Smith", "Chris Smith"),
        ("Chris Smith", "Tina Smith"),
        ("Kit Smith", "Chris Smith"),
    ])
    def test_rejects_shared_canonical(self, a, b):
        assert not o.same_person(a, b)

    @pytest.mark.parametrize("a,b", [
        ("Bob Latta", "Robert E. Latta"),
        ("Lizzie Fletcher", "Elizabeth Fletcher"),
    ])
    def test_direct_nickname_still_matches(self, a, b):
        assert o.same_person(a, b)


class TestTitleForms:
    @pytest.mark.parametrize("raw,expected", [
        ("Majority Leader Steve Scalise", "steve scalise"),
        ("U.S. Rep. Hakeem Jeffries", "hakeem jeffries"),
        ("U.S. Sen. Lisa Blount Rochester", "lisa blount rochester"),
        ("Speaker of the House Mike Johnson", "mike johnson"),
    ])
    def test_strips_office_and_leadership_titles(self, raw, expected):
        assert o.strip_titles(raw) == expected


class TestCompoundSurnames:
    def test_hyphenated_surname_matches_either_form(self):
        assert o.same_person("Rep. Kamlager-Dove", "Sydney Kamlager-Dove")

    def test_apostrophe_surname(self):
        assert o.same_person("Sean O'Brien", "Sean OBrien")


class TestAnnotations:
    @pytest.mark.parametrize("raw,expected", [
        ("Rep. Lisa Sanchez (D-CA-38)", "lisa sanchez"),
        ("U.S. Rep. Haley Stevens, U.S. Senate Candidate", "haley stevens"),
        ("Zoe Cadore, Candidate for U.S. House of Representatives", "zoe cadore"),
    ])
    def test_strips_trailing_role_and_district(self, raw, expected):
        assert o.strip_titles(raw) == expected


class TestSingleEditVariants:
    """Sources disagree on a single character for the same person."""

    @pytest.mark.parametrize("a,b", [
        ("Shelly Moore Capito", "Shelley Moore Capito"),
        ("Lindsay Graham", "Lindsey Graham"),
    ])
    def test_accepts_one_edit_in_given_name(self, a, b):
        assert o.same_person(a, b)

    def test_short_given_names_are_not_edit_matched(self):
        """Below the length floor one edit is too large a proportion."""
        assert not o.same_person("Dan Meuser", "Don Meuser")

    def test_surname_still_must_match_exactly(self):
        assert not o.same_person("Shelly Moore Capito", "Shelley Moore Capita")


class TestClassify:
    @pytest.mark.parametrize("name", [
        "DCCC", "Congressional Black Caucus PAC", "Friends of David Schweikert",
        "1.29.25 DSCC Event", "Elect Democratic Women",
        "Democratic Members of House Committee on Ways and Means",
        "Christian Menefee for Congress",
    ])
    def test_organisations(self, name):
        assert o.classify(name) is o.NameKind.ORGANISATION
        assert not o.is_person(name)

    @pytest.mark.parametrize("name", [
        "Sen. Marsha Blackburn", "Elizabeth Fletcher", "Gov. Maura Healey",
    ])
    def test_people(self, name):
        assert o.classify(name) is o.NameKind.PERSON
        assert o.is_person(name)

    def test_empty_is_unknown(self):
        assert o.classify("") is o.NameKind.UNKNOWN

    @pytest.mark.parametrize("name", [
        "N/A", "n/a", "General Fund", "Various Democratic Congressional Candidates",
    ])
    def test_placeholders_are_unknown_not_people(self, name):
        """Filing placeholders are neither. Left unhandled they classify
        as people and inflate the unresolved count."""
        assert o.classify(name) is o.NameKind.UNKNOWN
        assert not o.is_person(name)
