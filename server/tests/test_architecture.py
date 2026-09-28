import base64
from uuid import uuid4

from fastapi.testclient import TestClient

from app.architecture import build_architecture
from app.main import create_app


def test_architecture_extracts_readme_imports_and_folder_roles():
    files = {
        "README.md": "# Example\n\nA small app that renders a card from source data.\n",
        "package.json": '{"description":"Fallback only","main":"src/app.ts","scripts":{"start":"node src/app.ts"}}',
        "src/app.ts": "import { Card } from './components/Card'\nexport const app = Card\n",
        "src/components/Card.tsx": "export const Card = () => <p>Ready</p>\n",
        "docs/design.md": "# Design\n",
    }
    result = build_architecture(uuid4(), "Example", files)
    assert result.project_name == "Example"
    assert result.summary == "A small app that renders a card from source data."
    assert result.summary_source.file_path == "README.md"
    assert result.coverage.retained_files == 5
    assert result.coverage.inspected_source_files == 2
    assert result.coverage.resolved_imports == 1
    assert result.coverage.unresolved_local_imports == 0
    modules = {module.id: module for module in result.modules}
    assert modules["file:src/app.ts"].kind == "entry"
    assert modules["folder:src/components"].kind == "interface"
    assert modules["folder:src/components"].confidence == "inferred"
    assert modules["folder:docs"].kind == "docs"
    imports = [edge for edge in result.connections if edge.kind == "imports"]
    assert len(imports) == 1
    assert (imports[0].from_id, imports[0].to_id) == ("file:src/app.ts", "file:src/components/Card.tsx")
    assert imports[0].evidence[0].file_path == "src/app.ts"
    assert imports[0].evidence[0].line_start == 1
    assert any(edge.kind == "references" and edge.to_id == "file:src/app.ts" for edge in result.connections)
    assert any(edge.kind == "contains" and edge.from_id == "folder:src" and edge.to_id == "folder:src/components"
               for edge in result.connections)


def test_python_imports_are_dependencies_not_execution_flow():
    files = {
        "README.md": "# Sample\n\nReads an input and produces a report.\n",
        "main.py": "from flow import build_flow\n\nif __name__ == '__main__':\n    build_flow()\n",
        "flow.py": "from nodes import Worker\n\ndef build_flow():\n    return Worker()\n",
        "nodes.py": "from utils.text import clean\n\nclass Worker:\n    pass\n",
        "utils/text.py": "def clean(value):\n    return value.strip()\n",
    }
    result = build_architecture(uuid4(), "Sample", files)
    pairs = {(edge.from_id, edge.to_id) for edge in result.connections if edge.kind == "imports"}
    assert pairs == {
        ("file:main.py", "file:flow.py"),
        ("file:flow.py", "file:nodes.py"),
        ("file:nodes.py", "file:utils/text.py"),
    }
    assert next(module for module in result.modules if module.id == "file:main.py").kind == "entry"
    assert "不能单独证明运行顺序" in " ".join(result.limitations)


def test_nested_web_manifest_and_html_module_identify_real_frontend_entry():
    files = {
        "README.md": "# Studio\n\nA small workspace for visual source exploration.\n",
        "web/package.json": '{"module":"./src/library.ts","scripts":{"build":"vite --config vite.config.ts"}}',
        "web/index.html": (
            "<!doctype html>\n<html><body>\n"
            "<!-- <script type='module' src='/src/ghost.ts'></script> -->\n"
            "<script type='module'\n"
            "  src='/src/main.tsx?v=1'></script>\n"
            "<script src='/src/legacy.js'></script>\n"
            "<script type='module' src='https://example.com/remote.ts'></script>\n"
            "<script type='module' src='../../evil.ts'></script>\n"
            "</body></html>\n"
        ),
        "web/src/main.tsx": "import { App } from './App'\nimport helper from '@/shared/helper'\nexport const root = App\n",
        "web/src/App.tsx": "export const App = () => <main>Ready</main>\n",
        "web/src/library.ts": "export const library = true\n",
        "web/src/ghost.ts": "export const ghost = true\n",
        "web/src/legacy.js": "console.log('legacy')\n",
        "web/vite.config.ts": "export default {}\n",
        "web/app/page.tsx": "export const Page = () => <p>Ready</p>\n",
        "evil.ts": "export const ignored = true\n",
    }
    result = build_architecture(uuid4(), "Studio", files)
    modules = {module.id: module for module in result.modules}
    assert modules["folder:web/src"].kind == "interface"
    assert modules["folder:web/app"].kind == "interface"
    assert modules["file:web/src/main.tsx"].kind == "entry"
    assert modules["file:web/src/main.tsx"].confidence == "observed"
    assert modules["file:web/src/main.tsx"].evidence[0].file_path == "web/index.html"
    assert modules["file:web/src/main.tsx"].evidence[0].line_start == 5
    assert modules["file:web/src/library.ts"].kind == "entry"
    assert modules["file:web/vite.config.ts"].kind == "support"
    assert not any(module.id == "file:web/src/legacy.js" and module.kind == "entry" for module in result.modules)
    assert "file:web/src/ghost.ts" not in modules
    assert "file:evil.ts" in modules and modules["file:evil.ts"].kind != "entry"
    references = {(edge.from_id, edge.to_id, edge.label): edge for edge in result.connections
                  if edge.kind == "references"}
    html_edge = references[("file:web/index.html", "file:web/src/main.tsx", "HTML 模块脚本入口")]
    assert html_edge.evidence[0].file_path == "web/index.html"
    assert html_edge.evidence[0].line_start == 5
    assert "src='/src/main.tsx?v=1'" in html_edge.evidence[0].excerpt
    assert ("file:web/package.json", "file:web/src/library.ts", "清单声明的入口") in references
    assert ("file:web/package.json", "file:web/vite.config.ts", "清单脚本引用") in references
    assert not any(edge.to_id in {"file:web/src/ghost.ts", "file:web/src/legacy.js", "file:evil.ts"}
                   for edge in result.connections if edge.kind == "references")
    assert result.coverage.resolved_imports == 1
    assert "1 个看似路径别名的导入" in " ".join(result.limitations)


def test_short_readme_tagline_prefers_source_backed_workflow_description():
    files = {
        "README.md": (
            "# RepoLens\n\n开源 AI 项目拆解与学习平台工作区。\n\n"
            "安装依赖并双击脚本即可启动本地开发环境。\n\n"
            "用户输入公开 GitHub 仓库地址，页面分析项目源码和目录，生成可视化地图并展示模块作用。\n\n"
            "1. 输入项目地址，导入 GitHub 仓库源码，选择目录和模块，生成教程、报告与可视化地图。\n"
            "2. 点击文件夹继续阅读项目结构、源码与页面。\n"
        ),
    }
    result = build_architecture(uuid4(), "RepoLens", files)
    assert result.summary.startswith("用户输入公开 GitHub 仓库地址")
    assert result.summary_source.file_path == "README.md"
    assert result.summary_source.line_start == 7
    assert result.summary_source.excerpt == files["README.md"].splitlines()[6]


def test_architecture_api_uses_registered_hash_verified_snapshot(settings):
    with TestClient(create_app(settings)) as client:
        missing = client.get(f"/api/snapshots/{uuid4()}/architecture")
        assert missing.status_code == 404
        payload = {
            "source": "upload", "name": "Mini app",
            "files": [
                {"path": path, "content_base64": base64.b64encode(text.encode()).decode()}
                for path, text in {
                    "README.md": "# Mini app\n\nA small test project for architecture mapping.\n",
                    "main.py": "from helpers.format import render\nprint(render('hi'))\n",
                    "helpers/format.py": "def render(text):\n    return text.upper()\n",
                }.items()
            ],
        }
        imported = client.post("/api/projects/import", json=payload)
        assert imported.status_code == 201
        snapshot = imported.json()["detail"]["snapshots"][0]
        response = client.get(f"/api/snapshots/{snapshot['id']}/architecture")
        assert response.status_code == 200
        result = response.json()
        assert result["project_name"] == "Mini app"
        assert result["coverage"]["retained_files"] == 3
        assert any(edge["kind"] == "imports" and edge["to_id"] == "file:helpers/format.py"
                   for edge in result["connections"])
        target = settings.data_dir / snapshot["storage_path"] / "helpers/format.py"
        target.write_text("changed")
        changed = client.get(f"/api/snapshots/{snapshot['id']}/architecture")
        assert changed.status_code == 409
        assert changed.json()["detail"]["code"] == "snapshot_changed"
