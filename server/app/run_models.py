from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, Field
from .models import Record

Status = Literal['queued', 'running', 'cancelling', 'cancelled', 'succeeded', 'failed', 'interrupted']
ACTIVE = ('queued', 'running', 'cancelling')
STAGES = ('FetchRepo', 'IdentifyAbstractions', 'AnalyzeRelationships', 'OrderChapters', 'WriteChapters', 'CombineTutorial', 'FolderResponsibilities')


class RunRequest(Record):
    mode: Literal['stub', 'pocketflow'] = 'stub'
    snapshot_id: UUID
    language: Literal['zh', 'en'] = 'zh'
    topics: int = Field(default=3, ge=1, le=10)
    scope: str = '.'
    scenario: Literal['success', 'failure', 'slow'] = 'success'


class Artifact(Record):
    id: str
    run_id: str
    path: str
    size_bytes: int
    sha256: str


class Run(Record):
    id: str
    snapshot_id: str
    mode: Literal['stub', 'pocketflow']
    status: Status
    stage: str
    language: str
    topics: int
    scope: str
    scenario: str
    created_at: AwareDatetime
    started_at: AwareDatetime | None
    ended_at: AwareDatetime | None
    exit_code: int | None
    error: str | None
    upstream_commit: str
    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    model_usage: str | None = None
    result_cache_key: str | None = None
    artifacts: list[Artifact] = Field(default_factory=list)


class LogSlice(Record):
    offset: int
    next_offset: int
    content: str
    finished: bool
