"""Persistence boundary. The future importer can write through create_project."""

from pathlib import Path

from .db import connect
from .models import ProjectDetail, ProjectList


def create_project(database: Path, detail: ProjectDetail) -> None:
    # Revalidate nested relationships even if a caller mutated an existing model.
    detail = ProjectDetail.model_validate(detail.model_dump(mode="json"))
    data = detail.model_dump(mode="json")
    with connect(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            def insert(table: str, row: dict) -> None:
                # Table/column names originate only from these fixed models, never request input.
                columns = ", ".join(row)
                parameters = ", ".join("?" for _ in row)
                connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({parameters})", tuple(row.values()))

            insert("projects", data["project"])
            for snapshot in data["snapshots"]:
                cards = snapshot.pop("folder_cards")
                insert("snapshots", snapshot)
                for card in cards:
                    evidence_refs = card.pop("evidence_refs")
                    insert("folder_cards", card)
                    for evidence in evidence_refs:
                        insert("evidence_refs", evidence)
            connection.commit()
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
