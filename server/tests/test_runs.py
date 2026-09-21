import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.claims import verify_claims
from app.db import connect
from app.main import create_app
from app.pocketflow_adapter import COMMIT, isolated_environment, pocketflow_command
from test_import import upload
from test_api import live_server


def snapshot(client):
    response = client.post('/api/projects/import', json=upload({'main.py': b'def main():\n    return 42\n', 'utils/helper.py': b'def helper():\n    pass\n'}))
    assert response.status_code == 201
    return response.json()['detail']['snapshots'][0]


def wait_for(client, run_id, states, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f'/api/runs/{run_id}').json()
        if run['status'] in states:
            return run
        time.sleep(0.04)
    raise AssertionError(f'Task did not reach {states}: {run}')


def test_success_has_durable_parameters_stages_logs_and_safe_artifacts(settings):
    with TestClient(create_app(settings)) as client:
        snap = snapshot(client)
        created = client.post('/api/runs', json={'snapshot_id': snap['id'], 'scope': 'utils', 'language': 'en', 'topics': 5})
        assert created.status_code == 201, created.text
        run_id = created.json()['id']
        run = wait_for(client, run_id, {'succeeded', 'failed'})
        assert run['status'] == 'succeeded', run
        assert (run['scope'], run['language'], run['topics'], run['mode']) == ('utils', 'en', 5, 'stub')
        assert run['exit_code'] == 0 and run['started_at'] and run['ended_at']
        log = client.get(f'/api/runs/{run_id}/logs').json()
        assert log['finished'] and 'REPOLENS_STAGE:CombineTutorial' in log['content']
        assert '真实模型' in log['content']
        assert client.get(f'/api/runs/{run_id}/logs', params={'offset': log['next_offset']}).json()['content'] == ''
        index = next(a for a in run['artifacts'] if a['path'].endswith('/index.md'))
        response = client.get(f"/api/runs/{run_id}/artifacts/{index['id']}")
        content = response.json()['content']
        assert '读取 1 个' in content and 'en / 5' in content
        assert hashlib.sha256(content.encode()).hexdigest() == index['sha256']
        response = client.get(f"/api/runs/{run_id}/artifacts/{index['id']}?download=true")
        assert response.headers['content-disposition'].startswith('attachment;')
        assert response.headers['x-content-type-options'] == 'nosniff'
        refs = next(a for a in run['artifacts'] if a['path'].endswith('/verified-claims.json'))
        claims = json.loads(client.get(f"/api/runs/{run_id}/artifacts/{refs['id']}").json()['content'])
        assert claims[0]['claim_type'] == 'unverified'
        assert client.post(f'/api/runs/{run_id}/cancel').json()['status'] == 'succeeded'
    with TestClient(create_app(settings)) as client:
        assert client.get(f'/api/runs/{run_id}').json() == run
        assert client.get('/api/runs', params={'snapshot_id': snap['id']}).json()['total'] == 1
        assert client.get(f"/api/runs/{run_id}/artifacts/{index['id']}").status_code == 200


def test_failure_cancel_and_busy_do_not_publish_success(settings):
    with TestClient(create_app(settings)) as client:
        snap = snapshot(client)
        failed = client.post('/api/runs', json={'snapshot_id': snap['id'], 'scenario': 'failure'}).json()['id']
        run = wait_for(client, failed, {'failed'})
        assert run['exit_code'] == 23 and run['artifacts'] == []
        assert client.get(f'/api/runs/{failed}/artifacts/{uuid4()}').status_code == 409
        slow = client.post('/api/runs', json={'snapshot_id': snap['id'], 'scenario': 'slow'}).json()['id']
        wait_for(client, slow, {'running'})
        assert client.post('/api/runs', json={'snapshot_id': snap['id']}).status_code == 409
        assert client.post(f'/api/runs/{slow}/cancel').json()['status'] == 'cancelled'
        time.sleep(0.5)
        run = client.get(f'/api/runs/{slow}').json()
        assert run['status'] == 'cancelled' and run['artifacts'] == []
        assert client.post(f'/api/runs/{slow}/cancel').json()['status'] == 'cancelled'


def test_timeout_and_changed_snapshot_fail(settings):
    app = create_app(settings)
    app.state.runner.timeout = 0.15
    with TestClient(app) as client:
        snap = snapshot(client)
        run_id = client.post('/api/runs', json={'snapshot_id': snap['id'], 'scenario': 'slow'}).json()['id']
        assert wait_for(client, run_id, {'failed'})['artifacts'] == []
        (settings.data_dir / snap['storage_path'] / 'main.py').write_text('changed')
        run_id = client.post('/api/runs', json={'snapshot_id': snap['id']}).json()['id']
        assert wait_for(client, run_id, {'failed'})['artifacts'] == []


def test_invalid_snapshot_scope_and_request_limits(settings):
    with TestClient(create_app(settings)) as client:
        snap = snapshot(client)
        assert client.post('/api/runs', json={'snapshot_id': str(uuid4())}).status_code == 404
        for body in [{'scope': '../escape'}, {'scope': 'missing'}, {'topics': 99}, {'language': 'shell'}, {'command': 'echo hi'}, {'mode': 'unknown'}]:
            assert client.post('/api/runs', json={'snapshot_id': snap['id'], **body}).status_code == 422
        assert client.post('/api/runs', json={'snapshot_id': snap['id']}, headers={'Origin': 'https://example.com'}).status_code == 403
        assert client.post('/api/runs', content='x'*17000, headers={'Content-Type':'application/json'}).status_code == 413
        assert client.get('/api/runner').json()['real_enabled'] is False


def test_valid_and_invalid_prompt_references_do_not_overwrite_facts(settings):
    with TestClient(create_app(settings)) as client:
        snap = snapshot(client)
        good = {'folder_path': 'utils', 'description': '辅助函数推断', 'references': [{'file_path':'utils/helper.py', 'line_start':1, 'line_end':2, 'quote':'def helper():\n    pass'}]}
        assert verify_claims(settings, snap['id'], {'claims':[good]})[0]['claim_type'] == 'inference'
        good['references'][0]['quote'] = 'fabricated'
        assert verify_claims(settings, snap['id'], {'claims':[good]})[0]['claim_type'] == 'unverified'
        good['references'][0]['file_path'] = '../outside'
        assert verify_claims(settings, snap['id'], {'claims':[good]})[0]['claim_type'] == 'unverified'
        good['folder_path'] = ['malformed']
        assert verify_claims(settings, snap['id'], {'claims':[good]})[0]['claim_type'] == 'unverified'
        with connect(settings.database) as db:
            assert db.execute('SELECT count(*) FROM evidence_refs WHERE snapshot_id=?', (snap['id'],)).fetchone()[0] == 2


def test_fixed_adapter_and_sanitized_environment(settings, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'FAKE_TEST_KEY')
    monkeypatch.setenv('HTTP_PROXY', 'http://example.com')
    env = isolated_environment(settings.data_dir)
    assert 'GEMINI_API_KEY' not in env and 'HTTP_PROXY' not in env and 'PYTHONPATH' not in env
    command = pocketflow_command(settings.data_dir/'input', settings.data_dir/'output', 'zh', 3)
    assert command[3].endswith('/upstream/pocketflow-codebase-knowledge/main.py')
    assert command[command.index('--language')+1] == 'Chinese'
    assert '--repo' not in command and '--token' not in command
    assert COMMIT == '05b24cbbb0fe409c5e23c9791f0342f07524ffdc'


def test_graceful_restart_interrupts_active_task(settings):
    with TestClient(create_app(settings)) as client:
        snap = snapshot(client)
        run_id = client.post('/api/runs', json={'snapshot_id':snap['id'], 'scenario':'slow'}).json()['id']
        wait_for(client, run_id, {'running'})
    with TestClient(create_app(settings)) as client:
        assert client.get(f'/api/runs/{run_id}').json()['status'] == 'interrupted'


def test_artifact_tampering_and_cross_run_lookup_are_rejected(settings):
    with TestClient(create_app(settings)) as client:
        snap = snapshot(client)
        run_id = client.post('/api/runs', json={'snapshot_id':snap['id']}).json()['id']
        run = wait_for(client, run_id, {'succeeded'})
        artifact = run['artifacts'][0]
        path = settings.data_dir/'runs'/run_id/'output'/artifact['path']
        path.write_text('changed')
        assert client.get(f"/api/runs/{run_id}/artifacts/{artifact['id']}").status_code == 409
        path.unlink()
        assert client.get(f"/api/runs/{run_id}/artifacts/{artifact['id']}").status_code == 409
        assert client.get(f'/api/runs/{run_id}/artifacts/{uuid4()}').status_code == 404


def test_hard_backend_exit_stops_process_group_and_recovers(settings):
    # live_server owns the first API process; SIGKILL emulates a crash, not graceful lifespan cleanup.
    with live_server(settings) as client:
        snap = snapshot(client)
        run_id = client.post('/api/runs', json={'snapshot_id':snap['id'], 'scenario':'slow'}).json()['id']
        wait_for(client, run_id, {'running'})
        deadline = time.monotonic()+5
        supervisor = None
        while time.monotonic()<deadline:
            listing=subprocess.check_output(['ps','-eo','pid,ppid,command'],text=True)
            for line in listing.splitlines():
                if 'run_supervisor.py' in line and run_id in line:
                    pid, ppid, _ = line.strip().split(None,2)
                    supervisor, owner = int(pid), int(ppid)
            if supervisor: break
            time.sleep(0.05)
        assert supervisor
        os.kill(owner, signal.SIGKILL)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try: os.killpg(supervisor,0)
            except ProcessLookupError: break
            time.sleep(0.05)
        else: raise AssertionError('Orphan job group survived backend crash')
    with live_server(settings) as client:
        run=client.get(f'/api/runs/{run_id}').json()
        assert run['status']=='interrupted' and run['artifacts']==[]
