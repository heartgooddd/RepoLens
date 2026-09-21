"""Bounded public-GitHub imports pinned to immutable commits; repository code is never executed."""

import asyncio
import hashlib
import io
import os
import re
import shutil
import tarfile
import unicodedata
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import quote, urlsplit
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from pydantic import AwareDatetime, Field

from .config import Settings
from .db import connect
from .import_policy import MAX_FILE, MAX_FILES, MAX_TOTAL, excluded, fail, supported, validate_path
from .models import FolderCard, GitHubRepositoryRef, Project, Record, Snapshot, SnapshotFile
from .repository import create_github_snapshot, get_cached_github_snapshot
from .scanner import scan

MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_FILES = 2000
MAX_UNPACKED_BYTES = 32 * 1024 * 1024
NETWORK_DEADLINE_SECONDS = 30
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
PART_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class GitHubImportRequest(Record):
    repository_url: str = Field(max_length=1000)


ImportStatus = Literal["queued", "running", "succeeded", "failed", "interrupted"]
ImportStage = Literal["queued", "resolving", "downloading", "extracting", "scanning", "saving", "complete", "error", "interrupted"]


class GitHubImportJob(Record):
    id: UUID
    repository_url: str
    canonical_url: str
    repository_key: str
    status: ImportStatus
    stage: ImportStage
    progress: int
    commit_sha: str | None
    project_id: UUID | None
    snapshot_id: UUID | None
    cache_hit: bool
    skipped_count: int
    error_code: str | None
    error_message: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_github_url(value: str) -> GitHubRepositoryRef:
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        parsed = None
        port = None
    if (parsed is None or parsed.scheme != "https" or parsed.hostname != "github.com" or port not in (None, 443)
            or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
        fail("invalid_github_url", "请输入完整的公开 GitHub 仓库 HTTPS 地址，例如 https://github.com/owner/repo。")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        # Permit the conventional trailing .git and slash, but no branch, issue, or file subpaths.
        fail("invalid_github_url", "GitHub 地址只能包含 owner/repo，不能包含分支、Issue、查询参数或文件路径。")
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not PART_PATTERN.fullmatch(owner) or not PART_PATTERN.fullmatch(repo) or owner in {".", ".."} or repo in {".", ".."}:
        fail("invalid_github_url", "GitHub 仓库 owner 或 repo 格式不合法。")
    return GitHubRepositoryRef(owner=owner, repo=repo,
                               repository_key=f"{owner.casefold()}/{repo.casefold()}",
                               canonical_url=f"https://github.com/{owner}/{repo}")


def _unsafe(message: str = "GitHub 归档包含越界路径、链接或不受支持的特殊文件。") -> None:
    fail("unsafe_archive", message)


def read_archive(raw: bytes) -> tuple[dict[str, bytes], int]:
    if len(raw) > MAX_ARCHIVE_BYTES:
        fail("github_archive_too_large", "GitHub 压缩包超过 16 MiB 限制。", 413)
    retained: dict[str, bytes] = {}
    normalized: set[str] = set()
    skipped = 0
    total_unpacked = 0
    roots: set[str] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r|gz") as bundle:
            member_count = 0
            for member in bundle:
                member_count += 1
                if member_count > MAX_ARCHIVE_FILES:
                    fail("github_archive_too_large", "GitHub 归档超过 2000 个条目限制。", 413)
                path = PurePosixPath(member.name)
                parts = path.parts
                if path.is_absolute() or len(parts) < 1 or any(part in ("", ".", "..") for part in parts):
                    _unsafe()
                roots.add(parts[0])
                if len(roots) != 1:
                    _unsafe("GitHub 归档必须只有一个仓库根目录。")
                if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                    _unsafe()
                if member.isdir() or len(parts) == 1:
                    continue
                relative = PurePosixPath(*parts[1:]).as_posix()
                try:
                    validate_path(relative)
                except HTTPException:
                    _unsafe()
                total_unpacked += member.size
                if member.size < 0 or total_unpacked > MAX_UNPACKED_BYTES:
                    fail("github_archive_too_large", "GitHub 归档解包后超过 32 MiB 限制。", 413)
                if excluded(relative) or not supported(relative):
                    skipped += 1
                    continue
                if member.size > MAX_FILE:
                    fail("file_too_large", "保留的单个源码文件超过 1 MiB 限制。", 413)
                stream = bundle.extractfile(member)
                if stream is None:
                    _unsafe()
                content = stream.read(MAX_FILE + 1)
                if len(content) != member.size or len(content) > MAX_FILE:
                    fail("file_too_large", "保留的单个源码文件超过 1 MiB 限制。", 413)
                try:
                    content.decode("utf-8")
                except UnicodeDecodeError:
                    skipped += 1
                    continue
                if b"\0" in content:
                    skipped += 1
                    continue
                key = unicodedata.normalize("NFC", relative).casefold()
                if key in normalized:
                    _unsafe("GitHub 归档包含重复或大小写冲突路径。")
                normalized.add(key)
                retained[relative] = content
                if len(retained) > MAX_FILES or sum(len(item) for item in retained.values()) > MAX_TOTAL:
                    fail("project_too_large", "过滤后的源码超过 500 个文件或 8 MiB 限制。", 413)
    except (tarfile.TarError, EOFError, OSError):
        fail("invalid_github_archive", "GitHub 返回的归档无法安全读取。", 502)
    if not retained:
        fail("empty_directory", "GitHub 仓库过滤后没有可扫描的 UTF-8 文本源码。")
    directories = {unicodedata.normalize("NFC", str(parent)).casefold()
                   for path in retained for parent in PurePosixPath(path).parents if str(parent) != "."}
    if normalized & directories:
        _unsafe("GitHub 归档中同一路径同时作为文件和目录。")
    return retained, skipped


def save_snapshot(settings: Settings, source: GitHubRepositoryRef, commit: str, files: dict[str, bytes],
                  snapshot_id: str, folder_cards: list[FolderCard]) -> tuple[str, str]:
    project_id = str(uuid4())
    timestamp = now()
    snapshot = Snapshot(
        id=snapshot_id, project_id=project_id, revision=f"git:{commit}", commit_sha=commit,
        storage_path=f"snapshots/{snapshot_id}", created_at=timestamp,
        files=[SnapshotFile(path=path, size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
               for path, content in sorted(files.items())],
        folder_cards=folder_cards,
    )
    destination = settings.data_dir / snapshot.storage_path
    destination.mkdir(exist_ok=False)
    try:
        for path, content in files.items():
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.resolve().is_relative_to(destination.resolve()):
                _unsafe()
            with target.open("xb") as stream:
                stream.write(content)
        project = Project(id=project_id, name=source.repo, source_type="github", source_label=source.canonical_url,
                          created_at=timestamp, updated_at=timestamp)
        project_id = create_github_snapshot(settings.database, source, project, snapshot)
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return project_id, snapshot_id


class GitHubImporter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.transport = None
        self.tasks: dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        self.network_deadline = NETWORK_DEADLINE_SECONDS

    def start(self) -> None:
        with connect(self.settings.database) as db:
            db.execute("""UPDATE github_import_jobs SET status='interrupted', stage='interrupted', progress=100,
                          error_code='backend_restarted', error_message='后台重启，远程导入已中断。', updated_at=?
                          WHERE status IN ('queued','running')""", (now(),))

    async def close(self) -> None:
        for task in self.tasks.values():
            task.cancel()
        if self.tasks:
            await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)

    def create(self, repository_url: str) -> GitHubImportJob:
        repository = parse_github_url(repository_url)
        job_id = str(uuid4())
        timestamp = now()
        with connect(self.settings.database) as db:
            db.execute("""INSERT INTO github_import_jobs
                (id,repository_url,canonical_url,repository_key,status,stage,progress,created_at,updated_at)
                VALUES (?,?,?,?,'queued','queued',0,?,?)""",
                (job_id, repository_url.strip(), repository.canonical_url, repository.repository_key, timestamp, timestamp))
        task = asyncio.create_task(self.execute(job_id, repository))
        self.tasks[job_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(job_id, None))
        return self.get(job_id)

    def get(self, job_id: str) -> GitHubImportJob | None:
        with connect(self.settings.database) as db:
            row = db.execute("SELECT * FROM github_import_jobs WHERE id = ?", (job_id,)).fetchone()
        return GitHubImportJob(**dict(row)) if row else None

    def update(self, job_id: str, **values) -> None:
        allowed = {"status", "stage", "progress", "commit_sha", "project_id", "snapshot_id", "cache_hit",
                   "skipped_count", "error_code", "error_message"}
        if not values or not values.keys() <= allowed:
            raise ValueError("Invalid GitHub job fields")
        values["updated_at"] = now()
        with connect(self.settings.database) as db:
            db.execute(f"UPDATE github_import_jobs SET {', '.join(key + ' = ?' for key in values)} WHERE id = ?",
                       (*values.values(), job_id))

    async def request(self, client: httpx.AsyncClient, url: str, *, archive: bool = False) -> httpx.Response:
        try:
            if archive:
                chunks = bytearray()
                async with client.stream("GET", url) as response:
                    self.check_response(response)
                    length = response.headers.get("content-length")
                    if length and int(length) > MAX_ARCHIVE_BYTES:
                        fail("github_archive_too_large", "GitHub 压缩包超过 16 MiB 限制。", 413)
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_ARCHIVE_BYTES:
                            fail("github_archive_too_large", "GitHub 压缩包超过 16 MiB 限制。", 413)
                return httpx.Response(200, content=bytes(chunks), request=response.request)
            response = await client.get(url)
            self.check_response(response)
            return response
        except HTTPException:
            raise
        except httpx.TimeoutException:
            fail("github_timeout", "GitHub 连接或单次网络读取超时，请稍后重试。", 504)
        except (httpx.HTTPError, ValueError):
            fail("github_unavailable", "无法安全读取 GitHub，请检查网络后重试。", 502)

    @staticmethod
    def check_response(response: httpx.Response) -> None:
        if response.status_code in (403, 429) and response.headers.get("x-ratelimit-remaining") == "0":
            fail("github_rate_limited", "GitHub API 已限流，请等待额度恢复或在本机配置 Token。", 429)
        if response.status_code == 404:
            fail("github_repository_not_found", "公开仓库不存在、已改名或不可访问。", 404)
        if response.status_code >= 400:
            fail("github_unavailable", f"GitHub 返回 HTTP {response.status_code}，未创建快照。", 502)

    async def execute(self, job_id: str, repository: GitHubRepositoryRef) -> None:
        try:
            async with self.lock:
                self.update(job_id, status="running", stage="resolving", progress=10)
                headers = {"Accept": "application/vnd.github+json", "User-Agent": "RepoLens-local/0.4",
                           "X-GitHub-Api-Version": "2022-11-28"}
                token = os.environ.get("REPOLENS_GITHUB_TOKEN")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                timeout = httpx.Timeout(20, connect=5)
                async with asyncio.timeout(self.network_deadline):
                    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=False,
                                                 trust_env=False, transport=self.transport) as client:
                        base = f"https://api.github.com/repos/{quote(repository.owner, safe='')}/{quote(repository.repo, safe='')}"
                        metadata = (await self.request(client, base)).json()
                        if metadata.get("private") is True or not metadata.get("default_branch"):
                            fail("github_repository_not_found", "只支持无需登录即可读取的公开 GitHub 仓库。", 404)
                        branch = quote(str(metadata["default_branch"]), safe="")
                        commit_data = (await self.request(client, f"{base}/commits/{branch}")).json()
                        commit = str(commit_data.get("sha", "")).lower()
                        if not SHA_PATTERN.fullmatch(commit):
                            fail("github_invalid_response", "GitHub 未返回可固定的 40 位 Commit。", 502)
                        self.update(job_id, commit_sha=commit, progress=25)
                        cached = get_cached_github_snapshot(self.settings.database, repository.repository_key, commit)
                        if cached:
                            self.update(job_id, status="succeeded", stage="complete", progress=100,
                                        project_id=cached["project_id"], snapshot_id=cached["snapshot_id"], cache_hit=1)
                            return
                        self.update(job_id, stage="downloading", progress=35)
                        archive_url = f"https://codeload.github.com/{quote(repository.owner, safe='')}/{quote(repository.repo, safe='')}/tar.gz/{commit}"
                        response = await self.request(client, archive_url, archive=True)
                self.update(job_id, stage="extracting", progress=60)
                files, skipped = await asyncio.to_thread(read_archive, response.content)
                self.update(job_id, stage="scanning", progress=75, skipped_count=skipped)
                snapshot_id = str(uuid4())
                folder_cards = await asyncio.to_thread(scan, files, snapshot_id)
                self.update(job_id, stage="saving", progress=90)
                project_id, snapshot_id = await asyncio.to_thread(
                    save_snapshot, self.settings, repository, commit, files, snapshot_id, folder_cards)
                self.update(job_id, status="succeeded", stage="complete", progress=100,
                            project_id=project_id, snapshot_id=snapshot_id, cache_hit=0)
        except asyncio.CancelledError:
            self.update(job_id, status="interrupted", stage="interrupted", progress=100,
                        error_code="backend_stopped", error_message="后台关闭，远程导入已中断。")
            raise
        except TimeoutError:
            self.update(job_id, status="failed", stage="error", progress=100,
                        error_code="github_timeout", error_message="GitHub 解析与归档下载合计超过 30 秒限制。")
        except HTTPException as error:
            detail = error.detail if isinstance(error.detail, dict) else {}
            self.update(job_id, status="failed", stage="error", progress=100,
                        error_code=detail.get("code", "github_import_failed"),
                        error_message=detail.get("message", "GitHub 导入失败。"))
        except Exception:
            self.update(job_id, status="failed", stage="error", progress=100,
                        error_code="github_import_failed", error_message="GitHub 导入失败，未保存不完整快照。")
