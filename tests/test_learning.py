import pytest

from core.profile_learning import (MIN_VOTES, active_preferences, aggregate, change_vector, direction, preference_guidance,
                                   record_feedback, reset_learned_preference, set_user_preference)
from core.retrieval import retrieve_examples

SHORT = "The result is clear. We tested it twice. It held up. " * 4
LONG = SHORT + "However, this is a longer elaboration that adds explanatory material. Moreover, it continues at length. " * 3


def test_change_vector_directions():
    v = change_vector(SHORT, LONG)
    assert v["length"] > 0.1 and v["transitions"] > 1.0
    assert direction("length", v["length"]) == 1
    assert direction("length", 0.01) == 0


def test_single_action_does_not_change_profile(repo, pid):
    record_feedback(repo, pid, None, "Essay", "clarity", "reject", SHORT, LONG)
    assert active_preferences(repo, pid, "Essay") == {}


def test_repeated_rejection_of_longer_text_learns_shorter(repo, pid):
    for _ in range(MIN_VOTES + 1):
        record_feedback(repo, pid, None, "Essay", "clarity", "reject", SHORT, LONG)
    prefs = active_preferences(repo, pid, "Essay")
    assert prefs.get("length") == "shorter" and prefs.get("transitions") == "fewer"
    assert repo.latest_preference_version(pid) >= 1 and "length: shorter" in repo.list_preference_versions(pid)[-1]["change_note"].replace(" -> ", ": ")
    assert any("shorter" in g.lower() or "same length" in g.lower() for g in preference_guidance(prefs))


def test_accepting_longer_text_learns_longer(repo, pid):
    for _ in range(4):
        record_feedback(repo, pid, None, "Essay", "elaborate", "accept", SHORT, LONG)
    assert active_preferences(repo, pid, "Essay")["length"] == "longer"


def test_conflicting_feedback_prevents_preference():
    ev = [{"action": "accept", "deltas": {"length": 0.5}, "created_at": "1"}, {"action": "accept", "deltas": {"length": -0.5}, "created_at": "2"},
          {"action": "accept", "deltas": {"length": 0.5}, "created_at": "3"}, {"action": "accept", "deltas": {"length": -0.5}, "created_at": "4"}]
    assert aggregate(ev)["length"]["preference"] is None


def test_user_preference_not_overridden_and_reset_works(repo, pid):
    set_user_preference(repo, pid, "Essay", "length", "longer")
    for _ in range(5):
        record_feedback(repo, pid, None, "Essay", "clarity", "reject", SHORT, LONG)
    assert active_preferences(repo, pid, "Essay")["length"] == "longer"
    reset_learned_preference(repo, pid, "Essay", "length")
    assert "length" not in active_preferences(repo, pid, "Essay")
    record_feedback(repo, pid, None, "Essay", "clarity", "reject", SHORT, LONG)  # old events are ignored after reset
    assert "length" not in active_preferences(repo, pid, "Essay")


def test_invalid_user_preference_value(repo, pid):
    with pytest.raises(ValueError):
        set_user_preference(repo, pid, "Essay", "length", "banana")


def test_version_history_and_restore(repo, pid):
    set_user_preference(repo, pid, "Essay", "length", "shorter")
    set_user_preference(repo, pid, "Essay", "length", "longer")
    assert repo.latest_preference_version(pid) == 2
    repo.restore_preference_version(pid, 1)
    assert active_preferences(repo, pid, "Essay")["length"] == "shorter"
    assert repo.latest_preference_version(pid) == 3


def test_rejected_suggestions_not_treated_as_approved(repo, pid):
    repo.add_example(pid, "Essay", "Rejected rewrite about cats.", "rejected")
    repo.add_example(pid, "Essay", "Approved passage about cats.", "approved")
    got = retrieve_examples("cats", repo.list_examples(pid), "Essay", k=5)
    assert [e["text"] for e in got] == ["Approved passage about cats."]
    assert repo.counts(pid)["approved_examples"] == 1
    assert retrieve_examples("cats", [e for e in repo.list_examples(pid) if e["label"] == "rejected"], "Essay") == []


def test_retrieval_prefers_same_genre_and_relevance(repo, pid):
    repo.add_example(pid, "Essay", "Dogs and bones in the garden.", "approved")
    repo.add_example(pid, "Essay", "Quarterly budget forecasting methods.", "approved")
    repo.add_example(pid, "Informal", "Budget budget budget forecasting.", "approved")
    got = retrieve_examples("budget forecasting", repo.list_examples(pid), "Essay", k=2)
    assert got[0]["text"].startswith("Quarterly") and all(e["genre"] == "Essay" for e in got)
