import base64
import hashlib
import shutil
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import importer
from app.db import MIGRATIONS, connect, migrate
from app.import_policy import MAX_BODY, MAX_FILE
from app.main import create_app
from test_api import live_server


def upload(files):
    return {"source": "upload", "name": "上传验证", "files": [
        {"path": path, "content_base64": base64.b64encode(raw).decode()} for path, raw in files.items()
    ]}


def test_uploaded_snapshot_is_real_and_persists_across_process_restart(settings):
    with live_server(settings) as client:
        response = client.post('/api/projects/import', json=upload({
            'main.py': b'def start():\n    return 42\n', 'utils/math.py': b'def add(a, b):\n    return a + b\n',
            '.env': b'FAKE_TEST_SECRET', 'node_modules/a.js': b'ignored', 'image.png': b'not text',
        }))
        assert response.status_code == 201, response.text
        result = response.json()
        assert result['skipped_count'] == 3
        detail = result['detail']
        snapshot = detail['snapshots'][0]
        assert [f['path'] for f in snapshot['files']] == ['main.py', 'utils/math.py']
        assert {c['path'] for c in snapshot['folder_cards']} == {'.', 'utils'}
        for card in snapshot['folder_cards']:
            for ref in card['evidence_refs']:
                raw = (settings.data_dir / snapshot['storage_path'] / ref['file_path']).read_text()
                assert '\n'.join(raw.splitlines()[ref['line_start']-1:ref['line_end']]) == ref['excerpt']
        project_id = detail['project']['id']
    with live_server(settings) as client:
        assert client.get(f'/api/projects/{project_id}').json() == detail
        response = client.get(f"/api/snapshots/{snapshot['id']}/source", params={'path': 'main.py'})
        assert response.status_code == 200
        assert response.json()['content'] == 'def start():\n    return 42'
        assert response.json()['sha256'] == hashlib.sha256(b'def start():\n    return 42\n').hexdigest()


def test_builtin_matches_commit_and_evidence(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post('/api/projects/import', json={'source': 'builtin'})
        assert response.status_code == 201, response.text
        snapshot = response.json()['detail']['snapshots'][0]
        assert snapshot['commit_sha'] == importer.git('rev-parse', 'HEAD').decode().strip()
        paths = {f['path'] for f in snapshot['files']}
        assert {'main.py', 'flow.py', 'nodes.py', 'utils/call_llm.py'} <= paths
        references = [r for c in snapshot['folder_cards'] for r in c['evidence_refs']]
        for path, symbol in [('main.py', '__main__ guard'), ('flow.py', 'create_tutorial_flow'), ('flow.py', 'operator >>'), ('nodes.py', 'FetchRepo'), ('utils/call_llm.py', 'call_llm')]:
            assert any(r['file_path'] == path and r['symbol'] == symbol for r in references)
        for ref in references:
            raw = importer.git('show', f"{snapshot['commit_sha']}:{ref['file_path']}").decode()
            assert ref['excerpt'] == '\n'.join(raw.splitlines()[ref['line_start']-1:ref['line_end']])


@pytest.mark.parametrize('path', ['../escape.py', '/etc/file.py', 'a/../../file.py', 'C:\\file.py', 'a//b.py', 'a/./b.py', 'nul\x00.py', '.git/../escape.py'])
def test_bad_paths_are_rejected_without_writes(settings, path):
    with TestClient(create_app(settings)) as client:
        response = client.post('/api/projects/import', json=upload({path: b'print(1)'}))
        assert response.status_code == 422
        assert response.json()['detail']['code'] == 'invalid_path'
        assert client.get('/api/projects').json()['total'] == 0
        assert list((settings.data_dir / 'snapshots').iterdir()) == []


@pytest.mark.parametrize('files,code', [({}, 'empty_directory'), ({'.env': b'fake'}, 'empty_directory'), ({'file.py': b'\xff\x00'}, 'empty_directory'), ({'a.py': b'x', 'a.py/b.py': b'x'}, 'path_conflict'), ({'a.py': b'x', 'A.py': b'x'}, 'duplicate_path')])
def test_empty_and_conflicting_inputs(settings, files, code):
    with TestClient(create_app(settings)) as client:
        response = client.post('/api/projects/import', json=upload(files))
        assert response.status_code == 422
        assert response.json()['detail']['code'] == code
        assert client.get('/api/projects').json()['total'] == 0


def test_file_total_count_and_request_limits(settings):
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/projects/import', json=upload({'a.py': b'x' * (MAX_FILE + 1)})).status_code == 413
        assert client.post('/api/projects/import', json=upload({f'{i}.py': b'x' * MAX_FILE for i in range(9)})).status_code == 413
        assert client.post('/api/projects/import', json=upload({f'{i}.py': b'x' for i in range(501)})).status_code == 422
        response = client.post('/api/projects/import', content=b'x' * (MAX_BODY + 1), headers={'Content-Type': 'application/json'})
        assert response.status_code == 413
        assert response.json()['detail']['code'] == 'request_too_large'
        assert client.get('/api/projects').json()['total'] == 0


def test_malformed_body_and_cross_origin_are_rejected(settings):
    with TestClient(create_app(settings)) as client:
        assert client.post('/api/projects/import', content='{}').status_code == 415
        assert client.post('/api/projects/import', json={'source': 'builtin'}, headers={'Origin': 'https://example.com'}).status_code == 403
        response = client.post('/api/projects/import', json={'source': 'upload', 'files': [{'path': 'main.py', 'content_base64': 'NOT_BASE64'}]})
        assert response.status_code == 422
        assert 'NOT_BASE64' not in response.text
        assert client.post('/api/projects/import', content='{', headers={'Content-Type': 'application/json'}).status_code == 422


def test_snapshot_changes_missing_and_source_traversal(settings):
    with TestClient(create_app(settings)) as client:
        snapshot = client.post('/api/projects/import', json=upload({'main.py': b'print(42)\n'})).json()['detail']['snapshots'][0]
        url = f"/api/snapshots/{snapshot['id']}/source"
        assert client.get(url, params={'path': '../repolens.sqlite3'}).status_code == 422
        assert client.get(url, params={'path': 'other.py'}).status_code == 404
        target = settings.data_dir / snapshot['storage_path'] / 'main.py'
        target.write_text('changed')
        assert client.get(url, params={'path': 'main.py'}).json()['detail']['code'] == 'snapshot_changed'
        target.unlink()
        assert client.get(url, params={'path': 'main.py'}).json()['detail']['code'] == 'snapshot_missing'
        target.symlink_to(settings.database)
        assert client.get(url, params={'path': 'main.py'}).status_code == 409


def test_database_failure_cleans_snapshot(settings, monkeypatch):
    def broken(*args):
        raise RuntimeError('simulated storage failure')
    monkeypatch.setattr(importer, 'create_project', broken)
    with TestClient(create_app(settings)) as client:
        with pytest.raises(RuntimeError, match='simulated'):
            client.post('/api/projects/import', json=upload({'main.py': b'print(1)'}))
    assert list((settings.data_dir / 'snapshots').iterdir()) == []


def test_version_one_project_survives_upgrade(settings, data_dir):
    old = data_dir / 'v1'
    old.mkdir()
    shutil.copy(MIGRATIONS / '001_repository_metadata.sql', old)
    assert migrate(settings.database, old) == 1
    project_id = str(uuid4())
    with connect(settings.database) as db:
        db.execute('INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?)', (project_id, '旧项目', 'test_fixture', 'v1 fixture', '2026-09-21T00:00:00Z', '2026-09-21T00:00:00Z'))
    assert migrate(settings.database) == 5
    with TestClient(create_app(settings)) as client:
        assert client.get(f'/api/projects/{project_id}').json()['project']['name'] == '旧项目'
