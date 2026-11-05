CREATE TABLE login_limits (
    client TEXT PRIMARY KEY,
    failures INTEGER NOT NULL DEFAULT 0,
    blocked_until REAL NOT NULL DEFAULT 0,
    updated REAL NOT NULL
);
CREATE INDEX entries_occurred ON entries(occurred);
CREATE INDEX posts_published_created ON posts(published,created);
