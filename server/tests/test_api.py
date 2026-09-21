import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.db import connect, migrate
from app.main import create_app
from app.repository import create_project


def test_empty_api_contract_and_validation(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json() == {"status": "ok", "database": "ok", "schema_version": 4}
        assert client.get("/api/projects").json() == {"items": [], "total": 0, "limit": 20, "offset": 0}
        assert client.get(f"/api/projects/{uuid4()}").status_code == 404
        for url in ("/api/projects/not-a-uuid", "/api/projects?limit=101", "/api/projects?offset=-1"):
            assert client.get(url).status_code == 422
        assert client.post("/api/projects").status_code == 405
        assert client.post("/api/projects/import", json={}).status_code == 422
        response = client.get("/api/projects", headers={"Origin": "http://127.0.0.1:5173"})
        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        response = client.get("/api/projects", headers={"Origin": "https://example.com"})
        assert "access-control-allow-origin" not in response.headers
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"]) >= {"/api/health", "/api/projects", "/api/projects/{project_id}", "/api/projects/import", "/api/snapshots/{snapshot_id}/source"}


def test_project_details_and_pagination(settings, detail):
    with TestClient(create_app(settings)) as client:
        create_project(settings.database, detail)
        response = client.get(f"/api/projects/{detail.project.id}")
        assert response.status_code == 200
        assert response.json() == detail.model_dump(mode="json")
        page = client.get("/api/projects?limit=1").json()
        assert page["items"][0]["id"] == str(detail.project.id)
        assert page["items"][0]["snapshot_count"] == 1
        assert client.get("/api/projects?offset=1").json() == {"items": [], "total": 1, "limit": 20, "offset": 1}


def test_health_reports_unavailable_database(settings):
    with TestClient(create_app(settings)) as client:
        with connect(settings.database) as db:
            db.execute("DROP TABLE schema_migrations")
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}


@contextmanager
def live_server(settings):
    # Bind before spawning and pass the open socket: no fixed port or port-selection race.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        port = listener.getsockname()[1]
        env = {**os.environ, "REPOLENS_DATA_DIR": str(settings.data_dir)}
        with (settings.data_dir / "server-test.log").open("a") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--fd", str(listener.fileno())],
                cwd=Path(__file__).resolve().parents[1], env=env,
                pass_fds=(listener.fileno(),), stdout=log, stderr=log,
            )
            try:
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=0.5, trust_env=False) as client:
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise AssertionError("Server exited during startup")
                        try:
                            if client.get("/api/health").status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.05)
                    else:
                        raise AssertionError("Server did not become ready in 10 seconds")
                    yield client
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def test_real_process_restart_preserves_project_and_snapshot(settings, detail):
    migrate(settings.database)
    snapshot = detail.snapshots[0]
    snapshot_dir = settings.data_dir / snapshot.storage_path
    snapshot_dir.mkdir()
    excerpt = snapshot.folder_cards[0].evidence_refs[0].excerpt
    (snapshot_dir / "hello.py").write_text(excerpt)
    create_project(settings.database, detail)
    with live_server(settings) as client:
        before = client.get(f"/api/projects/{detail.project.id}")
        assert before.status_code == 200
        assert before.json() == detail.model_dump(mode="json")
    # First process is fully stopped. Migration and second startup reuse the same file.
    assert migrate(settings.database) == 4
    with live_server(settings) as client:
        after = client.get(f"/api/projects/{detail.project.id}")
        assert after.status_code == 200
        assert after.json() == before.json()
        assert client.get("/api/projects").json()["total"] == 1
        assert (snapshot_dir / "hello.py").read_text() == excerpt
