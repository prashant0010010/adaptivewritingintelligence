import pytest

from core.writing_analysis import analyse_text, build_genre_profile, evidence_level, js_distance, mattr, style_distance
from utils.text_processing import split_sentences, words


def test_counts_basic():
    a = analyse_text("One two three. Four five six seven.\n\nEight nine.")
    assert a["word_count"] == 9 and a["sentence_count"] == 3 and a["paragraph_count"] == 2


def test_sentence_lengths_and_mean():
    a = analyse_text("One two three. Four five six seven. Eight nine.")
    assert a["mean_sentence_length"] == 3.0
    assert a["min_sentence_length"] == 2 and a["max_sentence_length"] == 4


def test_sd_only_with_enough_sentences():
    assert analyse_text("A b c. D e f.")["sentence_length_sd"] is None
    text = " ".join(["Word " * n + "end." for n in (2, 4, 6, 8, 10)])
    assert analyse_text(text)["sentence_length_sd"] is not None


@pytest.mark.parametrize("text", ["", "   ", "Hi"])
def test_empty_and_very_short(text):
    a = analyse_text(text)
    assert a["word_count"] in (0, 1) and a["mean_sentence_length"] in (None, 1) and a["mattr_50"] is None and a["reliable"] is False


def test_abbreviations_and_decimals_do_not_split():
    s = split_sentences("Smith et al. found 3.5 percent growth, e.g. in 2020. Next sentence here.")
    assert len(s) == 2


def test_mattr_requires_length():
    assert mattr(["a"] * 10) is None
    assert 0 < mattr(["w%d" % (i % 20) for i in range(120)]) <= 1


def test_transitions_and_hedging_detected():
    a = analyse_text("However, the result may vary. Therefore we should check, for example, the data.")
    assert a["transition_counts"]["contrast"] >= 1 and a["transition_counts"]["cause_result"] >= 1
    assert a["hedging_per_100_words"] > 0


def test_js_distance_properties():
    assert js_distance([1, 1], [1, 1]) == 0
    assert 0 < js_distance([1, 0.1], [0.1, 1]) <= 1
    with pytest.raises(ValueError):
        js_distance([0, 0], [1, 1])


def test_style_distance_needs_enough_text():
    assert style_distance("short", "also short") is None
    t = "This is a sentence about writing and style. " * 20
    assert style_distance(t, t)["mean"] == 0


def test_evidence_level_labels():
    assert evidence_level(100, 1) == "very limited"
    assert evidence_level(1000, 2) == "limited"
    assert evidence_level(6000, 6) == "reasonable"


def test_genre_profile_empty():
    assert build_genre_profile([])["sample_count"] == 0
