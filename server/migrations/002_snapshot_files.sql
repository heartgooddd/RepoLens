CREATE TABLE snapshot_files (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    sha256 TEXT NOT NULL,
    PRIMARY KEY(snapshot_id, path)
);
ALTER TABLE folder_cards ADD COLUMN inference TEXT;
