"""Property-based tests: rules that must hold for *any* input, not just hand-picked cases."""

from __future__ import annotations

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cv_ats_check.checks.contact_checks import find_emails, find_phones
from cv_ats_check.checks.date_checks import check_dates, find_dates
from cv_ats_check.checks.layout_checks import find_columns
from cv_ats_check.models import Status, TextBlock
from cv_ats_check.nlp.jobad import LANGUAGE_NAMES, parse_job_requirements
from cv_ats_check.nlp.keywords import analyze_keywords, count_sequence, frequency_threshold
from cv_ats_check.nlp.normalize import normalize_text, stem, tokenize
from tests.helpers import make_doc

FAST = settings(max_examples=150, deadline=None)
SLOW = settings(max_examples=40, deadline=None)

any_text = st.text(max_size=300)
cv_like_text = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzåäöÅÄÖ ABC0123456789.,;:/-+#'’\n–"),
    max_size=300,
)

# --- text normalisation ------------------------------------------------------------------------


@FAST
@given(any_text)
def test_tokens_are_always_clean(text):
    for token in tokenize(text):
        assert token, "empty token"
        assert token == token.casefold()
        assert not any(c.isspace() for c in token)
        assert not token.isdigit()


@FAST
@given(any_text)
def test_tokenizing_ignores_surrounding_whitespace(text):
    assert tokenize(f" \n\t{text}\t\n ") == tokenize(text)


@FAST
@given(any_text)
def test_normalisation_is_idempotent(text):
    once = normalize_text(text)
    assert normalize_text(once) == once


@FAST
@given(st.text(min_size=1, max_size=30))
def test_stem_only_removes_a_trailing_s(word):
    stemmed = stem(word)
    assert word.startswith(stemmed)
    assert len(word) - len(stemmed) in (0, 1)


# --- sequence counting ---------------------------------------------------------------------------

small_tokens = st.lists(st.sampled_from(["a", "b", "c"]), max_size=40)
needles = st.lists(st.sampled_from(["a", "b", "c"]), min_size=1, max_size=4).map(tuple)


@FAST
@given(small_tokens, needles)
def test_count_is_bounded_by_what_fits(haystack, needle):
    assert 0 <= count_sequence(haystack, needle) <= len(haystack) // len(needle)


@FAST
@given(needles, st.integers(min_value=0, max_value=6))
def test_a_repeated_needle_is_counted_exactly(needle, times):
    haystack = ["#", *list(needle) * times, "#"]
    assert count_sequence(haystack, needle) == times


@FAST
@given(small_tokens, small_tokens, needles)
def test_appending_text_never_lowers_the_count(first, extra, needle):
    assert count_sequence(first + ["#"] + extra, needle) >= count_sequence(first, needle)


@FAST
@given(small_tokens)
def test_an_empty_needle_counts_nothing(haystack):
    assert count_sequence(haystack, ()) == 0


@FAST
@given(st.integers(0, 20_000), st.integers(0, 20_000))
def test_repetition_threshold_never_falls_below_ten_or_shrinks(a, b):
    low, high = sorted((a, b))
    assert frequency_threshold(low) >= 10
    assert frequency_threshold(low) <= frequency_threshold(high)


# --- dates ----------------------------------------------------------------------------------------

years = st.integers(min_value=1950, max_value=2049)
dashes = st.sampled_from(["-", "–", "—"])
months = st.sampled_from(["Jan", "feb", "Mars", "April", "maj", "Juni", "Aug", "okt", "Dec"])


@FAST
@given(cv_like_text)
def test_date_matches_come_from_the_text_and_never_overlap(text):
    matches = find_dates(text)
    assert all(m.text in text for m in matches)
    assert sum(len(m.text) for m in matches) <= len(text)


@FAST
@given(years, years, dashes)
def test_year_ranges_are_one_match_with_the_right_dash(y1, y2, dash):
    (match,) = find_dates(f"Worked {y1}{dash}{y2} at Acme")
    assert (match.label, match.separator, match.is_range) == ("YYYY – YYYY", dash, True)


@FAST
@given(months, years, months, years, dashes)
def test_month_ranges_are_one_match(m1, y1, m2, y2, dash):
    (match,) = find_dates(f"{m1} {y1} {dash} {m2} {y2}")
    assert match.label == "Mon YYYY – Mon YYYY"


TEMPLATES = [
    "{a}–{b}",
    "Jan {a} – Mar {b}",
    "{a}-01 – {b}-03",
    "01/{a} – 03/{b}",
]


@FAST
@given(st.integers(0, 3), st.integers(0, 3), years, years, years, years)
def test_mixing_date_styles_warns_and_one_style_passes(first, second, a1, b1, a2, b2):
    lines = [
        "Acme " + TEMPLATES[first].format(a=a1, b=b1),
        "Beta " + TEMPLATES[second].format(a=a2, b=b2),
    ]
    status = check_dates(make_doc(lines)).status
    assert status is (Status.PASS if first == second else Status.WARN)


# --- contact details ------------------------------------------------------------------------

separators = st.sampled_from([" ", "-", " ", " ", " ", "–", "−"])
digit_strings = st.text(alphabet="0123456789", min_size=7, max_size=7)


@FAST
@given(st.integers(0, 9), digit_strings, separators, separators, separators)
def test_swedish_mobile_numbers_are_found_whatever_the_separators(d, rest, s1, s2, s3):
    number = f"07{d}{s1}{rest[:3]}{s2}{rest[3:5]}{s3}{rest[5:]}"
    found = find_phones(f"Phone: {number} thanks")
    assert found, number
    assert re.sub(r"\D", "", found[0]) == f"07{d}{rest}"


@FAST
@given(digit_strings, separators, separators)
def test_international_numbers_are_found(rest, s1, s2):
    number = f"+46{s1}7{rest[:2]}{s2}{rest[2:5]}{s2}{rest[5:]}"
    assert find_phones(f"Tel {number}"), number


@FAST
@given(years, years, dashes)
def test_year_ranges_are_never_phone_numbers(y1, y2, dash):
    assert find_phones(f"Worked {y1}{dash}{y2} at Acme") == []


@FAST
@given(any_text)
def test_phone_and_email_search_never_crash(text):
    find_phones(text)
    find_emails(text)


local_parts = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789._+-", min_size=1, max_size=15)
labels = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=10)
tlds = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=6)


@FAST
@given(local_parts, labels, tlds)
def test_generated_emails_are_found_whole(local, domain, tld):
    email = f"{local}@{domain}.{tld}"
    assert find_emails(f"mail {email} now") == [email]


# --- layout --------------------------------------------------------------------------------------


def blocks_strategy(same_left_edge: bool):
    def build(args):
        x0, width, y, words = args
        left = 50.0 if same_left_edge else x0
        return TextBlock(" ".join(["word"] * words), 1, bbox=(left, y, left + width, y + 10))

    return st.lists(
        st.tuples(
            st.floats(10, 500), st.floats(5, 400), st.floats(10, 800), st.integers(1, 12)
        ).map(build),
        max_size=30,
    )


@FAST
@given(blocks_strategy(False), st.floats(50, 900))
def test_a_found_gutter_is_always_inside_the_page_with_enough_lines_on_both_sides(blocks, width):
    result = find_columns(blocks, width)
    if result is not None:
        gutter, left, right = result
        assert 0.2 * width <= gutter <= 0.8 * width
        assert left >= 4 and right >= 4


@FAST
@given(blocks_strategy(True), st.floats(50, 900))
def test_lines_sharing_one_left_edge_are_never_two_columns(blocks, width):
    assert find_columns(blocks, width) is None


# --- keyword analysis and job ads ---------------------------------------------------------------


@SLOW
@given(cv_like_text, cv_like_text)
def test_keyword_analysis_is_total_and_consistent(cv_text, ad_text):
    analysis = analyze_keywords(cv_text, ad_text)
    assert 0 <= analysis.match_pct <= 100
    assert 0 <= analysis.score_pct <= 100
    assert analysis.total == len(analysis.found) + len(analysis.missing)
    assert all(k.cv_count > 0 for k in analysis.found)
    assert all(k.cv_count == 0 for k in analysis.missing)
    assert all(k.cv_count > analysis.threshold for k in analysis.frequent)
    counts = analysis.tier_counts()
    assert sum(total for _, total in counts.values()) == analysis.total


@pytest.mark.parametrize("text", ["", "\n\n", "Requirements", "Krav\n- "])
def test_empty_looking_ads_have_no_keywords_and_a_zero_score(text):
    analysis = analyze_keywords("Python", text)
    assert analysis.total == 0 and analysis.score_pct == 0


@FAST
@given(any_text)
def test_job_requirement_parsing_is_total_and_bounded(text):
    parsed = parse_job_requirements(text)
    assert all(0 < r.years <= 40 for r in parsed.experience)
    assert set(parsed.languages) <= set(LANGUAGE_NAMES)
    assert set(parsed.work_modes) <= {"remote", "hybrid", "on-site"}
    assert len(parsed.education) <= 2
