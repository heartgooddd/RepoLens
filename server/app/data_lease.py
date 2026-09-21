"""One persistent advisory lock covers every owner of a local data directory."""
import fcntl
import os
import stat
from pathlib import Path


class DataLease:
    def __init__(self, data_dir: Path, filename: str = '.data.lock'):
        self.path = Path(data_dir) / filename
        self.fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise RuntimeError('数据目录锁文件不安全，已拒绝操作。')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as exc:
            os.close(fd)
            if isinstance(exc, BlockingIOError):
                raise RuntimeError('RepoLens 数据目录正在使用，请先停止后台服务再继续。') from None
            raise
        self.fd = fd
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        # Never unlink: waiters and future owners must lock the same inode.
