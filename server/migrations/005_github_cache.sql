CREATE TABLE github_sources (
    repository_key TEXT PRIMARY KEY NOT NULL,
    project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    canonical_url TEXT NOT NULL UNIQUE,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE github_snapshot_cache (
    repository_key TEXT NOT NULL REFERENCES github_sources(repository_key) ON DELETE CASCADE,
    commit_sha TEXT NOT NULL CHECK(length(commit_sha) = 40),
    snapshot_id TEXT NOT NULL UNIQUE REFERENCES snapshots(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY(repository_key, commit_sha)
);

CREATE TABLE github_import_jobs (
    id TEXT PRIMARY KEY NOT NULL,
    repository_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    repository_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'succeeded', 'failed', 'interrupted')),
    stage TEXT NOT NULL CHECK(stage IN ('queued', 'resolving', 'downloading', 'extracting', 'scanning', 'saving', 'complete', 'error', 'interrupted')),
    progress INTEGER NOT NULL CHECK(progress BETWEEN 0 AND 100),
    commit_sha TEXT,
    project_id TEXT REFERENCES projects(id),
    snapshot_id TEXT REFERENCES snapshots(id),
    cache_hit INTEGER NOT NULL DEFAULT 0 CHECK(cache_hit IN (0, 1)),
    skipped_count INTEGER NOT NULL DEFAULT 0 CHECK(skipped_count >= 0),
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX github_jobs_created ON github_import_jobs(created_at DESC, id DESC);

ALTER TABLE runs ADD COLUMN result_cache_key TEXT;
CREATE INDEX runs_result_cache ON runs(result_cache_key, status, ended_at DESC);
