"""Copy validated text into independent snapshots; commit metadata only after files exist."""

import base64
import binascii
import hashlib
import shutil
import subprocess
import unicodedata
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Literal
from uuid import uuid4

from pydantic import Field

from .config import ROOT, Settings
from .import_policy import MAX_FILE, MAX_FILES, MAX_TOTAL, excluded, fail, supported, validate_path
from .models import Project, ProjectDetail, Record, Snapshot, SnapshotFile
from .repository import create_project
from .scanner import scan

BUILTIN = ROOT / "upstream" / "pocketflow-codebase-knowledge"


class UploadFile(Record):
    path: str
    content_base64: str


class ImportRequest(Record):
    source: Literal["builtin", "upload"]
    name: str = Field(default="本地项目", min_length=1, max_length=200)
    files: list[UploadFile] = Field(default_factory=list, max_length=MAX_FILES)


class ImportResult(Record):
    detail: ProjectDetail
    skipped_count: int
    note: str


def git(*args: str) -> bytes:
    try:
        return subprocess.run(["git", "-C", str(BUILTIN), *args], check=True, capture_output=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        fail("sample_unavailable", "PocketFlow 本地 Git 样本不可读，请检查 upstream 下载是否完整。", 503)


def import_project(settings: Settings, request: ImportRequest) -> ImportResult:
    candidates: list[tuple[str, bytes]] = []
    skipped = 0
    commit = None
    if request.source == "builtin":
        if request.files:
            fail("invalid_request", "内置样本不接受上传文件。")
        commit = git("rev-parse", "HEAD").decode().strip()
        entries = git("ls-tree", "-rlz", commit).split(b"\0")
        for entry in entries:
            if not entry:
                continue
            meta, raw_path = entry.split(b"\t", 1)
            mode, kind, oid, size = meta.split()
            try:
                path = raw_path.decode("utf-8")
            except UnicodeDecodeError:
                fail("invalid_path", "样本包含非 UTF-8 文件名。")
            validate_path(path)
            # Read committed regular blobs, never links, submodules or the working tree.
            if mode not in (b"100644", b"100755") or excluded(path) or not supported(path):
                skipped += 1
                continue
            if int(size) > MAX_FILE:
                fail("file_too_large", "单文件超过 1 MiB 限制。", 413)
            candidates.append((path, git("cat-file", "blob", oid.decode())))
            if len(candidates) > MAX_FILES or sum(len(raw) for _, raw in candidates) > MAX_TOTAL:
                fail("project_too_large", "项目超过 500 个文件或 8 MiB 限制。", 413)
    else:
        for file in request.files:
            validate_path(file.path)
            if excluded(file.path) or not supported(file.path):
                skipped += 1
                continue
            if len(file.content_base64) > ((MAX_FILE + 2) // 3) * 4:
                fail("file_too_large", "单文件超过 1 MiB 限制。", 413)
            try:
                raw = base64.b64decode(file.content_base64, validate=True)
            except (ValueError, binascii.Error):
                fail("invalid_encoding", "文件内容必须使用合法 Base64 编码。")
            candidates.append((file.path, raw))

    files: dict[str, bytes] = {}
    normalized = set()
    total = 0
    for path, raw in candidates:
        key = unicodedata.normalize("NFC", path).casefold()
        if key in normalized:
            fail("duplicate_path", "文件路径重复或在本机文件系统上存在大小写冲突。")
        normalized.add(key)
        if len(raw) > MAX_FILE:
            fail("file_too_large", "单文件超过 1 MiB 限制。", 413)
        total += len(raw)
        if total > MAX_TOTAL:
            fail("project_too_large", "项目总内容超过 8 MiB 限制。", 413)
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            skipped += 1
            continue
        if b"\0" in raw:
            skipped += 1
            continue
        files[path] = raw
    if not files:
        fail("empty_directory", "目录为空，或过滤后没有可扫描的 UTF-8 文本文件。")
    # Reject file/directory aliases before touching disk (macOS is usually case insensitive).
    directories = {unicodedata.normalize("NFC", str(p)).casefold() for path in files for p in PurePosixPath(path).parents if str(p) != "."}
    if normalized & directories:
        fail("path_conflict", "同一路径不能同时用作文件和目录。")
    if len(directories) > 500:
        fail("project_too_large", "项目目录数量超过 500 个限制。", 413)

    project_id, snapshot_id = uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    digest = hashlib.sha256()
    for path, raw in sorted(files.items()):
        digest.update(path.encode() + b"\0" + hashlib.sha256(raw).digest())
    revision = "sha256:" + digest.hexdigest()
    snapshot = Snapshot(id=snapshot_id, project_id=project_id, revision=revision, commit_sha=commit,
                        storage_path=f"snapshots/{snapshot_id}", created_at=now,
                        files=[SnapshotFile(path=p, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()) for p, raw in sorted(files.items())],
                        folder_cards=scan(files, snapshot_id))
    detail = ProjectDetail(project=Project(id=project_id, name="PocketFlow" if commit else request.name.strip() or "本地项目",
                           source_type="builtin" if commit else "local_upload", source_label="PocketFlow 已提交版本" if commit else "浏览器目录上传",
                           created_at=now, updated_at=now), snapshots=[snapshot])
    destination = settings.data_dir / snapshot.storage_path
    destination.mkdir(exist_ok=False)
    try:
        for path, raw in files.items():
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(raw)
        create_project(settings.database, detail)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return ImportResult(detail=detail, skipped_count=skipped,
                        note="已保存过滤后的源码快照；仅静态扫描，未执行项目或调用模型。" + (" 内置样本读取 Git HEAD 已提交版本，不含未提交修改。" if commit else ""))
