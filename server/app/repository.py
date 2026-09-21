"""Transactional persistence boundary for local and GitHub repository snapshots."""

from pathlib import Path
from .db import connect
from .models import GitHubRepositoryRef, Project, ProjectDetail, ProjectList, Snapshot


def _insert(connection, table: str, row: dict) -> None:
    # Table/column names originate only from fixed models, never request input.
    columns = ", ".join(row)
    parameters = ", ".join("?" for _ in row)
    connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({parameters})", tuple(row.values()))


def _insert_snapshot(connection, snapshot: dict) -> None:
    cards = snapshot.pop("folder_cards")
    files = snapshot.pop("files")
    _insert(connection, "snapshots", snapshot)
    for file in files:
        _insert(connection, "snapshot_files", {"snapshot_id": snapshot["id"], **file})
    for card in cards:
        evidence_refs = card.pop("evidence_refs")
        _insert(connection, "folder_cards", card)
        for evidence in evidence_refs:
            _insert(connection, "evidence_refs", evidence)


def create_project(database: Path, detail: ProjectDetail) -> None:
    # Revalidate nested relationships even if a caller mutated an existing model.
    detail = ProjectDetail.model_validate(detail.model_dump(mode="json"))
    data = detail.model_dump(mode="json")
    with connect(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            _insert(connection, "projects", data["project"])
            for snapshot in data["snapshots"]:
                _insert_snapshot(connection, snapshot)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def get_cached_github_snapshot(database: Path, repository_key: str, commit_sha: str):
    with connect(database) as connection:
        return connection.execute("""SELECT s.project_id, c.snapshot_id FROM github_snapshot_cache c
                                     JOIN snapshots s ON s.id = c.snapshot_id
                                     WHERE c.repository_key = ? AND c.commit_sha = ?""",
                                  (repository_key, commit_sha)).fetchone()


def create_github_snapshot(database: Path, source: GitHubRepositoryRef, project: Project, snapshot: Snapshot) -> str:
    # Validate the new aggregate before opening the write transaction.
    ProjectDetail(project=project, snapshots=[snapshot])
    source_data = source.model_dump(mode="json")
    project_data = project.model_dump(mode="json")
    snapshot_data = snapshot.model_dump(mode="json")
    timestamp = project_data["updated_at"]
    with connect(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                "SELECT project_id FROM github_sources WHERE repository_key = ?", (source.repository_key,)
            ).fetchone()
            if existing:
                project_id = existing["project_id"]
                snapshot_data["project_id"] = project_id
                connection.execute("UPDATE projects SET updated_at = ?, source_label = ? WHERE id = ?",
                                   (timestamp, source.canonical_url, project_id))
                connection.execute("UPDATE github_sources SET updated_at = ?, canonical_url = ? WHERE repository_key = ?",
                                   (timestamp, source.canonical_url, source.repository_key))
            else:
                project_id = str(project.id)
                _insert(connection, "projects", project_data)
                connection.execute("INSERT INTO github_sources VALUES (?,?,?,?,?,?,?)", (
                    source.repository_key, project_id, source.canonical_url, source.owner, source.repo,
                    project_data["created_at"], timestamp,
                ))
            _insert_snapshot(connection, snapshot_data)
            connection.execute("INSERT INTO github_snapshot_cache VALUES (?,?,?,?)",
                               (source.repository_key, snapshot.commit_sha, str(snapshot.id), timestamp))
            connection.commit()
            return project_id
        except BaseException:
            connection.rollback()
            raise


def list_projects(database: Path, limit: int, offset: int) -> ProjectList:
    with connect(database) as connection:
        connection.execute("BEGIN")
        total = connection.execute("SELECT count(*) FROM projects").fetchone()[0]
        rows = connection.execute("""
            SELECT p.*, (SELECT count(*) FROM snapshots s WHERE s.project_id = p.id) AS snapshot_count
            FROM projects p ORDER BY p.created_at DESC, p.id DESC LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
        return ProjectList(items=[dict(row) for row in rows], total=total, limit=limit, offset=offset)


def get_project(database: Path, project_id: str) -> ProjectDetail | None:
    with connect(database) as connection:
        connection.execute("BEGIN")
        project = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if project is None:
            return None
        snapshots = []
        for row in connection.execute(
            "SELECT * FROM snapshots WHERE project_id = ? ORDER BY created_at DESC, id DESC", (project_id,)
        ).fetchall():
            snapshot = dict(row)
            snapshot["files"] = [dict(file) for file in connection.execute(
                "SELECT path, size_bytes, sha256 FROM snapshot_files WHERE snapshot_id = ? ORDER BY path",
                (row["id"],),
            )]
            cards = []
            for card_row in connection.execute(
                "SELECT * FROM folder_cards WHERE snapshot_id = ? ORDER BY path", (row["id"],)
            ).fetchall():
                card = dict(card_row)
                card["evidence_refs"] = [dict(ref) for ref in connection.execute(
                    "SELECT * FROM evidence_refs WHERE folder_card_id = ? ORDER BY file_path, line_start, id",
                    (card["id"],),
                )]
                cards.append(card)
            snapshot["folder_cards"] = cards
            snapshots.append(snapshot)
        return ProjectDetail(project=dict(project), snapshots=snapshots)
