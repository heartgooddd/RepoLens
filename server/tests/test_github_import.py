import asyncio
import io
import tarfile
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.github_importer import MAX_ARCHIVE_BYTES, MAX_ARCHIVE_FILES, read_archive
from app.main import create_app
from app import github_importer


POCKETFLOW_URL = "https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge"
COMMIT_A = "05b24cbbb0fe409c5e23c9791f0342f07524ffdc"
COMMIT_B = "15b24cbbb0fe409c5e23c9791f0342f07524ffdc"


def archive(commit: str, files: dict[str, bytes] | None = None) -> bytes:
    files = files or {
        "main.py": b"def main():\n    return 42\n",
        "flow.py": b"def create_tutorial_flow():\n    return None\n",
        "utils/call_llm.py": b"def call_llm(prompt):\n    return prompt\n",
        ".env": b"SHOULD_NOT_BE_SAVED",
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        root = f"PocketFlow-Tutorial-Codebase-Knowledge-{commit}"
        for path, raw in files.items():
            entry = tarfile.TarInfo(f"{root}/{path}")
            entry.size = len(raw)
            bundle.addfile(entry, io.BytesIO(raw))
    return buffer.getvalue()


class GitHubFixture:
    def __init__(self):
        self.commit = COMMIT_A
        self.repo_status = 200
        self.rate_limited = False
        self.archive_files = None
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if request.url.host == "api.github.com" and request.url.path.endswith("/PocketFlow-Tutorial-Codebase-Knowledge"):
            if self.rate_limited:
                return httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1790000000"}, json={"message": "API rate limit exceeded"})
            return httpx.Response(self.repo_status, json={
                "name": "PocketFlow-Tutorial-Codebase-Knowledge",
                "full_name": "The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge",
                "default_branch": "main",
                "private": False,
            })
        if request.url.host == "api.github.com" and "/commits/" in request.url.path:
            return httpx.Response(200, json={"sha": self.commit})
        if request.url.host == "codeload.github.com":
            return httpx.Response(200, content=archive(self.commit, self.archive_files))
        return httpx.Response(500, json={"message": f"unexpected URL {request.url}"})


def wait_for_terminal(client: TestClient, path: str, active: tuple[str, ...], timeout: float = 3) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = client.get(path).json()
        if value["status"] not in active:
            return value
        time.sleep(0.01)
    raise AssertionError(f"Operation did not finish: {value}")


def wait_for_job(client: TestClient, job_id: str, timeout: float = 3) -> dict:
    return wait_for_terminal(client, f"/api/github-imports/{job_id}", ("queued", "running"), timeout)


def start(client: TestClient, url: str = POCKETFLOW_URL) -> dict:
    response = client.post("/api/github-imports", json={"repository_url": url})
    assert response.status_code == 202, response.text
    assert response.json()["status"] in {"queued", "running"}
    return wait_for_job(client, response.json()["id"])


@pytest.mark.parametrize("url", [
    "", "owner/repo", "http://github.com/owner/repo", "https://gitlab.com/owner/repo",
    "https://github.com/owner", "https://github.com/owner/repo/issues", "https://user@github.com/owner/repo",
    "https://github.com/owner/repo?tab=readme", "https://github.com/owner/repo#readme",
])
def test_invalid_github_urls_fail_before_creating_a_job(settings, url):
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/github-imports", json={"repository_url": url})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_github_url"


def test_import_pins_commit_reuses_snapshot_and_never_saves_filtered_secrets(settings):
    fixture = GitHubFixture()
    app = create_app(settings)
    app.state.github_importer.transport = httpx.MockTransport(fixture)
    with TestClient(app) as client:
        first = start(client, POCKETFLOW_URL + ".git/")
        assert first["status"] == "succeeded" and first["progress"] == 100
        assert first["stage"] == "complete" and first["commit_sha"] == COMMIT_A
        assert first["canonical_url"] == POCKETFLOW_URL
        assert first["cache_hit"] is False
        detail = client.get(f"/api/projects/{first['project_id']}").json()
        snapshot = detail["snapshots"][0]
        assert snapshot["id"] == first["snapshot_id"]
        assert snapshot["commit_sha"] == COMMIT_A
        assert {item["path"] for item in snapshot["files"]} == {"main.py", "flow.py", "utils/call_llm.py"}
        assert not (settings.data_dir / snapshot["storage_path"] / ".env").exists()

        run_response = client.post('/api/runs', json={'snapshot_id': snapshot['id'], 'scope': '.', 'language': 'zh', 'topics': 3})
        assert run_response.status_code == 201
        run = wait_for_job_like_run(client, run_response.json()['id'])
        assert run['status'] == 'succeeded' and run['snapshot_id'] == snapshot['id']
        assert (settings.data_dir / 'runs' / run['id'] / 'input' / 'main.py').read_bytes() == (settings.data_dir / snapshot['storage_path'] / 'main.py').read_bytes()

        second = start(client, POCKETFLOW_URL)
        assert second["cache_hit"] is True
        assert (second["project_id"], second["snapshot_id"]) == (first["project_id"], first["snapshot_id"])
        assert client.get("/api/projects").json()["total"] == 1
        assert client.get(f"/api/projects/{first['project_id']}").json()["snapshots"] == detail["snapshots"]
        assert len([url for url in fixture.calls if "codeload.github.com" in url]) == 1


def test_new_default_branch_commit_adds_a_version_to_the_same_project(settings):
    fixture = GitHubFixture()
    app = create_app(settings)
    app.state.github_importer.transport = httpx.MockTransport(fixture)
    with TestClient(app) as client:
        first = start(client)
        fixture.commit = COMMIT_B
        fixture.archive_files = {"main.py": b"def main():\n    return 'version-b'\n"}
        second = start(client)
        assert second["status"] == "succeeded" and second["cache_hit"] is False
        assert second["project_id"] == first["project_id"]
        assert second["snapshot_id"] != first["snapshot_id"]
        detail = client.get(f"/api/projects/{first['project_id']}").json()
        assert [item["commit_sha"] for item in detail["snapshots"]] == [COMMIT_B, COMMIT_A]
        current = detail["snapshots"][0]
        source = client.get(f"/api/snapshots/{current['id']}/source", params={"path": "main.py"}).json()
        assert "version-b" in source["content"]


@pytest.mark.parametrize("setup,code", [
    (lambda fixture: setattr(fixture, "repo_status", 404), "github_repository_not_found"),
    (lambda fixture: setattr(fixture, "rate_limited", True), "github_rate_limited"),
])
def test_remote_errors_have_stable_codes_and_do_not_create_projects(settings, setup, code):
    fixture = GitHubFixture()
    setup(fixture)
    app = create_app(settings)
    app.state.github_importer.transport = httpx.MockTransport(fixture)
    with TestClient(app) as client:
        job = start(client)
        assert job["status"] == "failed" and job["stage"] == "error"
        assert job["error_code"] == code and job["error_message"]
        assert client.get("/api/projects").json()["total"] == 0
        assert list((settings.data_dir / "snapshots").iterdir()) == []


def test_archive_paths_must_stay_inside_one_repository_root(settings):
    fixture = GitHubFixture()
    fixture.archive_files = {"../../escape.py": b"print('escape')\n"}
    app = create_app(settings)
    app.state.github_importer.transport = httpx.MockTransport(fixture)
    with TestClient(app) as client:
        job = start(client)
        assert job["status"] == "failed"
        assert job["error_code"] == "unsafe_archive"
        assert not (settings.data_dir / "escape.py").exists()
        assert list((settings.data_dir / "snapshots").iterdir()) == []


def wait_for_job_like_run(client: TestClient, run_id: str, timeout: float = 3) -> dict:
    return wait_for_terminal(client, f'/api/runs/{run_id}', ('queued', 'running', 'cancelling'), timeout)


def test_archive_byte_and_entry_limits_are_enforced_before_writes():
    with pytest.raises(Exception) as too_many_bytes:
        read_archive(b'x' * (MAX_ARCHIVE_BYTES + 1))
    assert too_many_bytes.value.detail['code'] == 'github_archive_too_large'

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as bundle:
        for index in range(MAX_ARCHIVE_FILES + 1):
            entry = tarfile.TarInfo(f'root/files/{index}.bin')
            entry.size = 0
            bundle.addfile(entry, io.BytesIO())
    with pytest.raises(Exception) as too_many_entries:
        read_archive(buffer.getvalue())
    assert too_many_entries.value.detail['code'] == 'github_archive_too_large'


def test_network_timeout_becomes_a_stable_failed_job(settings):
    def timeout(_: httpx.Request):
        raise httpx.ReadTimeout('fixture timeout')
    app = create_app(settings)
    app.state.github_importer.transport = httpx.MockTransport(timeout)
    with TestClient(app) as client:
        job = start(client)
        assert job['status'] == 'failed'
        assert job['error_code'] == 'github_timeout'
        assert client.get('/api/projects').json()['total'] == 0


def test_scanning_stage_is_visible_while_scanner_is_actually_running(settings, monkeypatch):
    fixture = GitHubFixture()
    entered, release = threading.Event(), threading.Event()
    real_scan = github_importer.scan

    def paused_scan(files, snapshot_id):
        entered.set()
        assert release.wait(2)
        return real_scan(files, snapshot_id)

    monkeypatch.setattr(github_importer, 'scan', paused_scan)
    app = create_app(settings)
    app.state.github_importer.transport = httpx.MockTransport(fixture)
    with TestClient(app) as client:
        response = client.post('/api/github-imports', json={'repository_url': POCKETFLOW_URL})
        assert entered.wait(2)
        try:
            job = client.get(f"/api/github-imports/{response.json()['id']}").json()
            assert job['stage'] == 'scanning'
            assert job['progress'] == 75
        finally:
            release.set()
        assert wait_for_job(client, response.json()['id'])['status'] == 'succeeded'


def test_total_remote_deadline_cancels_network_before_any_snapshot_write(settings):
    class SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(.2)
            return httpx.Response(200, request=request, json={"default_branch": "main", "private": False})

    app = create_app(settings)
    app.state.github_importer.transport = SlowTransport()
    app.state.github_importer.network_deadline = .03
    with TestClient(app) as client:
        job = start(client)
        assert job['status'] == 'failed' and job['error_code'] == 'github_timeout'
        time.sleep(.25)
        assert client.get('/api/projects').json()['total'] == 0
        assert list((settings.data_dir / 'snapshots').iterdir()) == []
