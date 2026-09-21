CREATE TABLE runs (
    id TEXT PRIMARY KEY NOT NULL,
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
    mode TEXT NOT NULL CHECK(mode IN ('stub', 'pocketflow')),
    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'cancelling', 'cancelled', 'succeeded', 'failed', 'interrupted')),
    stage TEXT NOT NULL,
    language TEXT NOT NULL,
    topics INTEGER NOT NULL CHECK(topics BETWEEN 1 AND 10),
    scope TEXT NOT NULL,
    scenario TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    exit_code INTEGER,
    error TEXT,
    upstream_commit TEXT NOT NULL
);
CREATE INDEX runs_snapshot_created ON runs(snapshot_id, created_at DESC, id DESC);
CREATE TABLE artifacts (
    id TEXT PRIMARY KEY NOT NULL,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    sha256 TEXT NOT NULL,
    UNIQUE(run_id, path)
);
