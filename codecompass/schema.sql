-- Statements must be safe to rerun, because this file runs each time the app starts.
-- Tables for problems, attempts, and reviews are added once the data model is designed.
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO app_meta (key, value) VALUES ('schema_version', '1');
