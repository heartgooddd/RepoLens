import json
import subprocess
import sys


def test_sandbox_enforces_input_output_and_outside_boundaries(tmp_path):
    from app import isolation
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'input').mkdir()
    source = run / 'input/source.txt'
    source.write_text('allowed')
    outside = tmp_path / 'private.txt'
    outside.write_text('private')
    script = '''import json, pathlib, sys
run, outside = map(pathlib.Path, sys.argv[1:])
result = {'input': (run/'input/source.txt').read_text()}
for name, path, mode in [('outside_read', outside, 'r'), ('outside_write', outside, 'w'), ('input_write', run/'input/source.txt', 'w')]:
    try:
        with path.open(mode) as f:
            f.read() if mode == 'r' else f.write('bad')
        result[name] = 'allowed'
    except PermissionError:
        result[name] = 'denied'
(run/'output/result.json').write_text(json.dumps(result))
print(json.dumps(result))
'''
    command = isolation.sandbox_command([sys.executable, '-B', '-c', script, str(run), str(outside)], run, (), network=False)
    result = subprocess.run(command, capture_output=True, text=True, timeout=10, cwd=run)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'input': 'allowed', 'outside_read': 'denied', 'outside_write': 'denied', 'input_write': 'denied'}
    assert outside.read_text() == 'private'
    assert source.read_text() == 'allowed'


def test_isolation_fails_closed_on_other_platforms(monkeypatch):
    from app import isolation
    monkeypatch.setattr(isolation.sys, 'platform', 'linux')
    assert isolation.capability()['available'] is False


def test_pinned_runtime_imports_inside_sandbox_without_model_call(tmp_path):
    from app.isolation import sandbox_command
    from app.pocketflow_adapter import PYTHON, UPSTREAM, isolated_environment
    from app.recipes import REGISTRY
    command = [str(PYTHON), '-B', '-c', 'import sys; sys.path.insert(0,sys.argv[1]); import nodes; print("pinned imports ready")', str(UPSTREAM)]
    wrapped = sandbox_command(command, tmp_path, REGISTRY['pocketflow-tutorial'].read_paths(), network=False)
    result = subprocess.run(wrapped, cwd=tmp_path, env=isolated_environment(tmp_path), capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_capability_probe_requires_enforced_denial(monkeypatch):
    from pathlib import Path
    from app import isolation
    monkeypatch.setattr(isolation, 'SANDBOX', Path('/usr/bin/true'))
    isolation._probe.cache_clear()
    try:
        assert isolation.capability()['available'] is False
    finally:
        isolation._probe.cache_clear()


def test_worker_cannot_signal_owning_service(tmp_path):
    import os
    from app.isolation import sandbox_command
    script = 'import os,sys\ntry: os.kill(int(sys.argv[1]),0)\nexcept PermissionError: sys.exit(0)\nelse: sys.exit(2)'
    command = sandbox_command([sys.executable, '-B', '-c', script, str(os.getpid())], tmp_path, (), network=False)
    result = subprocess.run(command, capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr
