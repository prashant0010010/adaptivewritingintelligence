CREATE TABLE profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE genre_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    genre TEXT NOT NULL,
    features_json TEXT NOT NULL DEFAULT '{}',
    sample_count INTEGER NOT NULL DEFAULT 0,
    word_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE (profile_id, genre)
);

CREATE TABLE samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    genre TEXT NOT NULL,
    text TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'paste',
    status TEXT NOT NULL DEFAULT 'representative'
        CHECK (status IN ('representative','experimental','not_representative')),
    include_in_learning INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    sample_date TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_samples_profile_genre ON samples(profile_id, genre);

CREATE TABLE examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    genre TEXT NOT NULL,
    text TEXT NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('approved','rejected')),
    source_revision_id INTEGER,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX idx_examples_profile_label ON examples(profile_id, label, genre);

CREATE TABLE drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    genre TEXT NOT NULL,
    original_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_drafts_profile ON drafts(profile_id, created_at);

CREATE TABLE revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    parent_revision_id INTEGER REFERENCES revisions(id) ON DELETE SET NULL,
    kind TEXT NOT NULL CHECK (kind IN ('generated','user_edited','accepted_final')),
    mode TEXT NOT NULL,
    text TEXT NOT NULL,
    explanation_json TEXT NOT NULL DEFAULT '{}',
    quality_json TEXT NOT NULL DEFAULT '{}',
    provider TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','accepted','rejected')),
    style_rating INTEGER,
    satisfaction_rating INTEGER,
    runtime_seconds REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_revisions_draft ON revisions(draft_id, created_at);
CREATE INDEX idx_revisions_profile ON revisions(profile_id);

CREATE TABLE feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    revision_id INTEGER REFERENCES revisions(id) ON DELETE SET NULL,
    genre TEXT NOT NULL,
    mode TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('accept','reject','edit')),
    reason TEXT NOT NULL DEFAULT '',
    deltas_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX idx_feedback_profile_genre ON feedback_events(profile_id, genre, created_at);

CREATE TABLE preferences (
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    genre TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('learned','user','reset')),
    evidence_n INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, genre, key)
);

CREATE TABLE preference_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    change_note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (profile_id, version)
);

CREATE TABLE avoid_phrases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    phrase TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (profile_id, phrase)
);

CREATE TABLE onboarding_answers (
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    question_key TEXT NOT NULL,
    answer TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, question_key)
);

CREATE TABLE analysis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    content_md TEXT NOT NULL,
    data_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX idx_reports_profile_kind ON analysis_reports(profile_id, kind);

CREATE TABLE benchmark_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    genre TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
