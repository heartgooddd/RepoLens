"""Fail-closed macOS Seatbelt execution for explicitly registered, trusted entries."""
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

SANDBOX = Path('/usr/bin/sandbox-exec')
WRITABLE = ('output', 'home', 'tmp', 'model-data', 'provider-logs')


@lru_cache(maxsize=8)
def runtime_paths(python: str) -> tuple[Path, ...]:
    result = subprocess.run(
        [python, '-I', '-c', 'import sys,json,ssl; print(json.dumps([sys.prefix,sys.base_prefix,ssl.get_default_verify_paths().cafile]))'],
        capture_output=True, text=True, timeout=10, check=True,
    )
    paths = [Path(path).resolve() for path in json.loads(result.stdout) if path]
    # Homebrew Python links OpenSSL dynamically; do not grant the entire Cellar.
    paths.extend(path.resolve() for path in (Path('/opt/homebrew/opt/openssl@3/lib'), Path('/usr/local/opt/openssl@3/lib')) if path.is_dir())
    return tuple(paths)


def profile(command: list[str], run_dir: Path, read_paths: tuple[Path, ...], *, network: bool) -> str:
    run_dir = run_dir.resolve()
    # Metadata traversal does not grant file contents or directory enumeration.
    rules = ['(version 1)', '(deny default)', '(allow file-read-metadata)',
             '(allow file-read* (literal "/"))',
             '(allow process-exec process-fork)', '(allow signal (target self) (target children))', '(allow sysctl-read)']
    reads = [Path('/System/Library'), Path('/usr/lib'), Path('/usr/share/zoneinfo'),
             Path('/private/etc/ssl'), Path('/private/etc/hosts'), Path('/private/etc/resolv.conf'),
             Path('/private/var/run/resolv.conf'), Path('/dev/null'), Path('/dev/urandom'),
             Path('/dev/random'), run_dir / 'input', *runtime_paths(command[0]), *read_paths]
    for path in reads:
        resolved = path.resolve()
        kind = 'subpath' if resolved.is_dir() else 'literal'
        rules.append(f'(allow file-read* ({kind} {json.dumps(str(resolved))}))')
        for parent in resolved.parents:
            rules.append(f'(allow file-read-data (literal {json.dumps(str(parent))}))')
    for name in WRITABLE:
        path = run_dir / name
        path.mkdir(exist_ok=True)
        if path.is_symlink():
            raise ValueError('Writable directory cannot be a link')
        rules.append(f'(allow file-read* file-write* (subpath {json.dumps(str(path))}))')
    rules.append('(allow file-write* (literal "/dev/null"))')
    if network:
        rules.extend(['(allow network-outbound)',
                      '(allow mach-lookup (global-name "com.apple.system.configd") (global-name "com.apple.mDNSResponder"))'])
    return '\n'.join(rules)


@lru_cache(maxsize=1)
def _probe() -> bool:
    try:
        with TemporaryDirectory(prefix='repolens-isolation-') as temporary:
            base = Path(temporary).resolve()
            run = base / 'run'
            (run / 'input').mkdir(parents=True)
            (run / 'input/source.txt').write_text('input')
            (base / 'outside.txt').write_text('outside')
            script = '''from pathlib import Path
import sys
base = Path(sys.argv[1])
assert (base/'run/input/source.txt').read_text() == 'input'
for path, mode in [(base/'outside.txt','r'),(base/'outside.txt','w'),(base/'run/input/source.txt','w')]:
    try:
        with path.open(mode): pass
    except PermissionError: continue
    raise SystemExit(2)
(base/'run/output/probe.txt').write_text('ok')
print('boundaries-enforced')
'''
            command = [sys.executable, '-I', '-B', '-c', script, str(base)]
            policy = profile(command, run, (), network=False)
            result = subprocess.run([str(SANDBOX), '-p', policy, *command], capture_output=True, text=True, timeout=5,
                                    env={'PATH': '/usr/bin:/bin'}, cwd=run)
            return result.returncode == 0 and result.stdout.strip() == 'boundaries-enforced' and (run/'output/probe.txt').read_text() == 'ok'
    except (OSError, subprocess.SubprocessError):
        return False


def capability() -> dict:
    available = sys.platform == 'darwin' and SANDBOX.is_file() and _probe()
    return {'kind': 'macos-seatbelt', 'available': available,
            'reason': None if available else '需要可用的 macOS sandbox-exec；隔离检查未通过。'}


def sandbox_command(command: list[str], run_dir: Path, read_paths: tuple[Path, ...], *, network: bool) -> list[str]:
    if not capability()['available']:
        raise RuntimeError('isolation_unavailable')
    policy = profile(command, run_dir, read_paths, network=network)
    (run_dir / 'sandbox.sb').write_text(policy, encoding='utf-8')
    # Pass immutable policy as argv; a worker cannot rewrite the active policy file.
    return [str(SANDBOX), '-p', policy, *command]
