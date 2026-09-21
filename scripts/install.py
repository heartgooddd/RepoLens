"""Reproduce the two pinned environments and frontend from a clean Git checkout."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from delivery_common import ROOT, DeliveryError, fingerprint, run, write_private_json

SOURCE = json.loads((ROOT / 'server/pocketflow/source.json').read_text())


def require_python314(python):
    try:
        valid = run([python, '-c', 'import sys,ssl,sqlite3,venv; print(".".join(map(str,sys.version_info[:2])))']) == '3.14'
    except DeliveryError:
        valid = False
    if not valid:
        raise DeliveryError(f'{python} 不是可用的 Python 3.14。若是现有.venv，请先另存/重命名该环境目录，再安装；不会自动删除。')


def prerequisites():
    python = shutil.which('python3.14')
    if not python:
        raise DeliveryError('缺少 Python 3.14。请先安装 Python 3.14（含 venv/ssl/sqlite3），再双击 Install.command。')
    for tool in ('git', 'node', 'npm'):
        if not shutil.which(tool):
            raise DeliveryError(f'缺少 {tool}。请按 docs/05-local-setup-and-trial.md 安装 Git 和 Node.js 22，再重试。')
    require_python314(python)
    version = tuple(int(part) for part in run(['node', '--version']).lstrip('v').split('.')[:2])
    if version[0] != 22 or version < (22, 12):
        raise DeliveryError('本地交付已验收 Node.js 22.12+（22.x）；请安装该版本后重试。')
    run(['git', '--version'])
    return python


def git(directory, *args):
    environment = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_GLOBAL': '/dev/null',
                   'GIT_CONFIG_SYSTEM': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1'}
    return run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'credential.helper=', '-C', directory, *args], env=environment)


def prepare_upstream(target, url=SOURCE['url'], commit=SOURCE['commit']):
    if target.is_symlink():
        raise DeliveryError('上游路径不是普通目录；不会覆盖链接。')
    if target.exists():
        try:
            valid = (git(target, 'rev-parse', 'HEAD') == commit and
                     git(target, 'remote', 'get-url', 'origin') == url and
                     not git(target, 'status', '--porcelain', '--untracked-files=all'))
        except DeliveryError:
            valid = False
        if not valid:
            raise DeliveryError('已有 PocketFlow 来源/Commit 不匹配或存在修改；请另存后手动处理，不会覆盖。')
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.pocketflow-install-', dir=target.parent) as temporary:
        checkout = Path(temporary) / 'checkout'
        checkout.mkdir()
        git(checkout, 'init', '--quiet')
        git(checkout, 'remote', 'add', 'origin', url)
        git(checkout, 'fetch', '--depth', '1', 'origin', commit)
        git(checkout, 'checkout', '--detach', 'FETCH_HEAD')
        if git(checkout, 'rev-parse', 'HEAD') != commit or not (checkout / 'LICENSE').is_file():
            raise DeliveryError('PocketFlow 版本或许可证核对失败。')
        checkout.rename(target)


def install():
    if sys.platform != 'darwin':
        raise DeliveryError('本交付仅支持已验收的 macOS；不降级关闭运行隔离。')
    python = prerequisites()
    state = ROOT / 'var/local-delivery'
    state.mkdir(parents=True, exist_ok=True)
    with (state / '.install.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DeliveryError('另一个安装正在进行，请等其完成。') from None
        # The launcher also holds this lock throughout execution.
        print('1/4 核验并准备固定 PocketFlow 源码（不会执行仓库安装脚本）', flush=True)
        prepare_upstream(ROOT / 'upstream/pocketflow-codebase-knowledge')
        for name in ('server', 'server/pocketflow'):
            environment = ROOT / name / '.venv'
            print(f'2/4 安装精确依赖：{name}，首次需要联网', flush=True)
            if not environment.exists():
                run([python, '-m', 'venv', environment])
            interpreter = environment / 'bin/python'
            require_python314(interpreter)
            run([interpreter, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', ROOT / name / 'requirements.lock'], timeout=1200)
            run([interpreter, '-m', 'pip', 'check'])
        print('3/4 安装前端锁定依赖并构建页面', flush=True)
        run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=ROOT / 'web', timeout=600)
        run(['npm', 'run', 'build'], cwd=ROOT / 'web', timeout=180)
        print('4/4 检查入口、运行隔离并写入安装记录', flush=True)
        run([ROOT/'server/.venv/bin/python', '-c',
             'from app.recipes import REGISTRY; from app.isolation import capability; assert REGISTRY["pocketflow-tutorial"].runtime_ready(), "runtime unavailable"; assert capability()["available"], "sandbox unavailable"'], cwd=ROOT/'server')
        config = ROOT / 'server/.env'
        if not config.exists():
            with open(config, 'x', opener=lambda p, flags: os.open(p, flags | os.O_NOFOLLOW, 0o600)) as stream:
                stream.write('# 本机密钥，不提交、不备份。填写后重启；不会自动调用模型。\nOPENROUTER_API_KEY=\n')
        write_private_json(state / 'installation.json', {'format': 1, 'fingerprint': fingerprint(), 'root': str(ROOT), 'source': SOURCE})
        print('安装完成。双击 Start.command；密钥可稍后按文档配置。', flush=True)


if __name__ == '__main__':
    try:
        install()
    except (DeliveryError, OSError, ValueError) as error:
        print(f'安装未完成：{error}', file=sys.stderr)
        raise SystemExit(1)
