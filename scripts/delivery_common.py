"""Dependency-free shared paths, input fingerprint and readable delivery errors."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FINGERPRINT_FILES = ('server/requirements.lock', 'server/pocketflow/requirements.lock',
                     'server/pocketflow/source.json', 'web/package-lock.json', 'web/package.json',
                     'web/index.html', 'web/vite.config.ts', 'web/tsconfig.json')


class DeliveryError(RuntimeError):
    pass


def fingerprint(root=ROOT):
    files = [root / name for name in FINGERPRINT_FILES]
    files += sorted((root / 'web/src').rglob('*'))
    digest = hashlib.sha256()
    for path in files:
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b'\0' + path.read_bytes())
    return digest.hexdigest()


def data_directory():
    path = Path(os.environ.get('REPOLENS_DATA_DIR', str(ROOT / 'var'))).expanduser()
    if not path.is_absolute():
        raise DeliveryError('REPOLENS_DATA_DIR 必须是绝对路径。')
    return path.resolve()


def run(command, *, cwd=ROOT, timeout=120, env=None):
    try:
        result = subprocess.run([str(v) for v in command], cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=timeout, check=True)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise DeliveryError(f'{Path(command[0]).name} 超时（{timeout}秒）；检查网络后重试安装。') from None
    except (OSError, subprocess.CalledProcessError) as error:
        # Do not echo subprocess environment/output: it can contain package-index credentials.
        code = getattr(error, 'returncode', None)
        raise DeliveryError(f'{Path(command[0]).name} 执行失败（退出码 {code}）；检查网络、工具权限及锁文件依赖。') from None


def write_private_json(path, value):
    with open(path, 'w', opener=lambda p, flags: os.open(p, flags | os.O_NOFOLLOW, 0o600)) as stream:
        json.dump(value, stream, ensure_ascii=False)
    path.chmod(0o600)
