"""Read public GitHub trees and selected immutable blobs, in bounded memory only.

No archive, clone, checkout, database row, or source file is written by this service.
The architecture covers loaded text only; the directory inventory is separate.
"""
import asyncio
import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from .architecture import ArchitectureMap, build_architecture, _imports, _manifest_refs, _html_refs
from .github_importer import GitHubImportRequest, parse_github_url, SHA_PATTERN
from .import_policy import MAX_FILE, MAX_TOTAL, excluded, supported, validate_path, fail
from .models import Record
from .source import SourceSlice

MAX_TREE_BYTES = 8 * 1024 * 1024
MAX_TREE_ENTRIES = 20000
MAX_SESSIONS = 8
SESSION_TTL = 1800
MAX_LOADED_FILES = 120
BATCH_SIZE = 12


class OnlineFile(Record):
    path: str
    size_bytes: int
    sha: str
    loaded: bool = False


class OnlineProject(Record):
    id: UUID
    name: str
    repository_url: str
    commit_sha: str
    files: list[OnlineFile]
    excluded_count: int
    loaded_count: int
    architecture: ArchitectureMap
    warnings: list[str]


class ReadRequest(Record):
    paths: list[str] = Field(default_factory=list, max_length=BATCH_SIZE)


@dataclass
class Session:
    id: UUID
    name: str
    url: str
    base: str
    commit: str
    files: dict[str, OnlineFile]
    excluded_count: int
    text: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    touched: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def seed_rank(path: str) -> tuple[int, int, str]:
    name = PurePosixPath(path).name.lower()
    priorities = {"readme.md": 0, "package.json": 1, "pyproject.toml": 1, "index.html": 2,
                  "main.py": 3, "main.tsx": 3, "main.ts": 3, "main.js": 3,
                  "app.tsx": 4, "app.py": 4, "index.ts": 5, "index.js": 5, "flow.py": 5}
    return priorities.get(name, 20 if PurePosixPath(path).suffix in {".py", ".ts", ".tsx", ".js", ".jsx"} else 50), path.count("/"), path


class OnlineExplorer:
    def __init__(self, transport=None):
        self.transport = transport
        self.sessions: dict[UUID, Session] = {}
        self.open_lock = asyncio.Lock()
        self.network_lock = asyncio.Semaphore(4)

    def client(self):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "RepoLens/online-explorer",
                   "X-GitHub-Api-Version": "2022-11-28"}
        token = os.environ.get("REPOLENS_GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(12, connect=5),
                                 follow_redirects=False, trust_env=False, transport=self.transport)

    async def get_json(self, client, url, limit=MAX_TREE_BYTES):
        # URLs are constructed from validated owner/repo, commit and blob hashes only.
        try:
            async with self.network_lock, asyncio.timeout(18):
                async with client.stream("GET", url) as response:
                    if response.status_code in (403, 429):
                        fail("github_rate_limited", "GitHub 暂时限制读取。请稍后重试，或在后台设置 REPOLENS_GITHUB_TOKEN 提高额度。", 429)
                    if response.status_code == 404:
                        fail("github_not_found", "公开仓库或文件不可访问，请检查地址。", 404)
                    if response.status_code != 200:
                        fail("github_unavailable", f"GitHub 返回 HTTP {response.status_code}，请稍后重试。", 502)
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > limit:
                            fail("github_response_too_large", "GitHub 响应超过在线读取限制，请选择较小的仓库或文件。", 413)
                    value = json.loads(data)
                    if not isinstance(value, dict):
                        raise ValueError("Expected object")
                    return value
        except HTTPException:
            raise
        except (httpx.TimeoutException, TimeoutError):
            fail("github_timeout", "GitHub 读取超时，请重试。已读取的文件仍可查看。", 504)
        except (httpx.HTTPError, ValueError):
            fail("github_unavailable", "无法读取 GitHub 返回的数据，请稍后重试。", 502)

    def session(self, session_id: UUID) -> Session:
        now = time.monotonic()
        for key, item in list(self.sessions.items()):
            if now - item.touched > SESSION_TTL and not item.lock.locked():
                del self.sessions[key]
        item = self.sessions.get(session_id)
        if item is None:
            fail("online_session_expired", "在线会话已过期或服务已重启。请返回首页重新读取仓库。", 410)
        item.touched = now
        return item

    def result(self, session: Session) -> OnlineProject:
        architecture = build_architecture(session.id, session.name, session.text)
        architecture.limitations[0] = "仅分析内存中已读取的文本；未读取文件不计入关系分析，未执行仓库代码。"
        return OnlineProject(id=session.id, name=session.name, repository_url=session.url,
                             commit_sha=session.commit, files=[item.model_copy(update={"loaded": path in session.text})
                                                              for path, item in session.files.items()],
                             excluded_count=session.excluded_count, loaded_count=len(session.text),
                             architecture=architecture, warnings=session.warnings[-6:])

    async def open(self, url: str) -> OnlineProject:
        repository = parse_github_url(url)
        base = f"https://api.github.com/repos/{quote(repository.owner, safe='')}/{quote(repository.repo, safe='')}"
        async with self.open_lock, self.client() as client:
            metadata = await self.get_json(client, base, 256 * 1024)
            if metadata.get("private") is not False or not isinstance(metadata.get("default_branch"), str):
                fail("github_not_public", "在线浏览目前仅支持公开 GitHub 仓库。", 404)
            commit = await self.get_json(client, base + "/commits/" + quote(metadata["default_branch"], safe=''), 2 * 1024 * 1024)
            sha = commit.get("sha", "")
            if not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha):
                fail("github_invalid_commit", "无法确定仓库版本，请重试。", 502)
            # Reuse only an unexpired session for the exact immutable revision.
            now = time.monotonic()
            for key, item in list(self.sessions.items()):
                if now - item.touched > SESSION_TTL and not item.lock.locked():
                    del self.sessions[key]
                elif item.url.casefold() == repository.canonical_url.casefold() and item.commit == sha:
                    item.touched = now
                    return self.result(item)
            tree = await self.get_json(client, base + f"/git/trees/{sha}?recursive=1")
            entries = tree.get("tree")
            if tree.get("truncated") is not False or not isinstance(entries, list) or len(entries) > MAX_TREE_ENTRIES:
                fail("github_tree_incomplete", "仓库目录超过在线读取上限，未展示不完整目录。当前支持最多 20,000 个目录条目。", 413)
            files = {}
            skipped = 0
            for entry in entries:
                if not isinstance(entry, dict):
                    fail("github_invalid_tree", "GitHub 目录数据不完整。", 502)
                if entry.get("type") == "tree":
                    continue
                path = entry.get("path")
                try:
                    if not isinstance(path, str):
                        raise ValueError()
                    validate_path(path)
                except (HTTPException, ValueError):
                    skipped += 1
                    continue
                size = entry.get("size")
                blob = entry.get("sha")
                if (entry.get("type") != "blob" or entry.get("mode") not in ("100644", "100755")
                        or excluded(path) or not supported(path) or not isinstance(size, int)
                        or size < 0 or size > MAX_FILE or not isinstance(blob, str) or not SHA_PATTERN.fullmatch(blob)):
                    skipped += 1
                    continue
                files[path] = OnlineFile(path=path, size_bytes=size, sha=blob)
            if not files:
                fail("no_readable_files", "过滤后没有可读取的文本文件。", 422)
            while len(self.sessions) >= MAX_SESSIONS:
                candidates = [item for item in self.sessions.values() if not item.lock.locked()]
                if not candidates:
                    fail("online_busy", "在线分析繁忙，请稍后重试。", 503)
                oldest = min(candidates, key=lambda item: item.touched)
                del self.sessions[oldest.id]
            session = Session(uuid4(), repository.repo, repository.canonical_url, base, sha, dict(sorted(files.items())), skipped)
            self.sessions[session.id] = session
            # Directory first. File content is fetched only by explicit read requests.
            return self.result(session)

    async def load(self, session: Session, paths: list[str]) -> None:
        async with self.client() as client:
            for path in dict.fromkeys(paths):
                if path in session.text:
                    continue
                item = session.files.get(path)
                if item is None:
                    fail("file_not_found", "文件不在当前版本的可读目录中。", 404)
                total = sum(len(text.encode("utf-8")) for text in session.text.values())
                if len(session.text) >= MAX_LOADED_FILES or total + item.size_bytes > MAX_TOTAL:
                    fail("online_memory_limit", "已达到在线分析上限（120 个文件 / 8 MiB）。已读取内容仍可查看。", 413)
                blob = await self.get_json(client, session.base + "/git/blobs/" + item.sha, 2 * MAX_FILE)
                try:
                    if blob.get("encoding") != "base64" or blob.get("sha") != item.sha:
                        raise ValueError()
                    raw = base64.b64decode("".join(blob["content"].split()), validate=True)
                    # Git blob identity binds content to the tree from the pinned commit.
                    digest = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
                    if len(raw) != item.size_bytes or len(raw) > MAX_FILE or digest != item.sha:
                        raise ValueError()
                    text = raw.decode("utf-8")
                    if "\x00" in text:
                        raise ValueError()
                except (ValueError, KeyError, TypeError, AttributeError):
                    fail("github_invalid_blob", "文件不是有效的 UTF-8 文本，或与固定版本的校验值不一致。", 422)
                session.text[path] = text
                session.touched = time.monotonic()

    def candidates(self, session: Session) -> list[str]:
        # Resolve local references against the full directory without pretending unloaded files were inspected.
        available = {path: session.text.get(path, "") for path in session.files}
        imports, *_ = _imports(available)
        references = _manifest_refs(available) + _html_refs(available)
        targets = [target for _, target, _ in imports] + [ref.target for ref in references]
        remaining = sorted(session.files, key=seed_rank)
        return list(dict.fromkeys(path for path in [*targets, *remaining] if path not in session.text))[:BATCH_SIZE]

    async def read(self, session_id: UUID, paths: list[str]) -> OnlineProject:
        session = self.session(session_id)
        async with session.lock:
            requested = paths or self.candidates(session)
            # Bad user paths must fail, rather than becoming a partial-success warning.
            if any(path not in session.files for path in requested):
                fail("file_not_found", "文件不在当前版本的可读目录中。", 404)
            session.warnings.clear()
            try:
                async with asyncio.timeout(45):
                    await self.load(session, requested)
            except HTTPException as error:
                if not session.text or paths:
                    raise
                session.warnings.append(error.detail["message"])
            except TimeoutError:
                session.warnings.append("本轮读取达到时间上限，已保留完成部分；可点击继续分析。")
            return self.result(session)

    async def source(self, session_id: UUID, path: str, start: int, limit: int) -> SourceSlice:
        session = self.session(session_id)
        async with session.lock:
            await self.load(session, [path])
            text = session.text[path]
            lines = text.splitlines()
            end = min(len(lines), start + limit - 1)
            content = "\n".join(lines[start - 1:end])
            if len(content.encode()) > 64 * 1024:
                fail("source_slice_too_large", "源码片段过长，请在 GitHub 查看原文。", 413)
            return SourceSlice(path=path, sha256=hashlib.sha256(text.encode()).hexdigest(),
                               line_start=start, line_end=max(start - 1, end), total_lines=len(lines), content=content)


def routes(explorer: OnlineExplorer) -> APIRouter:
    router = APIRouter(prefix="/api/online")

    @router.post("", response_model=OnlineProject, status_code=201)
    async def open_project(body: GitHubImportRequest):
        return await explorer.open(body.repository_url)

    @router.get("/{session_id}", response_model=OnlineProject)
    async def project(session_id: UUID):
        return explorer.result(explorer.session(session_id))

    @router.post("/{session_id}/read", response_model=OnlineProject)
    async def read(session_id: UUID, body: ReadRequest):
        return await explorer.read(session_id, body.paths)

    @router.get("/{session_id}/source", response_model=SourceSlice)
    async def source(session_id: UUID, path: str, start: int = Query(1, ge=1), limit: int = Query(80, ge=1, le=200)):
        return await explorer.source(session_id, path, start, limit)

    return router
