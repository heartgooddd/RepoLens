"""Isolated backend for browser tests. No writes to the development database."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from app.config import ROOT, Settings
from app.main import create_app

parent = ROOT / 'var' / 'tests'
parent.mkdir(parents=True, exist_ok=True)
with TemporaryDirectory(prefix='browser-', dir=parent) as directory:
    uvicorn.run(create_app(Settings(Path(directory))), host='127.0.0.1', port=8001)
