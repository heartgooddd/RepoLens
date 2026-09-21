"""Offline, verified directory backups. Caller-owned inputs are never migrated."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unicodedata
from contextlib import closing, contextmanager
from uuid import UUID

from .config import ROOT, Settings
from .data_lease import DataLease
from .db import MIGRATIONS
from .import_policy import excluded

MAX_FILES = 100_000
MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 8 * 1024 * 1024 * 1024
MAX_MANIFEST = 32 * 1024 * 1024
DATABASE = 'repolens.sqlite3'


def relative(value):
    if not isinstance(value, str) or not value or len(value) > 1024 or '\\' in value or ':' in value or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid backup path')
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Invalid backup path')
    return path


def identifier(value):
    if str(UUID(value)) != value:
        raise ValueError('Invalid registered identifier')
    return value


def checked(root, name, *, directory=False):
    parts = relative(name).parts
    current = root
    for index, part in enumerate(parts):
        current = current / part
        info = current.lstat()
        is_directory = directory or index < len(parts) - 1
        if (is_directory and not stat.S_ISDIR(info.st_mode)) or (not is_directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)):
            raise ValueError('Backup paths must be ordinary directories and unlinked regular files')
    return current


def regular_bytes(root, name, limit=MAX_FILE):
    path = checked(root, name)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('Unsafe file or backup size limit exceeded')
        raw = stream.read(limit + 1)
        if len(raw) > limit or len(raw) != info.st_size:
            raise ValueError('File changed or backup size limit exceeded')
        return raw


def metadata(raw):
    return {'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate manifest key')
        result[key] = value
    return result


def readonly(database, *, immutable=False):
    db = sqlite3.connect(database.as_uri() + '?mode=ro' + ('&immutable=1' if immutable else ''), uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA trusted_schema=OFF')
    db.execute('PRAGMA query_only=ON')
    # Bound malformed database computations without loading extensions or running backup SQL.
    budget = [0]
    def progress():
        budget[0] += 1
        return budget[0] > 100_000
    db.set_progress_handler(progress, 1000)
    return db


def validate_database(db):
    if [tuple(r) for r in db.execute('PRAGMA integrity_check')] != [('ok',)] or list(db.execute('PRAGMA foreign_key_check')):
        raise ValueError('Database integrity or foreign key check failed')
    files = sorted(MIGRATIONS.glob('*.sql'))
    applied = list(db.execute('SELECT version,name,checksum FROM schema_migrations ORDER BY version'))
    if len(applied) != len(files):
        raise ValueError('Database schema is incompatible; upgrade the original service before backing it up')
    for index, (row, path) in enumerate(zip(applied, files), 1):
        if tuple(row) != (index, path.name, hashlib.sha256(path.read_bytes()).hexdigest()):
            raise ValueError('Database migration checksum mismatch')
    # Checksums alone do not establish that a supplied database has the trusted schema.
    with closing(sqlite3.connect(':memory:')) as expected:
        expected.execute("""CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )""")
        for path in files:
            expected.executescript(path.read_text())
        query = "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        normalize = lambda rows: [(r[0], r[1], r[2], ' '.join(r[3].split()) if r[3] else None) for r in rows]
        if normalize(db.execute(query)) != normalize(expected.execute(query)):
            raise ValueError('Database schema differs from trusted migrations')
    return len(files)


def registered(db):
    required, snapshots, runs = {}, set(), set()
    for row in db.execute('SELECT id,storage_path FROM snapshots'):
        name = f"snapshots/{identifier(row['id'])}"
        if row['storage_path'] != name:
            raise ValueError('Snapshot storage path escapes its registered directory')
        snapshots.add(name)
    for row in db.execute('SELECT * FROM snapshot_files'):
        name = f"snapshots/{identifier(row['snapshot_id'])}/{relative(row['path'])}"
        required[name] = {'size_bytes': row['size_bytes'], 'sha256': row['sha256']}
    for row in db.execute('SELECT id FROM runs'):
        runs.add(f"runs/{identifier(row['id'])}")
    for row in db.execute('SELECT * FROM artifacts'):
        name = f"runs/{identifier(row['run_id'])}/output/{relative(row['path'])}"
        required[name] = {'size_bytes': row['size_bytes'], 'sha256': row['sha256']}
    return required, snapshots, runs


def tree_files(root, name):
    directory = checked(root, name, directory=True)
    for entry in sorted(directory.iterdir()):
        child = f'{name}/{entry.name}'
        relative(child)
        if stat.S_ISDIR(entry.lstat().st_mode):
            yield from tree_files(root, child)
        else:
            checked(root, child)
            yield child


def allowed_run_file(name, runs):
    parts = relative(name).parts
    if len(parts) < 3 or '/'.join(parts[:2]) not in runs or excluded(name) or parts[-1] in ('.data.lock', '.runner.lock'):
        return False
    return (parts[2:] == ('run.log',) or parts[2:] == ('model-data', 'usage.json') or
            (len(parts) > 3 and parts[2] in ('input', 'output')))


def check_names(names):
    seen = {}
    for name in names:
        parts = relative(name).parts
        for index in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:index])
            key = unicodedata.normalize('NFC', prefix).casefold()
            if key in seen and seen[key] != prefix:
                raise ValueError('Backup paths collide by case or Unicode normalization')
            seen[key] = prefix
        if any('/'.join(parts[:i]) in names for i in range(1, len(parts))):
            raise ValueError('Backup file and directory paths conflict')


@contextmanager
def staging(destination):
    destination = Path(destination).absolute()
    if os.path.lexists(destination):
        raise ValueError('Destination already exists; use a fresh directory')
    if not destination.parent.is_dir():
        raise ValueError('Destination parent must exist')
    stage = Path(tempfile.mkdtemp(prefix=f'.{destination.name}.staging-', dir=destination.parent))
    try:
        yield stage
        # Exclusive rename is atomic and also refuses an empty target created during validation.
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == 'darwin':
            rename = libc.renamex_np
            rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            result = rename(os.fsencode(stage), os.fsencode(destination), 4)  # RENAME_EXCL
        elif sys.platform.startswith('linux'):
            rename = libc.renameat2
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            result = rename(-100, os.fsencode(stage), -100, os.fsencode(destination), 1)  # RENAME_NOREPLACE
        else:
            raise ValueError('Atomic exclusive restore is supported on macOS and Linux only')
        if result:
            raise OSError(ctypes.get_errno(), 'Cannot publish backup to destination')
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def put(stage, name, raw):
    target = stage / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(raw)


def create(settings, destination):
    root = settings.data_dir
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Source data directory does not exist or is a symlink')
    if os.path.lexists(root / 'runs'):
        checked(root, 'runs', directory=True)
    with DataLease(root), DataLease(root / 'runs', '.runner.lock'):
        if checked(root, DATABASE).stat().st_size > MAX_FILE:
            raise ValueError('Database exceeds backup file size limit')
        for suffix in ('-wal', '-shm', '-journal'):
            if os.path.lexists(root / (DATABASE + suffix)):
                checked(root, DATABASE + suffix)
        with closing(readonly(root / DATABASE)) as source:
            validate_database(source)
            with staging(destination) as stage:
                with closing(sqlite3.connect(stage / DATABASE)) as target:
                    source.backup(target)
                    target.execute('PRAGMA journal_mode=DELETE')
                with closing(readonly(stage / DATABASE, immutable=True)) as db:
                    version = validate_database(db)
                    required, snapshots, runs = registered(db)
                names = set(required)
                for directory in snapshots:
                    checked(root, directory, directory=True)
                for directory in runs:
                    if not os.path.lexists(root / directory):
                        continue  # Historical failed runs may have no output directory.
                    checked(root, directory, directory=True)
                    for suffix in ('run.log', 'input', 'output', 'model-data/usage.json'):
                        name = f'{directory}/{suffix}'
                        if not os.path.lexists(root / name):
                            continue
                        if suffix in ('input', 'output'):
                            names.update(item for item in tree_files(root, name) if allowed_run_file(item, runs))
                        else:
                            checked(root, name)
                            names.add(name)
                check_names(names | {DATABASE})
                if len(names) + 1 > MAX_FILES:
                    raise ValueError('Too many backup files')
                records = {DATABASE: metadata(regular_bytes(stage, DATABASE))}
                total = records[DATABASE]['size_bytes']
                for name in sorted(names):
                    if excluded(name) or PurePosixPath(name).name in ('.data.lock', '.runner.lock'):
                        raise ValueError('A registered file has a reserved or credential filename')
                    raw = regular_bytes(root, name)
                    record = metadata(raw)
                    if name in required and required[name] != record:
                        raise ValueError('Registered snapshot or artifact hash mismatch')
                    total += len(raw)
                    if total > MAX_TOTAL:
                        raise ValueError('Backup total size limit exceeded')
                    put(stage, name, raw)
                    records[name] = record
                commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
                manifest = {'format_version': 1, 'schema_version': version, 'code_commit': commit, 'files': records}
                put(stage, 'manifest.json', json.dumps(manifest, indent=2, sort_keys=True).encode())
                validate_backup(stage)


def validate_backup(root):
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Backup must be an ordinary directory')
    manifest = json.loads(regular_bytes(root, 'manifest.json', MAX_MANIFEST), object_pairs_hook=unique_object)
    if not isinstance(manifest, dict) or manifest.get('format_version') != 1 or not re.fullmatch(r'[0-9a-f]{40,64}', str(manifest.get('code_commit', ''))):
        raise ValueError('Unsupported or invalid backup manifest')
    records = manifest.get('files')
    if not isinstance(records, dict) or DATABASE not in records or len(records) > MAX_FILES:
        raise ValueError('Invalid backup file inventory')
    check_names(set(records))
    total = 0
    for name, record in records.items():
        if not isinstance(record, dict) or type(record.get('size_bytes')) is not int or not 0 <= record['size_bytes'] <= MAX_FILE or not re.fullmatch(r'[0-9a-f]{64}', str(record.get('sha256', ''))):
            raise ValueError('Invalid backup file metadata')
        total += record['size_bytes']
        if total > MAX_TOTAL:
            raise ValueError('Backup total size limit exceeded')
        if metadata(regular_bytes(root, name)) != record:
            raise ValueError('Backup file hash mismatch')
    actual = set()
    for entry in root.iterdir():
        if stat.S_ISDIR(entry.lstat().st_mode):
            actual.update(tree_files(root, entry.name))
        else:
            checked(root, entry.name)
            actual.add(entry.name)
    if actual != set(records) | {'manifest.json'}:
        raise ValueError('Backup contains unregistered files')
    with closing(readonly(root / DATABASE, immutable=True)) as db:
        if validate_database(db) != manifest.get('schema_version'):
            raise ValueError('Backup schema version mismatch')
        required, _, runs = registered(db)
    if any(records.get(name) != record for name, record in required.items()):
        raise ValueError('Backup is missing a registered snapshot or artifact, or its hash changed')
    if any(name != DATABASE and (excluded(name) or PurePosixPath(name).name in ('.data.lock', '.runner.lock') or
           (name not in required and not allowed_run_file(name, runs))) for name in records):
        raise ValueError('Backup file is outside registered data')
    return records


def restore(backup, destination):
    backup = Path(backup).absolute()
    records = validate_backup(backup)
    with staging(destination) as stage:
        for name, record in records.items():
            raw = regular_bytes(backup, name)
            if metadata(raw) != record:
                raise ValueError('Backup changed during restore')
            put(stage, name, raw)
        # Validate the copied set again before it becomes visible; no migrations run here.
        put(stage, 'manifest.json', regular_bytes(backup, 'manifest.json', MAX_MANIFEST))
        validate_backup(stage)
        (stage / 'manifest.json').unlink()
        (stage / 'snapshots').mkdir(exist_ok=True)
        (stage / 'runs').mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create_parser = commands.add_parser('create')
    create_parser.add_argument('destination', type=Path)
    restore_parser = commands.add_parser('restore')
    restore_parser.add_argument('backup', type=Path)
    restore_parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'create':
            create(Settings.from_env(), args.destination)
        else:
            restore(args.backup, args.destination)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        parser.exit(1, f'备份／恢复已拒绝，目标未发布：{exc}\n')
    print(f'{"备份" if args.command == "create" else "恢复"}完成：{args.destination}')


if __name__ == '__main__':
    main()
