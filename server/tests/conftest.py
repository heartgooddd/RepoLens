from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest

from app.config import ROOT, Settings
from app.models import ProjectDetail


@pytest.fixture
def data_dir():
    parent = ROOT / "var" / "tests"
    parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="m2-", dir=parent) as directory:
        yield Path(directory)


@pytest.fixture
def settings(data_dir):
    value = Settings(data_dir)
    value.prepare()
    return value


@pytest.fixture
def detail():
    project, snapshot, folder, evidence = [str(uuid4()) for _ in range(4)]
    return ProjectDetail.model_validate({
        "project": {
            "id": project, "name": "Persistence verification fixture",
            "source_type": "test_fixture", "source_label": "Synthetic fixture, not repository analysis",
            "created_at": "2026-09-21T00:00:00Z", "updated_at": "2026-09-21T00:00:00Z",
        },
        "snapshots": [{
            "id": snapshot, "project_id": project, "revision": "fixture-v1",
            "storage_path": f"snapshots/{snapshot}", "created_at": "2026-09-21T00:00:00Z",
            "folder_cards": [{
                "id": folder, "snapshot_id": snapshot, "path": ".", "title": "Fixture root",
                "description": "Test file defines a greeting.", "claim_type": "fact",
                "evidence_refs": [{
                    "id": evidence, "folder_card_id": folder, "snapshot_id": snapshot,
                    "file_path": "hello.py", "line_start": 1, "line_end": 2,
                    "symbol": "hello", "excerpt": "def hello():\n    return 'fixture'\n",
                }],
            }],
        }],
    })
