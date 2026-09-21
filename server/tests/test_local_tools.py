"""Local delivery tools: no model calls; synthetic git only tests installer mechanics."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    path = ROOT / 'scripts' / f'{name}.py'
    assert path.is_file(), f'Missing delivery tool: {name}'
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(result)
    return result


def test_dependency_error_is_actionable(monkeypatch):
    installer = module('install')
    monkeypatch.setattr(installer.shutil, 'which', lambda _: None)
    with pytest.raises(installer.DeliveryError, match='Python 3.14'):
        installer.prerequisites()


def test_pinned_checkout_repeat_and_modified_refusal(tmp_path):
    installer = module('install')
    origin = tmp_path / 'source'
    origin.mkdir()
    def git(*args):
        return subprocess.run(['git', '-C', str(origin), *args], check=True, text=True, capture_output=True).stdout.strip()
    git('init')
    (origin / 'LICENSE').write_text('test fixture license')
    git('add', 'LICENSE')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
    commit = git('rev-parse', 'HEAD')
    target = tmp_path / 'install with spaces' / 'upstream'
    installer.prepare_upstream(target, str(origin), commit)
    installer.prepare_upstream(target, str(origin), commit)
    assert (target / 'LICENSE').read_text() == 'test fixture license'
    (target / 'LICENSE').write_text('user change')
    with pytest.raises(installer.DeliveryError, match='修改|不匹配'):
        installer.prepare_upstream(target, str(origin), commit)
    assert (target / 'LICENSE').read_text() == 'user change'


def test_installer_rejects_wrong_existing_commit(tmp_path):
    installer = module('install')
    target = tmp_path / 'existing'
    target.mkdir()
    with pytest.raises(installer.DeliveryError, match='不匹配|不是'):
        installer.prepare_upstream(target)
    assert target.exists()


def test_port_conflict_never_kills_owner():
    local = module('local')
    import socket
    with socket.socket() as owner:
        owner.bind(('127.0.0.1', 0))
        owner.listen()
        port = owner.getsockname()[1]
        with pytest.raises(local.DeliveryError, match='占用'):
            local.reserve_port(port)
        assert owner.fileno() >= 0


def test_stop_rejects_untrusted_control_address(tmp_path):
    local = module('local')
    state = tmp_path / 'control.json'
    state.write_text(json.dumps({'host': 'example.com', 'port': 8000, 'token': 'x'}))
    with pytest.raises(local.DeliveryError, match='控制|启动'):
        local.stop(tmp_path)


def test_install_stamp_detects_changed_lock(tmp_path):
    common = module('delivery_common')
    for name in common.FINGERPRINT_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('original')
    before = common.fingerprint(tmp_path)
    (tmp_path / common.FINGERPRINT_FILES[0]).write_text('changed')
    assert common.fingerprint(tmp_path) != before


def test_finder_entry_prefers_user_tool_installation():
    entry = (ROOT / 'scripts/entry.sh').read_text()
    assert entry.index('$HOME/.local/bin') < entry.index('/opt/homebrew/bin')


def test_control_record_has_private_permissions(tmp_path):
    common = module('delivery_common')
    path = tmp_path / 'control.json'
    common.write_private_json(path, {'token': 'test only'})
    assert json.loads(path.read_text()) == {'token': 'test only'}
    assert path.stat().st_mode & 0o777 == 0o600


def test_immediate_restart_after_serving_a_connection():
    local = module('local')
    import socket
    listener = local.reserve_port(0)
    port = listener.getsockname()[1]
    with socket.create_connection(('127.0.0.1', port)) as client:
        peer, _ = listener.accept()
        peer.shutdown(socket.SHUT_RDWR)
        peer.close()
    listener.close()
    with local.reserve_port(port):
        pass


@pytest.mark.parametrize('body', [None, [], 1, 'stop', {}, {'action':'stop','token':'wrong'}])
def test_control_requires_authenticated_object(body):
    local = module('local')
    assert hasattr(local, 'authorized_stop'), 'Missing control request validator'
    assert local.authorized_stop(body, 'secret') is False


def test_real_mode_requires_explicit_opt_in():
    local = module('local')
    assert hasattr(local, 'service_environment')
    assert local.service_environment({}, '/data')['REPOLENS_ENABLE_REAL_RUN'] == '0'
    assert local.service_environment({'REPOLENS_ENABLE_REAL_RUN':'1'}, '/data')['REPOLENS_ENABLE_REAL_RUN'] == '1'
