"""Exercise the real online endpoints/parser with an offline GitHub transport."""
import base64
import hashlib
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import uvicorn
from app.config import ROOT, Settings
from app.main import create_app

FILES = {
    "README.md": "# Explorer fixture\n\nA browser application that submits a repository and shows source relationships.\n",
    "web/index.html": '<html><script type="module" src="/src/main.tsx"></script></html>',
    "web/package.json": '{"name":"explorer-fixture","scripts":{"dev":"vite"}}',
    "web/src/main.tsx": "import { App } from './App'\nexport const root = App\n",
    "web/src/App.tsx": "import { HomePage } from './pages/HomePage'\nexport const App = HomePage\n",
    "web/src/pages/HomePage.tsx": "import { submit } from '../api/projects'\nexport const HomePage = () => submit()\n",
    "web/src/api/projects.ts": "export const submit = () => fetch('/api/projects')\n",
    "server/app/main.py": "from .github_importer import read_repo\nif __name__ == '__main__':\n    read_repo('example/demo')\n",
    "server/app/github_importer.py": "from .scanner import scan\nfrom .repository import save\n\ndef read_repo(url):\n    return save(scan(url))\n",
    "server/app/scanner.py": "def scan(files):\n    return {'files': files}\n",
    "server/app/repository.py": "def save(result):\n    return result\n",
    "docs/design.md": "# Design\nStatic fixture; no real model or GitHub requests.\n",
    "extra/unread.py": "def only_on_demand():\n    return 'loaded on demand'\n",
    "extra/another.py": "def another():\n    return 2\n",
    "extra/third.py": "def third():\n    return 3\n",
}
BLOBS = {}
ENTRIES = []
for path, content in FILES.items():
    raw = content.encode()
    sha = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    BLOBS[sha] = raw
    ENTRIES.append({"path": path, "size": len(raw), "sha": sha, "type": "blob", "mode": "100644"})


def github(request):
    path = request.url.path
    if path.startswith('/repos/example/demo') and path.count('/') == 3:
        return httpx.Response(200, json={"private": False, "default_branch": "main"})
    if path.endswith('/commits/main'):
        return httpx.Response(200, json={"sha": "a" * 40})
    if '/git/trees/' in path:
        return httpx.Response(200, json={"truncated": False, "tree": ENTRIES})
    if '/git/blobs/' in path:
        sha = path.rsplit('/', 1)[-1]
        return httpx.Response(200, json={"sha": sha, "encoding": "base64", "content": base64.b64encode(BLOBS[sha]).decode()})
    return httpx.Response(404)

parent = ROOT / 'var' / 'tests'
parent.mkdir(parents=True, exist_ok=True)
with TemporaryDirectory(prefix='explorer-browser-', dir=parent) as directory:
    app = create_app(Settings(Path(directory)))
    app.state.online_explorer.transport = httpx.MockTransport(github)
    uvicorn.run(app, host='127.0.0.1', port=8001)
