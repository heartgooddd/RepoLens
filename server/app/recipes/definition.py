"""Immutable Python-action contract, registered by application code only."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from pydantic import BaseModel
from ..import_policy import validate_path

CommandBuilder = Callable[[Path, Path, dict], list[str]]


@dataclass(frozen=True)
class ActionRecipe:
    id: str
    version: str
    name: str
    verification: str
    entry_path: str
    upstream_name: str
    upstream_commit: str
    runtime: str
    dependencies: str
    parameter_model: type[BaseModel]
    command_builder: CommandBuilder
    runtime_ready: Callable[[], bool]
    read_paths: Callable[[], tuple[Path, ...]]
    input_commit: str | None
    public: bool = True
    requires_model: bool = True
    network: bool = True
    timeout_seconds: float = 900
    max_timeout_seconds: int = 900
    stop_grace_seconds: float = 0.2
    required_artifacts: tuple[str, ...] = ('project/index.md',)
    artifact_suffixes: tuple[str, ...] = ('.md', '.json')

    def __post_init__(self):
        if not 0 < self.timeout_seconds <= self.max_timeout_seconds or not 0 < self.stop_grace_seconds <= 5:
            raise ValueError('Invalid recipe time limits')
        for path in self.required_artifacts:
            validate_path(path)

    def description(self) -> dict:
        return {
            'id': self.id, 'version': self.version, 'name': self.name, 'verification': self.verification,
            'entry': {'path': self.entry_path, 'upstream': self.upstream_name, 'commit': self.upstream_commit},
            'environment': {'runtime': self.runtime, 'dependencies': self.dependencies, 'ready': self.runtime_ready()},
            'parameters': self.parameter_model.model_json_schema(),
            'input': {'commit': self.input_commit, 'read_only': True, 'kind': 'registered-snapshot'},
            'working_directory': 'var/runs/<run-id>',
            'timeout_seconds': self.timeout_seconds, 'max_timeout_seconds': self.max_timeout_seconds,
            'stop': {'signals': ['SIGTERM', 'SIGKILL'], 'grace_seconds': self.stop_grace_seconds, 'scope': 'process-group'},
            'artifacts': {'root': 'output', 'required': list(self.required_artifacts), 'suffixes': list(self.artifact_suffixes), 'max_files': 32, 'max_file_bytes': 524288, 'max_total_bytes': 4194304},
            'network': 'outbound' if self.network else 'disabled',
            'requires_model': self.requires_model,
        }
