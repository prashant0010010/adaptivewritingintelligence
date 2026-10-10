import pytest

from database.db import DatabaseError, backup_db, init_db, restore_db, schema_version
from database.repository import Repository


def test_creation_and_version(tmp_path):
    db = tmp_path / "x.db"
    assert init_db(db) >= 1
    assert schema_version(db) >= 1
    assert init_db(db) == schema_version(db)  # idempotent


def test_persistence_across_instances(tmp_path):
    db = tmp_path / "x.db"
    init_db(db)
    p = Repository(db).create_profile("A")
    Repository(db).add_sample(p, "t", "Essay", "some text here")
    assert len(Repository(db).list_samples(p)) == 1


def test_empty_sample_rejected(repo, pid):
    with pytest.raises(DatabaseError):
        repo.add_sample(pid, "t", "Essay", "   ")


def test_duplicate_profile_name(repo):
    repo.create_profile("Same")
    with pytest.raises(DatabaseError):
        repo.create_profile("Same")


def test_sample_inclusion_and_exclusion(repo, pid):
    a = repo.add_sample(pid, "a", "Essay", "text a")
    b = repo.add_sample(pid, "b", "Essay", "text b", status="not_representative")
    c = repo.add_sample(pid, "c", "Essay", "text c", include=False)
    ids = {s["id"] for s in repo.list_samples(pid, learning_only=True)}
    assert ids == {a}
    repo.update_sample(pid, c, include_in_learning=1)
    assert c in {s["id"] for s in repo.list_samples(pid, learning_only=True)}


def test_delete_sample_and_profile_cascade(repo, pid):
    s = repo.add_sample(pid, "a", "Essay", "text a")
    d = repo.create_draft(pid, "d", "Essay", "orig")
    repo.add_revision(pid, d, "generated", "clarity", "rev")
    repo.delete_sample(pid, s)
    assert repo.list_samples(pid) == []
    repo.delete_profile(pid)
    assert repo.list_drafts(pid) == [] and repo.get_profile(pid) is None


def test_revision_history_chain(repo, pid):
    d = repo.create_draft(pid, "d", "Essay", "orig")
    r1 = repo.add_revision(pid, d, "generated", "clarity", "v1")
    r2 = repo.add_revision(pid, d, "user_edited", "clarity", "v2", parent_revision_id=r1, status="accepted")
    revs = repo.list_revisions(pid, d)
    assert [r["id"] for r in revs] == [r1, r2] and revs[1]["parent_revision_id"] == r1


def test_backup_and_restore(tmp_path, repo, pid):
    backup = backup_db(repo.db_path, tmp_path / "bk")
    repo.create_profile("Later")
    restore_db(backup, repo.db_path)
    assert [p["name"] for p in repo.list_profiles()] == ["Tester"]


def test_restore_rejects_garbage(tmp_path, repo):
    bad = tmp_path / "bad.db"
    bad.write_text("not a database")
    with pytest.raises(DatabaseError):
        restore_db(bad, repo.db_path)


def test_sql_injection_is_inert(repo):
    pid = repo.create_profile("x'); DROP TABLE profiles;--")
    assert repo.get_profile(pid)["name"].startswith("x'")
