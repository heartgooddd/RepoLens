"""Fixed, pinned entry points. RunRequest never supplies a command or executable."""
import os
import json
import subprocess
import sys
from pathlib import Path
from .config import ROOT
from .import_policy import fail

COMMIT = json.loads((ROOT / 'server/pocketflow/source.json').read_text())['commit']
UPSTREAM = ROOT / 'upstream' / 'pocketflow-codebase-knowledge'
PYTHON = ROOT / 'server' / 'pocketflow' / '.venv' / 'bin' / 'python'


def verify_upstream() -> None:
    def git(*args):
        return subprocess.run(['git', '-C', str(UPSTREAM), *args], capture_output=True, check=True, timeout=10).stdout
    try:
        if git('rev-parse', 'HEAD').decode().strip() != COMMIT:
            fail('upstream_changed', 'PocketFlow Commit 与已核对版本不一致。', 409)
        # Check every tracked Python file before importing the entry point.
        for entry in git('ls-tree', '-rz', COMMIT).split(b'\0'):
            if not entry:
                continue
            meta, raw_path = entry.split(b'\t', 1)
            path = raw_path.decode()
            if not (path.endswith('.py') or path in ('requirements.txt', 'LICENSE')):
                continue
            target = UPSTREAM / path
            if target.is_symlink() or target.read_bytes() != git('cat-file', 'blob', meta.split()[2].decode()):
                fail('upstream_changed', 'PocketFlow 入口或依赖文件已修改，请恢复固定版本。', 409)
    except (OSError, subprocess.SubprocessError):
        fail('upstream_unavailable', '无法核对本机 PocketFlow 版本。', 503)


def pocketflow_command(input_dir: Path, output_dir: Path, language: str, topics: int) -> list[str]:
    verify_upstream()
    if not PYTHON.is_file():
        fail('runtime_missing', 'PocketFlow 隔离环境尚未安装。', 503)
    return [str(PYTHON), '-B', '-u', str(UPSTREAM / 'main.py'), '--dir', str(input_dir),
            '--name', 'project', '--output', str(output_dir), '--language', {'zh': 'Chinese', 'en': 'English'}[language],
            '--max-abstractions', str(topics), '--no-cache']


def stub_command(input_dir: Path, output_dir: Path, language: str, topics: int, scenario: str) -> list[str]:
    return [sys.executable, '-B', '-u', str(Path(__file__).with_name('stub_worker.py')),
            '--dir', str(input_dir), '--output', str(output_dir), '--language', language,
            '--topics', str(topics), '--scenario', scenario]


def isolated_environment(run_dir: Path) -> dict[str, str]:
    # Deliberately don't inherit model keys, cloud credentials, proxies or PYTHONPATH.
    home = run_dir / 'home'
    home.mkdir(exist_ok=True)
    return {'PATH': os.defpath, 'HOME': str(home), 'LANG': 'en_US.UTF-8', 'PYTHONUNBUFFERED': '1',
            'TMPDIR': str(run_dir / 'tmp'),
            # --dir does not use GitPython; disable its import-time git discovery.
            'GIT_PYTHON_GIT_EXECUTABLE': '/nonexistent/repolens-git-disabled', 'GIT_PYTHON_REFRESH': 'quiet',
            'PYTHONDONTWRITEBYTECODE': '1', 'PYTHON_DOTENV_DISABLED': '1', 'LOG_DIR': str(run_dir / 'provider-logs')}


def worker_command(input_dir: Path, output_dir: Path, language: str, topics: int) -> list[str]:
    command = pocketflow_command(input_dir, output_dir, language, topics)
    return [*command[:3], str(ROOT / 'server/pocketflow/worker.py'), *command[4:]]
