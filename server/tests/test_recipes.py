import json
from fastapi.testclient import TestClient

from app.main import create_app
from app.pocketflow_adapter import COMMIT
from test_runs import snapshot, wait_for
from test_real_runs import prepare, registered


def test_public_registry_describes_only_verified_action(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get('/api/recipes')
        assert response.status_code == 200
        items = response.json()['items']
        assert [r['id'] for r in items] == ['pocketflow-tutorial']
        recipe = items[0]
        assert recipe['version'] == '1'
        assert recipe['entry']['commit'] == COMMIT
        assert recipe['entry']['path'] == 'server/pocketflow/worker.py'
        assert recipe['parameters']['properties']['topics']['maximum'] == 3
        assert recipe['timeout_seconds'] == 900
        assert recipe['stop']['signals'] == ['SIGTERM', 'SIGKILL']
        assert recipe['artifacts']['required'] == ['project/index.md']
        assert recipe['isolation']['kind'] == 'macos-seatbelt'
        assert recipe['ready'] is False
        assert '/Users/' not in json.dumps(recipe)


def test_recipe_requests_reject_unsafe_or_unknown_fields_before_run(settings):
    with TestClient(create_app(settings)) as client:
        snap = snapshot(client)
        body = {'snapshot_id': snap['id'], 'recipe_id': 'uploaded-main', 'parameters': {}}
        assert client.post('/api/runs', json=body).status_code == 404
        body['recipe_id'] = 'pocketflow-tutorial'
        for params in [{'command': 'sh'}, {'topics': '3'}, {'topics': True}, {'topics': 4}, {'language': 'en'}, {'scope': '../outside'}]:
            response = client.post('/api/runs', json={**body, 'parameters': params})
            assert response.status_code == 422, response.text
        assert client.post('/api/runs', json={**body, 'command': 'sh'}).status_code == 422
        assert client.get('/api/runs', params={'snapshot_id': snap['id']}).json()['total'] == 0


def test_registered_worker_persists_identity_and_uses_sandbox(settings):
    app = prepare(settings)
    with TestClient(app) as client:
        legacy = registered(client, settings)
        body = {'recipe_id': 'pocketflow-tutorial', 'snapshot_id': legacy['snapshot_id'], 'parameters': {'topics': 3}}
        response = client.post('/api/runs', json=body)
        assert response.status_code == 201, response.text
        run = wait_for(client, response.json()['id'], {'succeeded', 'failed'}, timeout=15)
        assert run['status'] == 'succeeded', (run, client.get(f"/api/runs/{run['id']}/logs").text)
        assert run['recipe_id'] == 'pocketflow-tutorial'
        assert run['recipe_version'] == '1'
        assert run['isolation_kind'] == 'macos-seatbelt'
        assert json.loads(run['parameters_json']) == {'topics': 3, 'scope': 'utils', 'language': 'zh'}
        assert '(deny default)' in (settings.data_dir / 'runs' / run['id'] / 'sandbox.sb').read_text()
        assert client.post('/api/runs', json=body).status_code == 200
        from dataclasses import replace
        app.state.runner.recipes['pocketflow-tutorial'] = replace(app.state.runner.recipes['pocketflow-tutorial'], version='2')
        newer = client.post('/api/runs', json=body)
        assert newer.status_code == 201
        assert newer.json()['result_cache_key'] != run['result_cache_key']
        assert newer.json()['recipe_version'] == '2'
        assert wait_for(client, newer.json()['id'], {'succeeded', 'failed'}, timeout=15)['status'] == 'succeeded'


def test_real_legacy_api_cannot_bypass_missing_sandbox(settings, monkeypatch):
    from app import runner
    monkeypatch.setattr(runner, 'capability', lambda: {'available': False, 'kind': 'macos-seatbelt'})
    with TestClient(prepare(settings)) as client:
        response = client.post('/api/runs', json=registered(client, settings))
        assert response.status_code == 409
        assert response.json()['detail']['code'] == 'isolation_unavailable'


def test_uploaded_source_cannot_supply_registered_entry(settings):
    with TestClient(prepare(settings)) as client:
        snap = snapshot(client)
        response = client.post('/api/runs', json={'recipe_id': 'pocketflow-tutorial', 'snapshot_id': snap['id'], 'parameters': {}})
        assert response.status_code == 422
        assert response.json()['detail']['code'] == 'recipe_input_unsupported'


def lifecycle_app(settings, scenario, timeout=10):
    from dataclasses import replace
    from app.config import ROOT
    from app.pocketflow_adapter import PYTHON
    app = prepare(settings)
    app.state.runner.real_command = lambda *args: [str(PYTHON), '-B', '-u', str(ROOT / 'server/tests/action_fixture_worker.py'), scenario]
    app.state.runner.recipes['pocketflow-tutorial'] = replace(app.state.runner.recipes['pocketflow-tutorial'], timeout_seconds=timeout)
    return app


def test_recipe_nonzero_exit_and_unsafe_artifact(settings):
    for scenario, message in [('nonzero', 'recipe_exit_nonzero'), ('artifact_link', 'artifact_policy_violation')]:
        with TestClient(lifecycle_app(settings, scenario)) as client:
            response = client.post('/api/runs', json=registered(client, settings))
            run = wait_for(client, response.json()['id'], {'failed'})
            assert message in run['error']
            assert run['exit_code'] == (37 if scenario == 'nonzero' else 0)
            assert run['artifacts'] == []


def test_cancel_and_timeout_kill_stubborn_child(settings):
    import os
    import time
    import pytest
    for scenario in ['child', 'timeout']:
        app = lifecycle_app(settings, scenario, timeout=1.0 if scenario == 'timeout' else 10)
        with TestClient(app) as client:
            response = client.post('/api/runs', json=registered(client, settings))
            run_id = response.json()['id']
            pidfile = settings.data_dir / 'runs' / run_id / 'model-data/child.json'
            deadline = time.monotonic() + 5
            while not pidfile.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            assert pidfile.exists(), client.get(f'/api/runs/{run_id}/logs').text
            pid = json.loads(pidfile.read_text())['pid']
            if scenario == 'child':
                run = client.post(f'/api/runs/{run_id}/cancel').json()
                assert run['status'] == 'cancelled'
            else:
                run = wait_for(client, run_id, {'failed'})
                assert 'recipe_timeout' in run['error']
            assert run['exit_code'] is not None
            assert run['artifacts'] == []
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(.02)
            else:
                pytest.fail('Child survived stop/timeout')


def test_output_parent_link_never_overwrites_input(settings):
    from app.runner import Runner
    from types import SimpleNamespace
    import pytest
    directory = settings.data_dir / 'runs/fixture'
    input_dir = directory / 'input'
    input_dir.mkdir(parents=True)
    (input_dir / 'index.md').write_text('input')
    (input_dir / 'folder-claims.json').write_text('{"claims": []}')
    (directory / 'output').mkdir()
    (directory / 'output/project').symlink_to(input_dir, target_is_directory=True)
    runner = Runner(settings)
    # Database is needed only if the collector wrongly reads claims before validating links.
    from app.db import migrate
    migrate(settings.database)
    with pytest.raises(ValueError):
        runner.collect_artifacts(SimpleNamespace(id='fixture',snapshot_id='unused'),directory)
    assert not (input_dir / 'verified-claims.json').exists()


def test_recipe_only_grants_pinned_upstream_files():
    from app.recipes import REGISTRY
    from app.pocketflow_adapter import UPSTREAM
    paths = REGISTRY['pocketflow-tutorial'].read_paths()
    assert UPSTREAM not in paths
    assert UPSTREAM / 'main.py' in paths
    assert UPSTREAM / '.env' not in paths


def test_second_code_registered_recipe_uses_its_own_parameters_and_entry(settings):
    from dataclasses import replace
    from app.recipes import REGISTRY
    from app.config import ROOT
    from app.pocketflow_adapter import PYTHON
    from pydantic import BaseModel, ConfigDict
    class FixtureParameters(BaseModel):
        model_config = ConfigDict(extra='forbid', strict=True)
        scope: str = 'utils'
        message: str = 'only runner evidence'
    app = create_app(settings)
    recipe = replace(REGISTRY['pocketflow-tutorial'], id='fixture-action', public=False, requires_model=False,
                     parameter_model=FixtureParameters, input_commit=None,
                     command_builder=lambda source, output, params: [str(PYTHON), '-B', '-u', str(ROOT/'server/tests/action_fixture_worker.py'), 'success', params['message']])
    app.state.runner.recipes[recipe.id] = recipe
    with TestClient(app) as client:
        snap = snapshot(client)
        assert [r['id'] for r in client.get('/api/recipes').json()['items']] == ['pocketflow-tutorial']
        response = client.post('/api/runs', json={'recipe_id': recipe.id, 'snapshot_id': snap['id'], 'parameters': {'message':'fixture output'}})
        assert response.status_code == 201, response.text
        run = wait_for(client, response.json()['id'], {'succeeded','failed'})
        assert run['status'] == 'succeeded', run
        assert run['recipe_id'] == recipe.id
        assert json.loads(run['parameters_json'])['message'] == 'fixture output'
        artifact = run['artifacts'][0]
        assert client.get(f"/api/runs/{run['id']}/artifacts/{artifact['id']}").json()['content'] == 'fixture output'


def test_cache_identity_includes_all_recipe_parameters():
    from app.runner import result_cache_key
    base = dict(snapshot_id='snapshot', snapshot_revision='sha256:abc', mode='pocketflow', provider='OPENROUTER', model='test',
                prompt_version='v1', language='zh', topics=3, scope='utils', scenario='success', recipe_id='recipe', recipe_version='1')
    assert result_cache_key(**base, recipe_parameters={'extra':'a'}) != result_cache_key(**base, recipe_parameters={'extra':'b'})


def test_dependency_mismatch_marks_runtime_unready(tmp_path, monkeypatch):
    from app.recipes import pocketflow
    lock = tmp_path / 'requirements.lock'
    lock.write_text('pocketflow==999.0.0\n')
    monkeypatch.setattr(pocketflow, 'DEPENDENCY_LOCK', lock, raising=False)
    assert pocketflow.runtime_ready() is False
