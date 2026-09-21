"""Resolve data locations independently of the terminal's working directory."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    real_enabled: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        path = Path(os.environ.get("REPOLENS_DATA_DIR", str(ROOT / "var"))).expanduser()
        if not path.is_absolute():
            raise ValueError("REPOLENS_DATA_DIR must be an absolute path")
        return cls(path.resolve(), real_enabled=os.environ.get('REPOLENS_ENABLE_REAL_RUN') == '1')

    @property
    def database(self) -> Path:
        return self.data_dir / "repolens.sqlite3"

    def prepare(self) -> None:
        for path in (self.data_dir, self.data_dir / "snapshots", self.data_dir / "runs"):
            path.mkdir(parents=True, exist_ok=True)
