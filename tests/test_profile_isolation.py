from core.profile_learning import record_feedback
from core.retrieval import retrieve_examples


def test_switching_profiles_never_leaks(repo):
    a, b = repo.create_profile("A"), repo.create_profile("B")
    repo.add_sample(a, "secret A", "Essay", "alpha text")
    repo.add_example(a, "Essay", "alpha approved", "approved")
    da = repo.create_draft(a, "dA", "Essay", "orig A")
    ra = repo.add_revision(a, da, "generated", "clarity", "rev A")
    repo.add_avoid_phrase(a, "leverage")
    repo.save_onboarding(a, {"audience": "tutors"})
    repo.set_preference(a, "Essay", "length", "shorter", "user")
    repo.add_feedback(a, ra, "Essay", "clarity", "accept")
    repo.save_report(a, "argument", "t", "md")
    repo.add_benchmark_case(a, "c", "Essay", "text")
    assert repo.list_samples(b) == [] and repo.list_examples(b) == [] and repo.list_drafts(b) == []
    assert repo.list_revisions(b, da) == [] and repo.list_avoid_phrases(b) == [] and repo.get_onboarding(b) == {}
    assert repo.get_preferences(b) == [] and repo.list_feedback(b) == [] and repo.list_reports(b) == []
    assert repo.list_benchmark_cases(b) == [] and repo.counts(b)["samples"] == 0 and repo.list_preference_versions(b) == []


def test_ids_from_other_profile_cannot_be_touched(repo):
    a, b = repo.create_profile("A"), repo.create_profile("B")
    s = repo.add_sample(a, "t", "Essay", "text")
    d = repo.create_draft(a, "d", "Essay", "orig")
    repo.delete_sample(b, s)
    repo.update_sample(b, s, title="hacked")
    assert repo.list_samples(a)[0]["title"] == "t"
    assert repo.get_draft(b, d) is None and repo.get_revision(b, 1) is None
    import pytest
    from database.db import DatabaseError
    with pytest.raises(DatabaseError):
        repo.add_revision(b, d, "generated", "clarity", "x")


def test_learning_is_per_profile(repo):
    a, b = repo.create_profile("A"), repo.create_profile("B")
    orig = "Short text here. " * 10
    longer = orig + "Extra sentence one. Extra sentence two. " * 5
    for _ in range(4):
        record_feedback(repo, a, None, "Essay", "clarity", "reject", orig, longer)
    assert repo.get_preferences(a) and repo.get_preferences(b) == []
    assert retrieve_examples("anything", repo.list_examples(b), "Essay") == []
