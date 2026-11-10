-- Statements must be safe to rerun, because this file runs each time the app starts.
-- The tables follow docs/data_model.md. Scores, due dates, and streaks are calculated, not stored.

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO app_meta (key, value) VALUES ('schema_version', '1');

CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK (category IN ('core', 'advanced')),
    tier TEXT NOT NULL CHECK (tier IN ('narrow', 'normal', 'broad')),
    family TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL,
    list_position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    link TEXT UNIQUE,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard', 'very hard')),
    rating INTEGER,
    source TEXT NOT NULL,
    is_custom INTEGER NOT NULL DEFAULT 0 CHECK (is_custom IN (0, 1)),
    catalog_position INTEGER,
    reserve_position INTEGER
);

CREATE TABLE IF NOT EXISTS problem_patterns (
    problem_id INTEGER NOT NULL REFERENCES problems (id) ON DELETE CASCADE,
    pattern_id INTEGER NOT NULL REFERENCES patterns (id),
    PRIMARY KEY (problem_id, pattern_id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES problems (id),
    date TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('solved_alone', 'solved_with_hints', 'solved_after_solution', 'not_solved')),
    time_seconds INTEGER CHECK (time_seconds IS NULL OR time_seconds >= 1),
    notes TEXT,
    entry_method TEXT NOT NULL CHECK (entry_method IN ('manual', 'csv', 'sync')),
    review_of_problem_id INTEGER REFERENCES problems (id)
);

CREATE INDEX IF NOT EXISTS attempts_by_problem ON attempts (problem_id, date);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY CHECK (key IN ('starting_difficulty', 'advanced_on', 'very_hard_on')),
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interviews (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    date TEXT NOT NULL,
    target_difficulty TEXT CHECK (target_difficulty IS NULL OR target_difficulty IN ('easy', 'medium', 'hard', 'very hard'))
);

CREATE TABLE IF NOT EXISTS interview_patterns (
    interview_id INTEGER NOT NULL REFERENCES interviews (id) ON DELETE CASCADE,
    pattern_id INTEGER NOT NULL REFERENCES patterns (id),
    PRIMARY KEY (interview_id, pattern_id)
);

CREATE TABLE IF NOT EXISTS hidden_sites (
    site TEXT NOT NULL CHECK (site IN ('leetcode', 'codeforces', 'cses', 'atcoder')),
    category TEXT NOT NULL CHECK (category IN ('core', 'advanced')),
    PRIMARY KEY (site, category)
);

CREATE TABLE IF NOT EXISTS pattern_preferences (
    pattern_id INTEGER PRIMARY KEY REFERENCES patterns (id),
    preference TEXT NOT NULL CHECK (preference IN ('target', 'mastered'))
);

CREATE TABLE IF NOT EXISTS sibling_suggestions (
    id INTEGER PRIMARY KEY,
    due_problem_id INTEGER NOT NULL REFERENCES problems (id) ON DELETE CASCADE,
    sibling_problem_id INTEGER NOT NULL REFERENCES problems (id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('active', 'dismissed')),
    date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS not_now (
    id INTEGER PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES problems (id) ON DELETE CASCADE,
    date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hint_reveals (
    id INTEGER PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES problems (id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0 CHECK (used IN (0, 1))
);

CREATE TABLE IF NOT EXISTS linked_accounts (
    site TEXT NOT NULL CHECK (site IN ('codeforces', 'atcoder', 'leetcode')),
    username TEXT NOT NULL,
    last_synced TEXT,
    PRIMARY KEY (site, username)
);

CREATE TABLE IF NOT EXISTS sync_items (
    id INTEGER PRIMARY KEY,
    site TEXT NOT NULL,
    username TEXT NOT NULL,
    problem_link TEXT NOT NULL,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    accepted INTEGER NOT NULL CHECK (accepted IN (0, 1)),
    rating INTEGER,
    tags TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'dismissed')),
    UNIQUE (site, problem_link, date)
);

CREATE TABLE IF NOT EXISTS rating_history (
    site TEXT NOT NULL,
    username TEXT NOT NULL,
    contest TEXT NOT NULL,
    date TEXT NOT NULL,
    rating INTEGER NOT NULL,
    PRIMARY KEY (site, username, contest)
);
