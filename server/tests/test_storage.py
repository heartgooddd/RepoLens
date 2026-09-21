import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.config import ROOT, Settings
from app.db import MIGRATIONS, connect, migrate
from app.models import ProjectDetail
from app.repository import create_project, get_project, list_projects


def test_repeated_migration_preserves_all_records(settings, detail):
    assert migrate(settings.database) == 1
    create_project(settings.database, detail)
    with connect(settings.database) as db:
        history = [tuple(row) for row in db.execute("SELECT * FROM schema_migrations")]
    for _ in range(3):
        assert migrate(settings.database) == 1
        assert get_project(settings.database, str(detail.project.id)) == detail
    with connect(settings.database) as db:
        assert history == [tuple(row) for row in db.execute("SELECT * FROM schema_migrations")]
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_upgrade_failure_rolls_back_and_corrected_upgrade_preserves_data(settings, detail, data_dir):
    migrate(settings.database)
    create_project(settings.database, detail)
    migrations = data_dir / "migrations"
    shutil.copytree(MIGRATIONS, migrations)
    next_file = migrations / "002_test_marker.sql"
    next_file.write_text("CREATE TABLE test_marker (id INTEGER);\nINVALID SQL;\n")
    with pytest.raises(sqlite3.OperationalError):
        migrate(settings.database, migrations)
    with connect(settings.database) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='test_marker'").fetchone() is None
        assert db.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 1
    next_file.write_text("CREATE TABLE test_marker (id INTEGER);\n")
    assert migrate(settings.database, migrations) == 2
    assert migrate(settings.database, migrations) == 2
    assert get_project(settings.database, str(detail.project.id)) == detail
    # Older code cannot open a newer schema silently.
    with pytest.raises(RuntimeError, match="incompatible"):
        migrate(settings.database)


def test_modified_migration_is_rejected(settings, data_dir):
    migrate(settings.database)
    migrations = data_dir / "migrations"
    shutil.copytree(MIGRATIONS, migrations)
    file = next(migrations.glob("*.sql"))
    file.write_text(file.read_text() + "\n-- modified\n")
    with pytest.raises(RuntimeError, match="modified"):
        migrate(settings.database, migrations)


def test_concurrent_startups_apply_once(settings):
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda _: migrate(settings.database), range(4))) == [1, 1, 1, 1]
    with connect(settings.database) as db:
        assert db.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 1


def test_atomic_write_and_database_constraints(settings, detail):
    migrate(settings.database)
    broken = detail.model_copy(deep=True)
    broken.snapshots[0].folder_cards.append(broken.snapshots[0].folder_cards[0])
    with pytest.raises(sqlite3.IntegrityError):
        create_project(settings.database, broken)
    assert list_projects(settings.database, 20, 0).total == 0
    create_project(settings.database, detail)
    with connect(settings.database) as db:
        # Composite FK disallows linking evidence to a different snapshot.
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE evidence_refs SET snapshot_id = ?", (str(uuid4()),))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE evidence_refs SET line_end = 0")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE folder_cards SET claim_type = 'invented'")
    assert get_project(settings.database, str(detail.project.id)) == detail


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "x/../file", "C:\\file", "x//file"])
def test_evidence_paths_are_relative(detail, path):
    data = detail.model_dump(mode="json")
    data["snapshots"][0]["folder_cards"][0]["evidence_refs"][0]["file_path"] = path
    with pytest.raises(ValidationError):
        ProjectDetail.model_validate(data)


def test_data_location_is_not_cwd(monkeypatch, data_dir):
    monkeypatch.delenv("REPOLENS_DATA_DIR", raising=False)
    monkeypatch.chdir(data_dir)
    assert Settings.from_env().data_dir == ROOT / "var"
    monkeypatch.setenv("REPOLENS_DATA_DIR", "relative/var")
    with pytest.raises(ValueError, match="absolute"):
        Settings.from_env()
