import json
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.bounded_llm import ModelFailure, ModelSession
from app.config import ROOT, Settings
from app.db import connect
from app.main import create_app
from app.model_config import ModelConfig, DEFAULT_MODEL, BASE_URL
from app.pocketflow_adapter import COMMIT, worker_command
from test_runs import snapshot, wait_for

FAKE_KEY = 'sk-or-v1-FAKE_REAL_FLOW_TEST'


def prepare(settings, scenario='success', missing=False):
    app = create_app(Settings(settings.data_dir, real_enabled=True))
    app.state.runner.model_loader = lambda: ModelConfig('OPENROUTER', DEFAULT_MODEL, BASE_URL, '' if missing else FAKE_KEY)
    def fixture(input_dir, output_dir, language, topics):
        command = worker_command(input_dir, output_dir, language, topics)
        return [*command[:3], str(ROOT/'server/tests/pocketflow_fixture_worker.py'), scenario, *command[4:]]
    app.state.runner.real_command = fixture
    return app


def registered(client, settings):
    snap = snapshot(client)
    with connect(settings.database) as db:
        db.execute('UPDATE snapshots SET commit_sha=? WHERE id=?',(COMMIT,snap['id']))
    return {'snapshot_id':snap['id'],'mode':'pocketflow','scope':'utils','language':'zh','topics':3}


def test_missing_key_and_real_scope_rejected_before_start(settings):
    with TestClient(prepare(settings, missing=True)) as client:
        request = registered(client, settings)
        response = client.post('/api/runs',json=request)
        assert response.status_code == 409 and response.json()['detail']['code']=='model_config_missing'
        assert client.get('/api/runner').json()['real_ready'] is False
        for patch in [{'scope':'.'},{'language':'en'},{'topics':5},{'scenario':'failure'}]:
            assert client.post('/api/runs',json={**request,**patch}).status_code==422
        assert client.get('/api/runs',params={'snapshot_id':request['snapshot_id']}).json()['total']==0


def test_pinned_entry_end_to_end_with_mock_model_and_durable_usage(settings):
    app = prepare(settings)
    with TestClient(app) as client:
        request = registered(client, settings)
        response = client.post('/api/runs',json=request)
        assert response.status_code==201,response.text
        run_id=response.json()['id']
        run=wait_for(client,run_id,{'succeeded','failed'},timeout=15)
        assert run['status']=='succeeded', client.get(f'/api/runs/{run_id}/logs').text
        assert run['mode']=='pocketflow' and run['model_name']==DEFAULT_MODEL
        usage=json.loads(run['model_usage'])
        assert usage['call_count']==5 and usage['retry_performed'] is False
        refs=next(a for a in run['artifacts'] if a['path'].endswith('verified-claims.json'))
        data=client.get(f"/api/runs/{run_id}/artifacts/{refs['id']}").json()
        assert json.loads(data['content'])[0]['claim_type']=='inference'
        assert json.loads(data['content'])[0]['references'][0]['line_start']==1
        log=client.get(f'/api/runs/{run_id}/logs').text
        assert 'FolderResponsibilities' in log and FAKE_KEY not in log
        for path in (settings.data_dir/'runs'/run_id).rglob('*'):
            if path.is_file(): assert FAKE_KEY.encode() not in path.read_bytes()
        cached = client.post('/api/runs', json=request)
        assert cached.status_code == 200
        assert cached.headers['x-repolens-result-cache'] == 'hit'
        assert cached.json()['id'] == run_id
        app.state.runner.model_loader = lambda: ModelConfig('OPENROUTER', 'fixture/model-b', BASE_URL, FAKE_KEY)
        changed_model = client.post('/api/runs', json=request)
        assert changed_model.status_code == 201
        assert changed_model.json()['id'] != run_id
        assert changed_model.json()['result_cache_key'] != run['result_cache_key']
        assert wait_for(client, changed_model.json()['id'], {'succeeded', 'failed'}, timeout=15)['status'] == 'succeeded'
    with TestClient(prepare(settings)) as client:
        reopened=client.get(f'/api/runs/{run_id}').json()
        assert reopened==run


def test_real_worker_provider_failure_no_retry(settings):
    with TestClient(prepare(settings,'failure')) as client:
        run_id=client.post('/api/runs',json=registered(client,settings)).json()['id']
        run=wait_for(client,run_id,{'failed'})
        assert run['artifacts']==[]
        usage=json.loads(run['model_usage'])
        assert usage['call_count']==1 and usage['calls'][0]['http_status']==401
        log=client.get(f'/api/runs/{run_id}/logs').json()['content']
        assert 'model_http_401' in log and FAKE_KEY not in log


def test_real_worker_cancel_does_not_publish_output(settings):
    with TestClient(prepare(settings,'slow')) as client:
        run_id=client.post('/api/runs',json=registered(client,settings)).json()['id']
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if 'Identifying abstractions' in client.get(f'/api/runs/{run_id}/logs').text: break
            time.sleep(.05)
        else: pytest.fail('Real worker did not start')
        assert client.post(f'/api/runs/{run_id}/cancel').json()['status']=='cancelled'
        time.sleep(.3)
        run=client.get(f'/api/runs/{run_id}').json()
        assert run['status']=='cancelled' and run['artifacts']==[]


def test_worker_enforces_three_topics_without_second_call(settings):
    with TestClient(prepare(settings,'too_many')) as client:
        run_id=client.post('/api/runs',json=registered(client,settings)).json()['id']
        run=wait_for(client,run_id,{'failed'})
        assert json.loads(run['model_usage'])['call_count']==1
        assert 'abstraction_limit' in client.get(f'/api/runs/{run_id}/logs').text


def test_client_limits_and_truncation_do_not_retry(tmp_path):
    calls=[]
    def respond(request):
        calls.append(request)
        return httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'partial'}}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        session=ModelSession(ModelConfig('OPENROUTER',DEFAULT_MODEL,BASE_URL,FAKE_KEY),tmp_path,1,client)
        with pytest.raises(ModelFailure,match='model_input_limit'): session('x'*120001)
        with pytest.raises(ModelFailure,match='model_incomplete_output'): session('short')
        with pytest.raises(ModelFailure,match='model_call_limit'): session('second')
    assert len(calls)==1
