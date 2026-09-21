"""Public delivery boundaries: ownership, directory backups and restored APIs."""
import json
import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.main import create_app
from test_import import upload
from test_runs import wait_for


def cli(settings, *args):
    return subprocess.run([sys.executable, '-m', 'app.backup', *map(str, args)],
                          cwd=ROOT / 'server', env={**os.environ, 'REPOLENS_DATA_DIR': str(settings.data_dir)},
                          capture_output=True, text=True, timeout=30)


def test_data_ownership_prevents_second_backend_and_releases_after_close(settings):
    from app.data_lease import DataLease
    with TestClient(create_app(settings)):
        with pytest.raises(RuntimeError, match='数据目录'):
            with DataLease(settings.data_dir):
                pass
    with DataLease(settings.data_dir):
        with pytest.raises(RuntimeError, match='数据目录'):
            with TestClient(create_app(settings)):
                pass
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/health').status_code == 200


def test_backup_restore_roundtrip_reads_uploaded_source_and_completed_artifact(settings, tmp_path):
    backup, restored = tmp_path / 'backup', tmp_path / 'restored'
    with TestClient(create_app(settings)) as client:
        detail = client.post('/api/projects/import', json=upload({'main.py': b'print(42)\n'})).json()['detail']
        snap = detail['snapshots'][0]
        run_id = client.post('/api/runs', json={'snapshot_id': snap['id']}).json()['id']
        run = wait_for(client, run_id, {'succeeded'})
        artifact = run['artifacts'][0]
        original = client.get(f"/api/runs/{run_id}/artifacts/{artifact['id']}").json()
        assert cli(settings, 'create', backup).returncode != 0
        assert not backup.exists()
    (settings.data_dir / 'orphan-secret.env').write_text('DO_NOT_COPY')
    (settings.data_dir / 'snapshots' / 'orphan').mkdir()
    result = cli(settings, 'create', backup)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((backup / 'manifest.json').read_text())
    assert manifest['format_version'] == 1 and manifest['schema_version'] == 6
    assert not (backup / 'orphan-secret.env').exists()
    assert not (backup / 'snapshots' / 'orphan').exists()
    result = cli(settings, 'restore', backup, restored)
    assert result.returncode == 0, result.stderr
    with TestClient(create_app(Settings(restored))) as client:
        assert client.get(f"/api/projects/{detail['project']['id']}").json() == detail
        assert client.get(f"/api/snapshots/{snap['id']}/source", params={'path': 'main.py'}).json()['content'] == 'print(42)'
        assert client.get(f"/api/runs/{run_id}/artifacts/{artifact['id']}").json() == original


def test_opt_in_built_web_keeps_api_404_and_private_files_private(settings, monkeypatch):
    monkeypatch.setenv('REPOLENS_SERVE_WEB', '1')
    with TestClient(create_app(settings)) as client:
        page = client.get('/')
        assert page.status_code == 200 and '<html' in page.text
        assert client.get('/api/not-found').status_code == 404
        assert client.get('/api/not-found').headers['content-type'].startswith('application/json')
        for path in ('/server/.env', '/server/app/main.py', '/.env', '/src/App.tsx', '/repolens.sqlite3'):
            assert client.get(path).status_code == 404
    monkeypatch.delenv('REPOLENS_SERVE_WEB')
    with TestClient(create_app(settings)) as client:
        assert client.get('/').status_code == 404


@pytest.fixture
def saved_backup(settings, tmp_path):
    with TestClient(create_app(settings)) as client:
        detail = client.post('/api/projects/import', json=upload({'main.py': b'print(42)\n'})).json()['detail']
    backup = tmp_path / 'backup'
    result = cli(settings, 'create', backup)
    assert result.returncode == 0, result.stderr
    return backup, detail


@pytest.mark.parametrize('damage', ['hash', 'traversal', 'symlink', 'hardlink', 'fifo', 'missing-reference', 'case-collision', 'unregistered', 'migration-checksum', 'schema-trigger', 'foreign-key', 'manifest-limit'])
def test_restore_rejects_unsafe_backup_without_publishing(settings, saved_backup, tmp_path, damage):
    backup, detail = saved_backup
    manifest_path = backup / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    source_name = next(name for name in manifest['files'] if name.startswith('snapshots/'))
    source = backup / source_name
    if damage == 'hash':
        source.write_text('tampered')
    elif damage == 'traversal':
        manifest['files']['../outside'] = manifest['files'].pop(source_name)
    elif damage in ('symlink', 'hardlink', 'fifo'):
        outside = tmp_path / 'outside'
        outside.write_bytes(source.read_bytes())
        source.unlink()
        if damage == 'symlink': source.symlink_to(outside)
        elif damage == 'hardlink': os.link(outside, source)
        else: os.mkfifo(source)
    elif damage == 'missing-reference':
        source.unlink()
        del manifest['files'][source_name]
    elif damage == 'case-collision':
        manifest['files'][source_name.replace('main.py', 'MAIN.py')] = manifest['files'][source_name]
    elif damage == 'unregistered':
        (backup / 'extra.txt').write_text('not registered')
    elif damage in ('migration-checksum', 'schema-trigger', 'foreign-key'):
        with sqlite3.connect(backup / 'repolens.sqlite3') as db:
            if damage == 'migration-checksum':
                db.execute("UPDATE schema_migrations SET checksum='wrong' WHERE version=1")
            elif damage == 'schema-trigger':
                db.execute("CREATE TRIGGER evil AFTER INSERT ON projects BEGIN DELETE FROM projects; END")
            else:
                db.execute('DELETE FROM projects')
        raw = (backup / 'repolens.sqlite3').read_bytes()
        manifest['files']['repolens.sqlite3'] = {'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    elif damage == 'manifest-limit':
        manifest['files'][source_name]['size_bytes'] = 10**20
    manifest_path.write_text(json.dumps(manifest))
    restored = tmp_path / 'restored'
    result = cli(settings, 'restore', backup, restored)
    assert result.returncode != 0, result.stdout
    assert not restored.exists()
    assert not list(tmp_path.glob('.restored.staging-*'))


def test_existing_empty_destinations_are_never_overwritten(settings, saved_backup, tmp_path):
    backup, _ = saved_backup
    destination = tmp_path / 'existing'
    destination.mkdir()
    for args in [('create', destination), ('restore', backup, destination)]:
        result = cli(settings, *args)
        assert result.returncode != 0 and 'exists' in result.stderr
        assert destination.is_dir() and list(destination.iterdir()) == []


def test_backup_includes_committed_wal_and_respects_legacy_runner_lease(settings, tmp_path):
    from app.data_lease import DataLease
    with TestClient(create_app(settings)) as client:
        detail = client.post('/api/projects/import', json=upload({'main.py': b'print(42)\n'})).json()['detail']
    backup = tmp_path / 'backup'
    with DataLease(settings.data_dir / 'runs', '.runner.lock'):
        assert cli(settings, 'create', backup).returncode != 0
    with sqlite3.connect(settings.database) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA wal_autocheckpoint=0')
        db.execute("UPDATE projects SET name='Committed WAL project'")
        db.commit()
        assert settings.database.with_name('repolens.sqlite3-wal').stat().st_size > 0
        result = cli(settings, 'create', backup)
        assert result.returncode == 0, result.stderr
    restored = tmp_path / 'restored'
    assert cli(settings, 'restore', backup, restored).returncode == 0
    with TestClient(create_app(Settings(restored))) as client:
        assert client.get(f"/api/projects/{detail['project']['id']}").json()['project']['name'] == 'Committed WAL project'


def test_backup_rejects_registered_links_and_releases_lease_on_failure(settings, tmp_path):
    from app.data_lease import DataLease
    with TestClient(create_app(settings)) as client:
        snap = client.post('/api/projects/import', json=upload({'main.py': b'print(42)\n'})).json()['detail']['snapshots'][0]
    source = settings.data_dir / snap['storage_path'] / 'main.py'
    source.unlink()
    source.symlink_to(settings.database)
    destination = tmp_path / 'backup'
    assert cli(settings, 'create', destination).returncode != 0
    assert not destination.exists() and not list(tmp_path.glob('.backup.staging-*'))
    with DataLease(settings.data_dir):
        pass


def test_backup_does_not_copy_keys_or_transient_run_material(settings, tmp_path):
    with TestClient(create_app(settings)) as client:
        snap = client.post('/api/projects/import', json=upload({'main.py': b'print(42)\n'})).json()['detail']['snapshots'][0]
        run = wait_for(client, client.post('/api/runs', json={'snapshot_id': snap['id']}).json()['id'], {'succeeded'})
    directory = settings.data_dir / 'runs' / run['id']
    (directory / 'output' / '.env').write_text('FAKE_SECRET')
    (directory / 'output' / '.runner.lock').write_text('transient')
    (directory / 'temporary').mkdir()
    (directory / 'temporary' / 'key').write_text('FAKE_SECRET')
    backup = tmp_path / 'backup'
    result = cli(settings, 'create', backup)
    assert result.returncode == 0, result.stderr
    paths = json.loads((backup / 'manifest.json').read_text())['files']
    assert not any(name.endswith(('.env', '.runner.lock', '/key')) for name in paths)


def test_restore_rejects_duplicate_manifest_keys(settings, saved_backup, tmp_path):
    backup, _ = saved_backup
    path = backup / 'manifest.json'
    path.write_text(path.read_text().replace('"format_version": 1', '"format_version": 999, "format_version": 1'))
    assert cli(settings, 'restore', backup, tmp_path / 'restored').returncode != 0


def test_backup_rejects_migration_tamper_without_modifying_source(settings, saved_backup, tmp_path):
    with sqlite3.connect(settings.database) as db:
        db.execute("UPDATE schema_migrations SET checksum='tampered' WHERE version=1")
    before = settings.database.read_bytes()
    assert cli(settings, 'create', tmp_path / 'invalid').returncode != 0
    assert settings.database.read_bytes() == before
