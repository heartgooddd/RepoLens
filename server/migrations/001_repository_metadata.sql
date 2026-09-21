CREATE TABLE projects (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
    source_type TEXT NOT NULL CHECK(source_type IN ('builtin', 'local_upload', 'github', 'test_fixture')),
    source_label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE snapshots (
    id TEXT PRIMARY KEY NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    revision TEXT NOT NULL,
    commit_sha TEXT,
    storage_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, revision)
);
CREATE INDEX snapshots_project_created ON snapshots(project_id, created_at DESC, id DESC);

CREATE TABLE folder_cards (
    id TEXT PRIMARY KEY NOT NULL,
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    claim_type TEXT NOT NULL CHECK(claim_type IN ('fact', 'inference', 'unverified')),
    UNIQUE(snapshot_id, path),
    UNIQUE(id, snapshot_id)
);

CREATE TABLE evidence_refs (
    id TEXT PRIMARY KEY NOT NULL,
    folder_card_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_start INTEGER NOT NULL CHECK(line_start >= 1),
    line_end INTEGER NOT NULL CHECK(line_end >= line_start),
    symbol TEXT,
    excerpt TEXT NOT NULL,
    FOREIGN KEY(folder_card_id, snapshot_id) REFERENCES folder_cards(id, snapshot_id) ON DELETE CASCADE
);
CREATE INDEX evidence_folder ON evidence_refs(folder_card_id);
