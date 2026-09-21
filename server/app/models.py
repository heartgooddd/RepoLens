"""Typed API contract. Paths are relative to a snapshot, never host file paths."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, AfterValidator, AwareDatetime, field_serializer, model_validator


def relative_path(value: str) -> str:
    if value == ".":
        return value
    if not value or value.startswith("/") or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError("Expected a normalized relative POSIX path")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError("Expected a normalized relative POSIX path")
    return value


RelativePath = Annotated[str, AfterValidator(relative_path)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_serializer("created_at", "updated_at", check_fields=False)
    def utc_timestamp(self, value: datetime) -> str:
        # Fixed-width UTC strings keep SQLite's lexical chronological ordering correct.
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class Project(Record):
    id: UUID
    name: str = Field(min_length=1, max_length=200)
    source_type: Literal["builtin", "local_upload", "github", "test_fixture"]
    source_label: str = Field(min_length=1, max_length=500)
    created_at: AwareDatetime
    updated_at: AwareDatetime


class GitHubRepositoryRef(Record):
    repository_key: str = Field(min_length=3, max_length=201)
    canonical_url: str = Field(min_length=20, max_length=500)
    owner: str = Field(min_length=1, max_length=100)
    repo: str = Field(min_length=1, max_length=100)


class ProjectSummary(Project):
    snapshot_count: int


class ProjectList(Record):
    items: list[ProjectSummary]
    total: int
    limit: int
    offset: int


class EvidenceRef(Record):
    id: UUID
    folder_card_id: UUID
    snapshot_id: UUID
    file_path: RelativePath
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    symbol: str | None = None
    excerpt: str

    @model_validator(mode="after")
    def ordered_lines(self) -> "EvidenceRef":
        if self.line_end < self.line_start or self.file_path == ".":
            raise ValueError("Evidence requires a file and an inclusive, ordered line range")
        return self


class FolderCard(Record):
    id: UUID
    snapshot_id: UUID
    path: RelativePath
    title: str
    description: str
    claim_type: Literal["fact", "inference", "unverified"]
    inference: str | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class SnapshotFile(Record):
    path: RelativePath
    size_bytes: int = Field(ge=0)
    sha256: str


class Snapshot(Record):
    id: UUID
    project_id: UUID
    revision: str = Field(min_length=1)
    commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
    storage_path: RelativePath
    created_at: AwareDatetime
    folder_cards: list[FolderCard] = Field(default_factory=list)
    files: list[SnapshotFile] = Field(default_factory=list)

    @model_validator(mode="after")
    def snapshot_location(self) -> "Snapshot":
        if self.storage_path != f"snapshots/{self.id}":
            raise ValueError("storage_path must be snapshots/<snapshot-id>")
        return self


class ProjectDetail(Record):
    project: Project
    snapshots: list[Snapshot] = Field(default_factory=list)

    @model_validator(mode="after")
    def linked_records(self) -> "ProjectDetail":
        for snapshot in self.snapshots:
            if snapshot.project_id != self.project.id:
                raise ValueError("Snapshot belongs to another project")
            for card in snapshot.folder_cards:
                if card.snapshot_id != snapshot.id:
                    raise ValueError("Folder card belongs to another snapshot")
                for evidence in card.evidence_refs:
                    if evidence.snapshot_id != snapshot.id or evidence.folder_card_id != card.id:
                        raise ValueError("Evidence belongs to another card or snapshot")
        return self


class Health(Record):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
    schema_version: int
