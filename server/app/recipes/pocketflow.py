"""First supported action: M3's verified, pinned PocketFlow worker."""
from pathlib import Path
import json
import subprocess
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from ..config import ROOT
from ..pocketflow_adapter import COMMIT, PYTHON, UPSTREAM, verify_upstream, worker_command
from .definition import ActionRecipe

DEPENDENCY_LOCK = ROOT / 'server/pocketflow/requirements.lock'


class PocketFlowParameters(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    scope: Literal['utils'] = Field(default='utils', title='分析范围')
    language: Literal['zh'] = Field(default='zh', title='任务语言')
    topics: int = Field(default=3, ge=1, le=3, title='核心主题数')


def runtime_ready() -> bool:
    try:
        verify_upstream()
        if not PYTHON.is_file():
            return False
        dependencies = dict(line.split('==', 1) for line in DEPENDENCY_LOCK.read_text().splitlines() if line and not line.startswith('#'))
        check = 'import json,sys; from importlib.metadata import version; assert all(version(name)==expected for name,expected in json.loads(sys.argv[1]).items())'
        result = subprocess.run([str(PYTHON), '-I', '-c', check, json.dumps(dependencies)], env={'PATH': '/usr/bin:/bin'},
                                capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def read_paths() -> tuple[Path, ...]:
    # Grant individual pinned Python files, never untracked source or upstream .env.
    tree = subprocess.run(['git', '-C', str(UPSTREAM), 'ls-tree', '-rz', '--name-only', COMMIT], capture_output=True, timeout=10, check=True)
    files = tuple(UPSTREAM / name.decode() for name in tree.stdout.split(b'\0') if name.endswith(b'.py'))
    return (ROOT / 'server/app', ROOT / 'server/pocketflow/worker.py', *files)


def command(source: Path, output: Path, parameters: dict) -> list[str]:
    return worker_command(source, output, parameters['language'], parameters['topics'])


POCKETFLOW = ActionRecipe(
    id='pocketflow-tutorial', version='1', name='PocketFlow 教程生成',
    verification='M3 已真实验证；M5 登记与隔离验证',
    entry_path='server/pocketflow/worker.py', upstream_name='The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge',
    upstream_commit=COMMIT, runtime='server/pocketflow/.venv', dependencies='server/pocketflow/requirements.lock',
    parameter_model=PocketFlowParameters, command_builder=command, runtime_ready=runtime_ready,
    read_paths=read_paths, input_commit=COMMIT,
)
