"""All database access. Every query is parameterised and scoped by profile_id."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from database.db import DatabaseError, session


def now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


class Repository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    # ---------- profiles ----------
    def create_profile(self, name: str, notes: str = "") -> int:
        name = (name or "").strip()
        if not name:
            raise DatabaseError("Profile name cannot be empty.")
        with session(self.db_path) as c:
            try:
                cur = c.execute("INSERT INTO profiles (name, notes, created_at) VALUES (?,?,?)", (name, notes, now()))
            except Exception as exc:
                raise DatabaseError(f"Could not create profile '{name}'. Is the name already used?") from exc
            return int(cur.lastrowid)

    def list_profiles(self) -> list[dict]:
        with session(self.db_path) as c:
            return _rows(c.execute("SELECT * FROM profiles ORDER BY name COLLATE NOCASE"))

    def get_profile(self, profile_id: int) -> Optional[dict]:
        with session(self.db_path) as c:
            r = c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
            return dict(r) if r else None

    def rename_profile(self, profile_id: int, name: str, notes: str) -> None:
        if not name.strip():
            raise DatabaseError("Profile name cannot be empty.")
        with session(self.db_path) as c:
            c.execute("UPDATE profiles SET name=?, notes=? WHERE id=?", (name.strip(), notes, profile_id))

    def delete_profile(self, profile_id: int) -> None:
        """Deletes the profile and, through ON DELETE CASCADE, all of its data."""
        with session(self.db_path) as c:
            c.execute("DELETE FROM profiles WHERE id=?", (profile_id,))

    # ---------- samples ----------
    def add_sample(self, profile_id: int, title: str, genre: str, text: str, source_type: str = "paste",
                   status: str = "representative", include: bool = True, notes: str = "",
                   sample_date: Optional[str] = None) -> int:
        if not text or not text.strip():
            raise DatabaseError("Refusing to save an empty sample.")
        with session(self.db_path) as c:
            cur = c.execute(
                "INSERT INTO samples (profile_id,title,genre,text,source_type,status,include_in_learning,notes,sample_date,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (profile_id, title.strip() or "Untitled", genre, text, source_type, status, int(include), notes, sample_date, now()))
            return int(cur.lastrowid)

    def list_samples(self, profile_id: int, genre: Optional[str] = None, learning_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM samples WHERE profile_id=?"
        args: list[Any] = [profile_id]
        if genre:
            sql += " AND genre=?"
            args.append(genre)
        if learning_only:
            sql += " AND include_in_learning=1 AND status!='not_representative'"
        sql += " ORDER BY created_at DESC"
        with session(self.db_path) as c:
            return _rows(c.execute(sql, args))

    def update_sample(self, profile_id: int, sample_id: int, **fields) -> None:
        allowed = {"title", "genre", "status", "include_in_learning", "notes", "text"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        sql = "UPDATE samples SET " + ",".join(f"{k}=?" for k in sets) + " WHERE id=? AND profile_id=?"
        with session(self.db_path) as c:
            c.execute(sql, [*sets.values(), sample_id, profile_id])

    def delete_sample(self, profile_id: int, sample_id: int) -> None:
        with session(self.db_path) as c:
            c.execute("DELETE FROM samples WHERE id=? AND profile_id=?", (sample_id, profile_id))

    # ---------- examples ----------
    def add_example(self, profile_id: int, genre: str, text: str, label: str = "approved",
                    source_revision_id: Optional[int] = None, note: str = "") -> int:
        if label not in ("approved", "rejected"):
            raise DatabaseError("Example label must be 'approved' or 'rejected'.")
        if not text.strip():
            raise DatabaseError("Cannot save an empty example.")
        with session(self.db_path) as c:
            cur = c.execute("INSERT INTO examples (profile_id,genre,text,label,source_revision_id,note,created_at) VALUES (?,?,?,?,?,?,?)",
                            (profile_id, genre, text, label, source_revision_id, note, now()))
            return int(cur.lastrowid)

    def list_examples(self, profile_id: int, label: Optional[str] = None, genre: Optional[str] = None) -> list[dict]:
        sql, args = "SELECT * FROM examples WHERE profile_id=?", [profile_id]
        if label:
            sql += " AND label=?"; args.append(label)
        if genre:
            sql += " AND genre=?"; args.append(genre)
        with session(self.db_path) as c:
            return _rows(c.execute(sql + " ORDER BY created_at DESC", args))

    def delete_example(self, profile_id: int, example_id: int) -> None:
        with session(self.db_path) as c:
            c.execute("DELETE FROM examples WHERE id=? AND profile_id=?", (example_id, profile_id))

    # ---------- drafts and revisions ----------
    def create_draft(self, profile_id: int, title: str, genre: str, text: str) -> int:
        with session(self.db_path) as c:
            cur = c.execute("INSERT INTO drafts (profile_id,title,genre,original_text,created_at) VALUES (?,?,?,?,?)",
                            (profile_id, title.strip() or "Untitled draft", genre, text, now()))
            return int(cur.lastrowid)

    def get_draft(self, profile_id: int, draft_id: int) -> Optional[dict]:
        with session(self.db_path) as c:
            r = c.execute("SELECT * FROM drafts WHERE id=? AND profile_id=?", (draft_id, profile_id)).fetchone()
            return dict(r) if r else None

    def list_drafts(self, profile_id: int, limit: int = 50) -> list[dict]:
        with session(self.db_path) as c:
            return _rows(c.execute("SELECT * FROM drafts WHERE profile_id=? ORDER BY created_at DESC LIMIT ?", (profile_id, limit)))

    def delete_draft(self, profile_id: int, draft_id: int) -> None:
        with session(self.db_path) as c:
            c.execute("DELETE FROM drafts WHERE id=? AND profile_id=?", (draft_id, profile_id))

    def add_revision(self, profile_id: int, draft_id: int, kind: str, mode: str, text: str,
                     parent_revision_id: Optional[int] = None, explanation: Optional[dict] = None,
                     quality: Optional[dict] = None, provider: str = "", status: str = "proposed",
                     runtime_seconds: Optional[float] = None) -> int:
        if not self.get_draft(profile_id, draft_id):
            raise DatabaseError("Draft not found for this profile.")
        with session(self.db_path) as c:
            cur = c.execute(
                "INSERT INTO revisions (draft_id,profile_id,parent_revision_id,kind,mode,text,explanation_json,quality_json,provider,status,runtime_seconds,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (draft_id, profile_id, parent_revision_id, kind, mode, text, json.dumps(explanation or {}),
                 json.dumps(quality or {}), provider, status, runtime_seconds, now()))
            return int(cur.lastrowid)

    def get_revision(self, profile_id: int, revision_id: int) -> Optional[dict]:
        with session(self.db_path) as c:
            r = c.execute("SELECT * FROM revisions WHERE id=? AND profile_id=?", (revision_id, profile_id)).fetchone()
            return dict(r) if r else None

    def list_revisions(self, profile_id: int, draft_id: int) -> list[dict]:
        with session(self.db_path) as c:
            return _rows(c.execute("SELECT * FROM revisions WHERE draft_id=? AND profile_id=? ORDER BY created_at", (draft_id, profile_id)))

    def list_recent_revisions(self, profile_id: int, limit: int = 20) -> list[dict]:
        with session(self.db_path) as c:
            return _rows(c.execute("SELECT * FROM revisions WHERE profile_id=? ORDER BY created_at DESC LIMIT ?", (profile_id, limit)))

    def set_revision_status(self, profile_id: int, revision_id: int, status: str,
                            style_rating: Optional[int] = None, satisfaction_rating: Optional[int] = None) -> None:
        with session(self.db_path) as c:
            c.execute("UPDATE revisions SET status=?, style_rating=COALESCE(?,style_rating), satisfaction_rating=COALESCE(?,satisfaction_rating) WHERE id=? AND profile_id=?",
                      (status, style_rating, satisfaction_rating, revision_id, profile_id))

    # ---------- feedback ----------
    def add_feedback(self, profile_id: int, revision_id: Optional[int], genre: str, mode: str, action: str,
                     reason: str = "", deltas: Optional[dict] = None) -> int:
        with session(self.db_path) as c:
            cur = c.execute("INSERT INTO feedback_events (profile_id,revision_id,genre,mode,action,reason,deltas_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                            (profile_id, revision_id, genre, mode, action, reason, json.dumps(deltas or {}), now()))
            return int(cur.lastrowid)

    def list_feedback(self, profile_id: int, genre: Optional[str] = None) -> list[dict]:
        sql, args = "SELECT * FROM feedback_events WHERE profile_id=?", [profile_id]
        if genre:
            sql += " AND genre=?"; args.append(genre)
        with session(self.db_path) as c:
            rows = _rows(c.execute(sql + " ORDER BY created_at", args))
        for r in rows:
            r["deltas"] = json.loads(r.pop("deltas_json") or "{}")
        return rows

    # ---------- preferences ----------
    def get_preferences(self, profile_id: int, genre: Optional[str] = None) -> list[dict]:
        sql, args = "SELECT * FROM preferences WHERE profile_id=?", [profile_id]
        if genre:
            sql += " AND genre=?"; args.append(genre)
        with session(self.db_path) as c:
            return _rows(c.execute(sql + " ORDER BY genre,key", args))

    def set_preference(self, profile_id: int, genre: str, key: str, value: str, source: str, evidence_n: int = 0) -> None:
        with session(self.db_path) as c:
            c.execute("INSERT INTO preferences (profile_id,genre,key,value,source,evidence_n,updated_at) VALUES (?,?,?,?,?,?,?)"
                      " ON CONFLICT(profile_id,genre,key) DO UPDATE SET value=excluded.value, source=excluded.source,"
                      " evidence_n=excluded.evidence_n, updated_at=excluded.updated_at",
                      (profile_id, genre, key, value, source, evidence_n, now()))

    def delete_preference(self, profile_id: int, genre: str, key: str) -> None:
        with session(self.db_path) as c:
            c.execute("DELETE FROM preferences WHERE profile_id=? AND genre=? AND key=?", (profile_id, genre, key))

    def latest_preference_version(self, profile_id: int) -> int:
        with session(self.db_path) as c:
            r = c.execute("SELECT COALESCE(MAX(version),0) FROM preference_versions WHERE profile_id=?", (profile_id,)).fetchone()
            return int(r[0])

    def snapshot_preferences(self, profile_id: int, note: str) -> int:
        prefs = self.get_preferences(profile_id)
        avoid = [a["phrase"] for a in self.list_avoid_phrases(profile_id)]
        version = self.latest_preference_version(profile_id) + 1
        with session(self.db_path) as c:
            c.execute("INSERT INTO preference_versions (profile_id,version,snapshot_json,change_note,created_at) VALUES (?,?,?,?,?)",
                      (profile_id, version, json.dumps({"preferences": prefs, "avoid_phrases": avoid}), note, now()))
        return version

    def list_preference_versions(self, profile_id: int) -> list[dict]:
        with session(self.db_path) as c:
            return _rows(c.execute("SELECT * FROM preference_versions WHERE profile_id=? ORDER BY version DESC", (profile_id,)))

    def restore_preference_version(self, profile_id: int, version: int) -> None:
        with session(self.db_path) as c:
            r = c.execute("SELECT snapshot_json FROM preference_versions WHERE profile_id=? AND version=?", (profile_id, version)).fetchone()
        if not r:
            raise DatabaseError("That preference version does not exist for this profile.")
        snap = json.loads(r["snapshot_json"])
        with session(self.db_path) as c:
            c.execute("DELETE FROM preferences WHERE profile_id=?", (profile_id,))
            for p in snap.get("preferences", []):
                c.execute("INSERT INTO preferences (profile_id,genre,key,value,source,evidence_n,updated_at) VALUES (?,?,?,?,?,?,?)",
                          (profile_id, p["genre"], p["key"], p["value"], p["source"], p["evidence_n"], now()))
            c.execute("DELETE FROM avoid_phrases WHERE profile_id=?", (profile_id,))
            for ph in snap.get("avoid_phrases", []):
                c.execute("INSERT INTO avoid_phrases (profile_id,phrase,created_at) VALUES (?,?,?)", (profile_id, ph, now()))
        self.snapshot_preferences(profile_id, f"Restored from version {version}")

    # ---------- avoid phrases, onboarding ----------
    def add_avoid_phrase(self, profile_id: int, phrase: str) -> None:
        phrase = phrase.strip()
        if not phrase:
            return
        with session(self.db_path) as c:
            c.execute("INSERT OR IGNORE INTO avoid_phrases (profile_id,phrase,created_at) VALUES (?,?,?)", (profile_id, phrase, now()))

    def list_avoid_phrases(self, profile_id: int) -> list[dict]:
        with session(self.db_path) as c:
            return _rows(c.execute("SELECT * FROM avoid_phrases WHERE profile_id=? ORDER BY phrase", (profile_id,)))

    def delete_avoid_phrase(self, profile_id: int, phrase: str) -> None:
        with session(self.db_path) as c:
            c.execute("DELETE FROM avoid_phrases WHERE profile_id=? AND phrase=?", (profile_id, phrase))

    def save_onboarding(self, profile_id: int, answers: dict[str, str]) -> None:
        with session(self.db_path) as c:
            for k, v in answers.items():
                if v and v.strip():
                    c.execute("INSERT INTO onboarding_answers (profile_id,question_key,answer,updated_at) VALUES (?,?,?,?)"
                              " ON CONFLICT(profile_id,question_key) DO UPDATE SET answer=excluded.answer, updated_at=excluded.updated_at",
                              (profile_id, k, v.strip(), now()))
                else:
                    c.execute("DELETE FROM onboarding_answers WHERE profile_id=? AND question_key=?", (profile_id, k))

    def get_onboarding(self, profile_id: int) -> dict[str, str]:
        with session(self.db_path) as c:
            return {r["question_key"]: r["answer"] for r in c.execute("SELECT * FROM onboarding_answers WHERE profile_id=?", (profile_id,))}

    # ---------- genre cache, reports, benchmarks, settings ----------
    def save_genre_profile(self, profile_id: int, genre: str, features: dict, sample_count: int, word_count: int) -> None:
        with session(self.db_path) as c:
            c.execute("INSERT INTO genre_profiles (profile_id,genre,features_json,sample_count,word_count,updated_at) VALUES (?,?,?,?,?,?)"
                      " ON CONFLICT(profile_id,genre) DO UPDATE SET features_json=excluded.features_json, sample_count=excluded.sample_count,"
                      " word_count=excluded.word_count, updated_at=excluded.updated_at",
                      (profile_id, genre, json.dumps(features, default=str), sample_count, word_count, now()))

    def list_genre_profiles(self, profile_id: int) -> list[dict]:
        with session(self.db_path) as c:
            rows = _rows(c.execute("SELECT * FROM genre_profiles WHERE profile_id=? ORDER BY genre", (profile_id,)))
        for r in rows:
            r["features"] = json.loads(r.pop("features_json") or "{}")
        return rows

    def save_report(self, profile_id: int, kind: str, title: str, content_md: str, data: Optional[dict] = None) -> int:
        with session(self.db_path) as c:
            cur = c.execute("INSERT INTO analysis_reports (profile_id,kind,title,content_md,data_json,created_at) VALUES (?,?,?,?,?,?)",
                            (profile_id, kind, title, content_md, json.dumps(data or {}, default=str), now()))
            return int(cur.lastrowid)

    def list_reports(self, profile_id: int, kind: Optional[str] = None, limit: int = 20) -> list[dict]:
        sql, args = "SELECT * FROM analysis_reports WHERE profile_id=?", [profile_id]
        if kind:
            sql += " AND kind=?"; args.append(kind)
        with session(self.db_path) as c:
            return _rows(c.execute(sql + " ORDER BY created_at DESC LIMIT ?", [*args, limit]))

    def add_benchmark_case(self, profile_id: int, title: str, genre: str, text: str) -> int:
        with session(self.db_path) as c:
            cur = c.execute("INSERT INTO benchmark_cases (profile_id,title,genre,text,created_at) VALUES (?,?,?,?,?)",
                            (profile_id, title, genre, text, now()))
            return int(cur.lastrowid)

    def list_benchmark_cases(self, profile_id: int) -> list[dict]:
        with session(self.db_path) as c:
            return _rows(c.execute("SELECT * FROM benchmark_cases WHERE profile_id=? ORDER BY created_at", (profile_id,)))

    def delete_benchmark_case(self, profile_id: int, case_id: int) -> None:
        with session(self.db_path) as c:
            c.execute("DELETE FROM benchmark_cases WHERE id=? AND profile_id=?", (case_id, profile_id))

    def get_setting(self, key: str, default: str = "") -> str:
        with session(self.db_path) as c:
            r = c.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
            return r["value"] if r else default

    def set_setting(self, key: str, value: str) -> None:
        with session(self.db_path) as c:
            c.execute("INSERT INTO app_settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    # ---------- counts ----------
    def counts(self, profile_id: int) -> dict:
        q = {
            "samples": "SELECT COUNT(*) FROM samples WHERE profile_id=?",
            "samples_in_learning": "SELECT COUNT(*) FROM samples WHERE profile_id=? AND include_in_learning=1 AND status!='not_representative'",
            "approved_examples": "SELECT COUNT(*) FROM examples WHERE profile_id=? AND label='approved'",
            "rejected_examples": "SELECT COUNT(*) FROM examples WHERE profile_id=? AND label='rejected'",
            "feedback": "SELECT COUNT(*) FROM feedback_events WHERE profile_id=?",
            "drafts": "SELECT COUNT(*) FROM drafts WHERE profile_id=?",
            "revisions": "SELECT COUNT(*) FROM revisions WHERE profile_id=?",
        }
        with session(self.db_path) as c:
            return {k: int(c.execute(sql, (profile_id,)).fetchone()[0]) for k, sql in q.items()}
