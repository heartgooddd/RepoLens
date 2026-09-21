"""Foreground owner for a loopback-only local service; stop never kills by port/PID."""
import argparse
import fcntl
import hmac
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request

from delivery_common import ROOT, DeliveryError, data_directory, fingerprint, run, write_private_json

STATE = ROOT / 'var/local-delivery'


def reserve_port(port):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', port))
        listener.listen(128)
        return listener
    except OSError:
        listener.close()
        raise DeliveryError(f'本机端口 {port} 已被占用；请确认并停止原服务。本工具不会终止未知进程。') from None


def stop(state=STATE):
    try:
        path = state / 'control.json'
        if path.is_symlink() or path.stat().st_size > 4096:
            raise ValueError('invalid control')
        control = json.loads(path.read_text())
        if control['host'] != '127.0.0.1' or len(control['token']) != 64:
            raise ValueError('invalid control')
        with socket.create_connection(('127.0.0.1', int(control['port'])), timeout=3) as connection:
            connection.sendall(json.dumps({'token': control['token'], 'action': 'stop'}).encode() + b'\n')
            if connection.recv(128) != b'stopping\n':
                raise ValueError('invalid reply')
        deadline = time.monotonic() + 20
        while path.exists() and time.monotonic() < deadline:
            time.sleep(.1)
        if path.exists():
            raise DeliveryError('停止请求已发送，但尚未完成；查看启动窗口日志，不要手动删除数据锁。')
        print('RepoLens 已停止；数据保留。')
    except (OSError, ValueError, KeyError, TypeError):
        raise DeliveryError('没有找到本启动器的有效控制连接；服务可能尚未启动或已退出。不会按旧PID停止其他进程。') from None


def check_installation():
    try:
        record = json.loads((STATE / 'installation.json').read_text())
        valid = record['root'] == str(ROOT) and record['fingerprint'] == fingerprint()
    except (OSError, ValueError, KeyError):
        valid = False
    if not valid or not (ROOT / 'web/dist/index.html').is_file():
        raise DeliveryError('尚未完成安装，或源码/锁文件/目录已变化；请先双击 Install.command。')
    python = ROOT / 'server/.venv/bin/python'
    run([python, '-c', 'import fastapi,uvicorn; from app.recipes import REGISTRY; from app.isolation import capability; assert REGISTRY["pocketflow-tutorial"].runtime_ready(); assert capability()["available"]'], cwd=ROOT/'server')
    return python


def authorized_stop(request, token):
    return (isinstance(request, dict) and request.get('action') == 'stop' and
            isinstance(request.get('token'), str) and hmac.compare_digest(request['token'], token))


def service_environment(environ, data):
    environment = {**environ, 'REPOLENS_DATA_DIR': str(data), 'REPOLENS_SERVE_WEB': '1',
                   'REPOLENS_ENABLE_REAL_RUN': environ.get('REPOLENS_ENABLE_REAL_RUN', '0'), 'PYTHONUNBUFFERED': '1'}
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    return environment


def start(*, browser=True):
    if sys.platform != 'darwin':
        raise DeliveryError('当前双击交付仅支持 macOS。')
    STATE.mkdir(parents=True, exist_ok=True)
    STATE.chmod(0o700)
    for name in ('.install.lock', 'control.json', 'service.log'):
        if (STATE / name).is_symlink():
            raise DeliveryError('启动状态包含链接，拒绝覆盖；请检查 var/local-delivery。')
    with (STATE / '.install.lock').open('a') as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DeliveryError('本目录已有启动器或安装程序运行。请使用原窗口或双击 Stop.command。') from None
        python = check_installation()
        data = data_directory()
        environment = service_environment(os.environ, data)
        stopped = False
        def request_stop(*_):
            nonlocal stopped
            stopped = True
        old_handlers = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        child = None
        token = secrets.token_hex(32)
        control_file = STATE / 'control.json'
        try:
            with reserve_port(8000) as listener, reserve_port(0) as control, (STATE / 'service.log').open('ab') as log:
                control.settimeout(.2)
                log.write(b'\n--- RepoLens local start ---\n'); log.flush()
                child = subprocess.Popen([str(python), '-B', str(ROOT/'scripts/service.py'), str(os.getpid()), str(listener.fileno())],
                                         cwd=ROOT/'server', env=environment, stdin=subprocess.DEVNULL, stdout=log,
                                         stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(listener.fileno(),))
                deadline = time.monotonic() + 30
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                while not stopped and time.monotonic() < deadline:
                    if child.poll() is not None:
                        raise DeliveryError(f'后台启动失败（退出码 {child.returncode}）。查看 {STATE / "service.log"}；检查数据锁、迁移及依赖。')
                    try:
                        with opener.open('http://127.0.0.1:8000/api/health', timeout=.5) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(.15)
                else:
                    raise DeliveryError('后台未在30秒内就绪；查看 service.log。')
                write_private_json(control_file, {'host': '127.0.0.1', 'port': control.getsockname()[1], 'token': token, 'data_dir': str(data)})
                print(f'RepoLens 已启动：http://127.0.0.1:8000/\n数据：{data}\n日志：{STATE / "service.log"}\n保持此窗口；Ctrl+C 或 Stop.command 停止。启动本身不发送模型请求。', flush=True)
                if browser:
                    subprocess.run(['/usr/bin/open', 'http://127.0.0.1:8000/'], check=False)
                while not stopped:
                    if child.poll() is not None:
                        raise DeliveryError(f'后台意外退出（{child.returncode}），请查看 service.log。')
                    try:
                        connection, _ = control.accept()
                    except socket.timeout:
                        continue
                    with connection:
                        connection.settimeout(1)
                        try:
                            request = json.loads(connection.recv(1024))
                            if authorized_stop(request, token):
                                connection.sendall(b'stopping\n')
                                stopped = True
                            else:
                                connection.sendall(b'denied\n')
                        except (ValueError, OSError):
                            pass
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=5)
            control_file.unlink(missing_ok=True)
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
        print('后台已退出，数据已保留。', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RepoLens 本机启动/停止')
    parser.add_argument('action', choices=('start', 'stop'))
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        start(browser=not args.no_browser) if args.action == 'start' else stop()
    except (DeliveryError, OSError, ValueError) as error:
        print(f'未完成：{error}', file=sys.stderr)
        raise SystemExit(1)
