"""Serve bounded, hash-verified source slices from registered snapshot files."""

import hashlib

from .config import Settings
from .db import connect
from .import_policy import MAX_FILE, fail, validate_path
from .models import Record


class SourceSlice(Record):
    path: str
    sha256: str
    line_start: int
    line_end: int
    total_lines: int
    content: str


def read_source(settings: Settings, snapshot_id: str, path: str, start: int, limit: int) -> SourceSlice:
    validate_path(path)
    with connect(settings.database) as db:
        row = db.execute("SELECT sha256 FROM snapshot_files WHERE snapshot_id = ? AND path = ?", (snapshot_id, path)).fetchone()
    if row is None:
        fail("file_not_found", "此文件不在已保存的快照中。", 404)
    base = settings.data_dir / "snapshots" / snapshot_id
    target = base / path
    try:
        if any(p.is_symlink() for p in [target, *target.parents] if p != settings.data_dir.parent):
            fail("snapshot_changed", "快照路径已变化，请重新导入。", 409)
        if not target.resolve().is_relative_to(base.resolve()):
            fail("invalid_path", "路径超出快照范围。")
        with target.open("rb") as stream:
            raw = stream.read(MAX_FILE + 1)
    except OSError:
        fail("snapshot_missing", "快照文件已丢失，请重新导入。", 409)
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        fail("snapshot_changed", "快照文件与保存的校验值不一致，请重新导入。", 409)
    lines = raw.decode("utf-8").splitlines()
    end = min(len(lines), start + limit - 1)
    content = "\n".join(lines[start - 1:end])
    if len(content.encode()) > 64 * 1024:
        fail("source_slice_too_large", "该源码片段过长，请缩小行数范围。", 413)
    return SourceSlice(path=path, sha256=row["sha256"], line_start=start, line_end=max(start - 1, end), total_lines=len(lines), content=content)
