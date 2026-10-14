"""Contract tests use actual Git blob hashes and never contact GitHub."""
import base64
import hashlib
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.online import SESSION_TTL, MAX_FILE

COMMIT = "a" * 40
FILES = {
    "README.md": b"# Demo\n\nReads input and returns formatted output.\n",
    "main.py": b"from helpers import clean\nif __name__ == '__main__':\n    print(clean('hello'))\n",
    "helpers.py": b"def clean(value):\n    return value.strip()\n",
    "src/independent.py": b"def isolated():\n    return True\n",
}


def blob_sha(raw):
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


@pytest.fixture
def online(settings):
    requests = []
    state = {"commit": COMMIT, "truncated": False, "rate_limit": False, "corrupt": False, "private": False}
    def handler(request):
        requests.append(request)
        path = request.url.path
        if state["rate_limit"]:
            return httpx.Response(403, headers={"x-ratelimit-remaining": "0"})
        if path == "/repos/example/demo":
            return httpx.Response(200, json={"private": state["private"], "default_branch": "main"})
        if path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": state["commit"]})
        if "/git/trees/" in path:
            entries = [{"path": name, "type": "blob", "mode": "100644", "size": len(raw), "sha": blob_sha(raw)} for name, raw in FILES.items()]
            entries += [{"path": name, "type": "blob", "mode": mode, "size": size, "sha": "b" * 40}
                        for name, mode, size in [(".env", "100644", 9), ("evil.py", "120000", 4), ("../../bad.py", "100644", 4), ("huge.py", "100644", MAX_FILE + 1), ("asset.png", "100644", 4)]]
            return httpx.Response(200, json={"truncated": state["truncated"], "tree": entries})
        if "/git/blobs/" in path:
            sha = path.rsplit("/", 1)[-1]
            raw = next(value for value in FILES.values() if blob_sha(value) == sha)
            return httpx.Response(200, json={"sha": sha, "encoding": "base64", "content": base64.b64encode(b"tampered" if state["corrupt"] else raw).decode()})
        raise AssertionError(f"Unexpected network request: {request.url}")
    app = create_app(settings)
    app.state.online_explorer.transport = httpx.MockTransport(handler)
    with TestClient(app) as client:
        yield client, app.state.online_explorer, requests, state


def open_project(client):
    response = client.post("/api/online", json={"repository_url": "https://github.com/example/demo"})
    assert response.status_code == 201, response.text
    return response.json()


def test_directory_first_lazy_text_and_no_snapshot_writes(online, settings):
    client, _, requests, _ = online
    opened = open_project(client)
    assert opened["loaded_count"] == 0
    assert {item["path"] for item in opened["files"]} == set(FILES)
    assert opened["excluded_count"] == 5
    assert not any("/blobs/" in str(request.url) for request in requests)
    session = opened["id"]
    read = client.post(f"/api/online/{session}/read", json={"paths": ["main.py"]})
    assert read.status_code == 200
    assert read.json()["loaded_count"] == 1
    assert read.json()["architecture"]["coverage"]["inspected_source_files"] == 1
    assert not any(link["kind"] == "imports" for link in read.json()["architecture"]["connections"])
    count = len(requests)
    read_again = client.post(f"/api/online/{session}/read", json={"paths": ["main.py"]})
    assert read_again.status_code == 200 and len(requests) == count
    completed = client.post(f"/api/online/{session}/read", json={"paths": []}).json()
    assert completed["loaded_count"] == len(FILES)
    edge = next(link for link in completed["architecture"]["connections"] if link["kind"] == "imports")
    assert (edge["from_id"], edge["to_id"]) == ("file:main.py", "file:helpers.py")
    assert edge["evidence"][0]["line_start"] == 1
    source = client.get(f"/api/online/{session}/source", params={"path": "helpers.py", "start": 2})
    assert source.status_code == 200 and source.json()["content"] == "    return value.strip()"
    assert client.get("/api/projects").json()["total"] == 0
    assert list((settings.data_dir / "snapshots").iterdir()) == []
    assert all(request.url.host == "api.github.com" for request in requests)


def test_same_commit_reuse_new_commit_isolation_and_expiry(online):
    client, explorer, _, state = online
    first = open_project(client)
    assert open_project(client)["id"] == first["id"]
    state["commit"] = "c" * 40
    second = open_project(client)
    assert second["id"] != first["id"]
    explorer.sessions[next(key for key in explorer.sessions if str(key) == first["id"])].touched -= SESSION_TTL + 1
    assert client.get(f"/api/online/{first['id']}").status_code == 410
    assert client.get(f"/api/online/{uuid4()}").status_code == 410


def test_truncated_tree_rate_limits_private_repos_and_blob_integrity(online):
    client, _, _, state = online
    state["truncated"] = True
    response = client.post("/api/online", json={"repository_url": "https://github.com/example/demo"})
    assert response.status_code == 413 and response.json()["detail"]["code"] == "github_tree_incomplete"
    state["truncated"] = False
    state["private"] = True
    assert client.post("/api/online", json={"repository_url": "https://github.com/example/demo"}).status_code == 404
    state["private"] = False
    opened = open_project(client)
    state["corrupt"] = True
    assert client.post(f"/api/online/{opened['id']}/read", json={"paths": ["main.py"]}).status_code == 422
    assert client.get(f"/api/online/{opened['id']}").json()["loaded_count"] == 0
    state["corrupt"] = False
    state["rate_limit"] = True
    assert client.post(f"/api/online/{opened['id']}/read", json={"paths": ["main.py"]}).status_code == 429
    state["rate_limit"] = False
    assert client.post(f"/api/online/{opened['id']}/read", json={"paths": ["main.py"]}).status_code == 200


def test_requests_are_bounded_and_paths_are_allowlisted(online):
    client, _, requests, _ = online
    session = open_project(client)["id"]
    count = len(requests)
    assert client.post(f"/api/online/{session}/read", json={"paths": ["../secret.py"]}).status_code == 404
    assert client.get(f"/api/online/{session}/source", params={"path": ".env"}).status_code == 404
    assert client.post(f"/api/online/{session}/read", json={"paths": ["main.py"] * 13}).status_code == 422
    assert client.post("/api/online", json={"repository_url": "https://example.com/demo"}).status_code == 422
    assert client.post("/api/online", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/online", content="x" * 17000, headers={"Content-Type": "application/json"}).status_code == 413
    assert client.get(f"/api/online/{session}/source", params={"path": "main.py", "start": 0}).status_code == 422
    assert len(requests) == count
