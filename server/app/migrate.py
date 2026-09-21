"""Run from server/: .venv/bin/python -m app.migrate"""

from .config import Settings
from .db import migrate


def main() -> None:
    settings = Settings.from_env()
    settings.prepare()
    version = migrate(settings.database)
    print(f"Schema version: {version}; database: {settings.database}")


if __name__ == "__main__":
    main()
