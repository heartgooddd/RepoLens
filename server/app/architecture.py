"""Evidence-backed architecture map for an immutable text snapshot.

This is a static map. An import is a source dependency, never a claim about
execution order, runtime calls, or the behavior of an unexecuted repository.
"""

import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Literal, NamedTuple
from uuid import UUID

from pydantic import Field

from .config import Settings
from .db import connect
from .import_policy import MAX_FILE, fail, validate_path
from .models import Record, RelativePath


ModuleKind = Literal["entry", "interface", "core", "data", "support", "docs", "tests", "other"]


class ArchitectureEvidence(Record):
    file_path: RelativePath
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    excerpt: str


class ArchitectureModule(Record):
    id: str
    title: str
    role: str
    kind: ModuleKind
    paths: list[RelativePath]
    evidence: list[ArchitectureEvidence]
    confidence: Literal["observed", "inferred", "unknown"]
    file_count: int


class ArchitectureConnection(Record):
    from_id: str
    to_id: str
    kind: Literal["imports", "contains", "references"]
    label: str
    evidence: list[ArchitectureEvidence]


class ArchitectureCoverage(Record):
    retained_files: int
    inspected_source_files: int
    folders: int
    resolved_imports: int
    unresolved_local_imports: int


class ArchitectureMap(Record):
    snapshot_id: UUID
    project_name: str
    summary: str
    summary_source: ArchitectureEvidence | None
    modules: list[ArchitectureModule]
    connections: list[ArchitectureConnection]
    coverage: ArchitectureCoverage
    limitations: list[str]


SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx"}
JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")
MANIFEST_NAMES = {"package.json", "pyproject.toml", "setup.py", "dockerfile", "makefile"}
FOLDER_KINDS: dict[str, ModuleKind] = {
    "components": "interface", "pages": "interface", "views": "interface", "ui": "interface",
    "routes": "interface", "api": "interface", "frontend": "interface", "web": "interface",
    "client": "interface", "server": "core", "backend": "core", "app": "core",
    "core": "core", "domain": "core", "services": "core", "src": "core",
    "models": "data", "db": "data", "database": "data", "storage": "data",
    "utils": "support", "helpers": "support", "lib": "support", "scripts": "support",
    "config": "support", "configs": "support", "docs": "docs", "doc": "docs",
    "test": "tests", "tests": "tests", "__tests__": "tests",
}
KIND_TITLES = {
    "entry": "启动入口", "interface": "界面或接口", "core": "核心源码", "data": "数据与存储",
    "support": "辅助与配置", "docs": "说明文档", "tests": "测试", "other": "项目内容",
}
JS_IMPORT = re.compile(r"^\s*(?:import|export)\s+(?:[^;]*?\s+from\s+)?['\"]([^'\"]+)['\"]")
JS_REQUIRE = re.compile(r"\b(?:require|import)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")


class _Reference(NamedTuple):
    source: str
    target: str
    evidence: ArchitectureEvidence
    label: str
    entry: bool


def _evidence(path: str, line: int, text: str) -> ArchitectureEvidence:
    return ArchitectureEvidence(file_path=path, line_start=line, line_end=line, excerpt=text[:240])


def _summary(files: dict[str, str]) -> tuple[str, ArchitectureEvidence | None]:
    readme = next((path for path in ("README.md", "README.rst", "README.txt", "README") if path in files), None)
    if readme:
        lines = files[readme].splitlines()
        candidates: list[tuple[int, str, ArchitectureEvidence]] = []
        fenced = False
        for index, line in enumerate(lines[:120]):
            content = line.strip()
            if content.startswith("```"):
                fenced = not fenced
            if fenced:
                continue
            if (len(content) < 12 or content.startswith(("#", "!", "[!", "<", "```", "---", "*", "- "))
                    or re.match(r"^\d{1,2}[.)]\s", content)
                    or re.fullmatch(r"[=~`-]+", content)):
                continue
            paragraph = [content]
            for next_line in lines[index + 1:index + 5]:
                if (not next_line.strip() or next_line.lstrip().startswith(("#", "```", "- "))
                        or re.match(r"^\d{1,2}[.)]\s", next_line.lstrip())):
                    break
                paragraph.append(next_line.strip())
            value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", " ".join(paragraph))
            value = re.sub(r"[`*_]", "", value).strip()
            if len(value) >= 12:
                evidence = ArchitectureEvidence(
                    file_path=readme, line_start=index + 1, line_end=index + len(paragraph),
                    excerpt="\n".join(paragraph)[:300],
                )
                candidates.append((index, value, evidence))
        if candidates:
            first = candidates[0]
            choice = first
            # A short tagline often names the product without saying what a user
            # supplies or receives. Prefer a nearby, source-backed workflow paragraph.
            if len(first[1]) < 55:
                def score(candidate: tuple[int, str, ArchitectureEvidence]) -> int:
                    index, value, _ = candidate
                    input_words = ("输入", "GitHub", "仓库地址", "导入", "上传")
                    output_words = ("输出", "生成", "展示", "可视化", "地图", "报告", "教程")
                    structure_words = ("项目", "源码", "文件夹", "目录", "模块", "结构", "体系", "代码", "快照")
                    groups = (input_words, output_words, structure_words)
                    if not all(any(word in value for word in group) for group in groups):
                        return -1
                    terms = sum(word in value for group in groups for word in group)
                    setup = any(word in value for word in ("安装", "双击", "环境变量", "运行命令"))
                    return terms * 2 + 2 - index // 10 - (8 if setup else 0)
                stronger = max(candidates[:20], key=score)
                if score(stronger) >= 7:
                    choice = stronger
            description = choice[1]
            if choice is not first:
                sentences = re.split(r"(?<=[。!?])\s*", description)
                description = next((sentence for sentence in sentences
                                    if 20 <= len(sentence) <= 220
                                    and any(word in sentence for word in ("输入", "GitHub", "导入", "上传"))
                                    and any(word in sentence for word in ("生成", "展示", "地图", "报告", "教程", "预览"))),
                                   description)
            return description[:300], choice[2]
    manifest = files.get("package.json")
    if manifest:
        try:
            description = json.loads(manifest).get("description")
            if isinstance(description, str) and description.strip():
                line = next((i for i, text in enumerate(manifest.splitlines(), 1) if '"description"' in text), 1)
                return description.strip()[:300], _evidence("package.json", line, manifest.splitlines()[line - 1])
        except (ValueError, TypeError, AttributeError):
            pass
    return "仓库没有可核对的项目简介；下面仅展示保留源码的结构与静态依赖。", None


def _resolve_python(path: str, module: str, level: int, symbol: str | None, files: set[str]) -> str | None:
    parent = PurePosixPath(path).parent
    prefix = [] if str(parent) == "." else list(parent.parts)
    if level:
        if level - 1 > len(prefix):
            return None
        prefix = prefix[:len(prefix) - level + 1]
    else:
        prefix = []
    parts = prefix + ([part for part in module.split(".") if part] if module else [])
    candidate_parts = ([parts + [symbol]] if symbol and symbol != "*" else []) + [parts]
    for item in candidate_parts:
        if not item:
            continue
        base = "/".join(item)
        for candidate in (f"{base}.py", f"{base}/__init__.py"):
            if candidate in files:
                return candidate
    return None


def _resolve_js(path: str, target: str, files: set[str]) -> str | None:
    if not target.startswith("."):
        return None
    parts = list(PurePosixPath(path).parent.parts)
    if parts == ["."]:
        parts = []
    for part in target.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    base = "/".join(parts)
    candidates = [base]
    if PurePosixPath(base).suffix in (".js", ".jsx"):
        candidates += [base.rsplit(".", 1)[0] + suffix for suffix in (".ts", ".tsx")]
    candidates += [base + suffix for suffix in JS_SUFFIXES]
    candidates += [base + "/index" + suffix for suffix in JS_SUFFIXES]
    return next((candidate for candidate in candidates if candidate in files), None)


def _imports(files: dict[str, str]) -> tuple[list[tuple[str, str, ArchitectureEvidence]], int, int, int, int]:
    found: list[tuple[str, str, ArchitectureEvidence]] = []
    paths = set(files)
    inspected = unresolved = alias_candidates = 0
    for path, text in files.items():
        suffix = PurePosixPath(path).suffix.lower()
        if suffix not in SOURCE_SUFFIXES:
            continue
        inspected += 1
        lines = text.splitlines()
        if suffix == ".py":
            try:
                tree = ast.parse(text)
            except (SyntaxError, ValueError, RecursionError):
                continue
            for node in ast.walk(tree):
                line = getattr(node, "lineno", None)
                if not line or line > len(lines):
                    continue
                targets: list[tuple[str, int, str | None]] = []
                if isinstance(node, ast.Import):
                    targets = [(alias.name, 0, None) for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    targets = [(node.module or "", node.level, alias.name) for alias in node.names]
                for module, level, symbol in targets:
                    target = _resolve_python(path, module, level, symbol, paths)
                    if target and target != path:
                        found.append((path, target, _evidence(path, line, lines[line - 1])))
                    elif level:
                        unresolved += 1
        else:
            for line, content in enumerate(lines, 1):
                specifiers = []
                match = JS_IMPORT.search(content)
                if match:
                    specifiers.append(match.group(1))
                specifiers.extend(JS_REQUIRE.findall(content))
                for specifier in specifiers:
                    if not specifier.startswith("."):
                        if specifier.startswith(("@/", "~/", "#/")):
                            alias_candidates += 1
                        continue
                    target = _resolve_js(path, specifier, paths)
                    if target and target != path:
                        found.append((path, target, _evidence(path, line, content)))
                    else:
                        unresolved += 1
    return found, inspected, len(found), unresolved, alias_candidates


def _reference_target(source: str, value: str, files: dict[str, str], *, web_root: bool = False) -> str | None:
    """Resolve a literal local reference against retained paths, without fetching it."""
    value = value.split("?", 1)[0].split("#", 1)[0].strip()
    if not value or value.startswith("//") or "\\" in value or re.match(r"^[A-Za-z][\w+.-]*:", value):
        return None
    parent = PurePosixPath(source).parent
    if web_root and value.startswith("/"):
        # A Vite-style /src/main.tsx is relative to its package's web root.
        # Without a package manifest, the HTML directory is the only observed root.
        parent = next((folder for folder in (parent, *parent.parents)
                       if str(folder / "package.json") in files), parent)
    parts = [] if str(parent) == "." else list(parent.parts)
    for part in value.lstrip("/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    target = "/".join(parts)
    return target if target in files else None


def _manifest_refs(files: dict[str, str]) -> list[_Reference]:
    result: list[_Reference] = []
    for path in sorted(files):
        if PurePosixPath(path).name != "package.json":
            continue
        try:
            package = json.loads(files[path])
        except (ValueError, TypeError):
            continue
        if not isinstance(package, dict):
            continue
        lines = files[path].splitlines()
        for key in ("main", "module", "browser"):
            value = package.get(key)
            if not isinstance(value, str):
                continue
            target = _reference_target(path, value, files)
            if target:
                line = next((i for i, text in enumerate(lines, 1) if f'"{key}"' in text and value in text), 1)
                result.append(_Reference(path, target, _evidence(path, line, lines[line - 1]),
                                         "清单声明的入口", True))
        scripts = package.get("scripts")
        if isinstance(scripts, dict):
            for value in scripts.values():
                if not isinstance(value, str):
                    continue
                for literal in sorted(set(re.findall(r"(?:\./|\.\./)?[\w./-]+\.(?:js|jsx|ts|tsx|py)\b", value))):
                    target = _reference_target(path, literal, files)
                    if target:
                        line = next((i for i, text in enumerate(lines, 1) if literal in text), 1)
                        result.append(_Reference(path, target, _evidence(path, line, lines[line - 1]),
                                                 "清单脚本引用", False))
    return result


class _ModuleScripts(HTMLParser):
    def __init__(self, path: str, text: str, files: dict[str, str]):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.lines = text.splitlines()
        self.files = files
        self.references: list[_Reference] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attributes = dict(attrs)
        if (attributes.get("type") or "").lower() != "module" or not attributes.get("src"):
            return
        target = _reference_target(self.path, attributes["src"], self.files, web_root=True)
        if target:
            raw = self.get_starttag_text() or ""
            src = re.search(r"\bsrc\s*=", raw, re.I)
            line = self.getpos()[0] + (raw[:src.start()].count("\n") if src else 0)
            self.references.append(_Reference(self.path, target, _evidence(self.path, line, self.lines[line - 1]),
                                              "HTML 模块脚本入口", True))


def _html_refs(files: dict[str, str]) -> list[_Reference]:
    result: list[_Reference] = []
    for path in sorted(files):
        if PurePosixPath(path).suffix.lower() != ".html":
            continue
        parser = _ModuleScripts(path, files[path], files)
        parser.feed(files[path])
        result.extend(parser.references)
    return result


def _kind(path: str, is_folder: bool, *, entry: bool = False) -> tuple[ModuleKind, str]:
    if entry:
        return "entry", "observed"
    name = PurePosixPath(path).name.lower()
    if is_folder and name in {"src", "app"} and any(
        part.lower() in {"web", "frontend", "client"} for part in PurePosixPath(path).parts[:-1]
    ):
        return "interface", "inferred"
    if is_folder and name in FOLDER_KINDS:
        return FOLDER_KINDS[name], "inferred"
    if is_folder:
        return "other", "unknown"
    if name.startswith("readme") or PurePosixPath(path).suffix.lower() in {".md", ".rst"}:
        return "docs", "observed"
    if name in MANIFEST_NAMES or name.endswith((".config.js", ".config.ts", ".config.json")):
        return "support", "observed"
    if name.startswith("test_") or name.endswith((".test.ts", ".spec.ts", "_test.py")):
        return "tests", "inferred"
    if PurePosixPath(path).suffix.lower() in {".tsx", ".jsx", ".html", ".css"}:
        return "interface", "inferred"
    return "core", "unknown"


def _definitions(path: str, text: str) -> list[tuple[str, ArchitectureEvidence]]:
    lines = text.splitlines()
    result = []
    suffix = PurePosixPath(path).suffix.lower()
    if suffix == ".py":
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            return result
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.lineno <= len(lines):
                result.append((node.name, _evidence(path, node.lineno, lines[node.lineno - 1])))
    elif suffix in JS_SUFFIXES:
        pattern = re.compile(r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let)\s+([\w$]+)")
        for line, content in enumerate(lines, 1):
            match = pattern.search(content)
            if match:
                result.append((match.group(1), _evidence(path, line, content)))
    return result


def build_architecture(snapshot_id: UUID | str, project_name: str, files: dict[str, str]) -> ArchitectureMap:
    """Pure transformation; callers supply only hash-verified snapshot text."""
    summary, summary_source = _summary(files)
    imports, inspected, resolved, unresolved, alias_candidates = _imports(files)
    references = _manifest_refs(files) + _html_refs(files)
    paths = sorted(files)
    definitions = {path: _definitions(path, files[path]) for path in paths}
    folders = {"."}
    for path in paths:
        folders.update(str(parent) for parent in PurePosixPath(path).parents)
    entry_files = {ref.target for ref in references if ref.entry}
    for path in paths:
        if path.endswith(".py") and re.search(r"^\s*if\s+__name__\s*==\s*['\"]__main__['\"]\s*:", files[path], re.M):
            entry_files.add(path)
    # Root code and manifest files remain visible as separate modules. Nested
    # files participating in a resolved import are visible too, so an import
    # arrow points to the exact file rather than to a possibly broad folder.
    # Other nested files are represented by their nearest folder.
    root_files = [path for path in paths if "/" not in path]
    separate_files = {path for path in root_files if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES
                      or path.lower() in MANIFEST_NAMES or path.lower().startswith("readme")}
    separate_files |= entry_files
    separate_files |= {path for ref in references for path in (ref.source, ref.target)}
    separate_files |= {path for source, target, _ in imports for path in (source, target)}
    direct_files: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        direct_files[str(PurePosixPath(path).parent)].append(path)
    folder_counts = {folder: sum(path == folder or path.startswith(folder + "/") for path in paths)
                     if folder != "." else len(paths) for folder in folders}
    def module_for(path: str) -> str:
        if path in separate_files:
            return f"file:{path}"
        return f"folder:{PurePosixPath(path).parent}"
    modules: list[ArchitectureModule] = []
    for folder in sorted(folders, key=lambda item: (item.count("/"), item)):
        kind, confidence = _kind(folder, True)
        count = folder_counts[folder]
        direct = direct_files.get(folder, [])
        suffixes = Counter(PurePosixPath(path).suffix.lower() or "无扩展名" for path in paths
                           if folder == "." or path.startswith(folder + "/"))
        types = "、".join(f"{extension} {number} 个" for extension, number in suffixes.most_common(2))
        label = KIND_TITLES[kind]
        prefix = "仓库根目录" if folder == "." else f"{label}（按名称归类）" if confidence == "inferred" else "目录"
        role = f"{prefix}，包含 {count} 个保留文件" + (f"；主要类型：{types}。" if types else "。")
        symbols = [(name, evidence) for path in paths
                   if folder != "." and path.startswith(folder + "/")
                   for name, evidence in definitions[path]][:3]
        if symbols:
            role += " 可见定义：" + "、".join(name for name, _ in symbols) + "。"
        # Import counts are a statement about source references only.
        import_sources = sorted({source for source, target, _ in imports
                                 if folder != "." and target.startswith(folder + "/")
                                 and not source.startswith(folder + "/")})
        if import_sources:
            role += " 被 " + "、".join(import_sources[:2]) + (" 等" if len(import_sources) > 2 else "") + " 静态导入。"
        evidence = [summary_source] if folder == "." and summary_source else [ref for _, ref in symbols]
        if not evidence and direct:
            representative = direct[0]
            first_line = next((line for line in files[representative].splitlines() if line.strip()), "")
            if first_line:
                line_number = files[representative].splitlines().index(first_line) + 1
                evidence.append(_evidence(representative, line_number, first_line))
        modules.append(ArchitectureModule(id=f"folder:{folder}", title="项目根目录" if folder == "." else folder,
                                          role=role, kind=kind, paths=[folder], evidence=evidence,
                                          confidence=confidence, file_count=count))
    for path in sorted(separate_files):
        entry = path in entry_files
        kind, confidence = _kind(path, False, entry=entry)
        text = files[path]
        symbols = definitions[path]
        inbound = sum(1 for source, target, _ in imports if target == path and source != path)
        entry_refs = [ref for ref in references if ref.target == path and ref.entry]
        entry_reason = "HTML 模块脚本入口" if any(ref.label == "HTML 模块脚本入口" for ref in entry_refs) else "清单声明的入口"
        role = (f"{entry_reason}；" if entry_refs else "") + f"保留的{KIND_TITLES[kind]}文件"
        if symbols:
            role += "；定义 " + "、".join(name for name, _ in symbols[:4]) + (" 等" if len(symbols) > 4 else "")
        if inbound:
            role += f"；被其他模块静态导入 {inbound} 次"
        role += "。"
        first = next(((line, content) for line, content in enumerate(text.splitlines(), 1) if content.strip()), None)
        evidence = [ref.evidence for ref in entry_refs[:2]]
        evidence += [ref for _, ref in symbols[:3 - len(evidence)]]
        if not evidence and first:
            evidence.append(_evidence(path, *first))
        modules.append(ArchitectureModule(id=f"file:{path}", title=path, role=role, kind=kind,
                                          paths=[path], evidence=evidence, confidence=confidence, file_count=1))

    connections: list[ArchitectureConnection] = []
    for folder in sorted(folders):
        if folder == ".":
            continue
        parent = str(PurePosixPath(folder).parent)
        connections.append(ArchitectureConnection(from_id=f"folder:{parent}", to_id=f"folder:{folder}",
                                                  kind="contains", label="包含目录", evidence=[]))
    for path in sorted(separate_files):
        parent = str(PurePosixPath(path).parent)
        connections.append(ArchitectureConnection(from_id=f"folder:{parent}", to_id=f"file:{path}",
                                                  kind="contains", label="包含文件", evidence=[]))
    grouped_evidence: dict[tuple[str, str], list[ArchitectureEvidence]] = defaultdict(list)
    for source, target, evidence in imports:
        pair = module_for(source), module_for(target)
        if pair[0] != pair[1] and len(grouped_evidence[pair]) < 3:
            grouped_evidence[pair].append(evidence)
    for (source, target), evidence in sorted(grouped_evidence.items()):
        connections.append(ArchitectureConnection(from_id=source, to_id=target, kind="imports",
                                                  label="源码导入", evidence=evidence))
    for ref in references:
        connections.append(ArchitectureConnection(from_id=module_for(ref.source), to_id=module_for(ref.target),
                                                  kind="references", label=ref.label, evidence=[ref.evidence]))
    return ArchitectureMap(
        snapshot_id=snapshot_id, project_name=project_name, summary=summary, summary_source=summary_source,
        modules=modules, connections=connections,
        coverage=ArchitectureCoverage(retained_files=len(paths), inspected_source_files=inspected,
                                      folders=len(folders), resolved_imports=resolved,
                                      unresolved_local_imports=unresolved),
        limitations=["只分析已保留的文本快照；未执行仓库代码。",
                     "目录包含和源码导入是不同关系，均不能单独证明运行顺序或函数调用。",
                     "目录类别按名称推测时标为 inferred；未解析的动态导入、别名和外部依赖不绘制关系。",
                     *([f"发现 {alias_candidates} 个看似路径别名的导入；尚未读取别名配置，不能确认其指向。"]
                       if alias_candidates else [])],
    )


def read_architecture(settings: Settings, snapshot_id: UUID) -> ArchitectureMap:
    """Load a registered snapshot and verify every source file before mapping."""
    with connect(settings.database) as db:
        row = db.execute("""SELECT s.id, p.name FROM snapshots s JOIN projects p ON p.id = s.project_id
                            WHERE s.id = ?""", (str(snapshot_id),)).fetchone()
        if row is None:
            fail("snapshot_not_found", "源码快照不存在。", 404)
        manifest = db.execute("SELECT path, sha256 FROM snapshot_files WHERE snapshot_id = ? ORDER BY path",
                              (str(snapshot_id),)).fetchall()
    base = settings.data_dir / "snapshots" / str(snapshot_id)
    if base.is_symlink() or not base.is_dir():
        fail("snapshot_missing", "源码快照已丢失或路径已变化，请重新导入。", 409)
    files = {}
    for item in manifest:
        path = validate_path(item["path"])
        target = base / path
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent != base and base in parent.parents):
            fail("snapshot_changed", "快照路径已变化，请重新导入。", 409)
        if not target.resolve().is_relative_to(base.resolve()):
            fail("snapshot_changed", "快照路径已变化，请重新导入。", 409)
        try:
            with target.open("rb") as stream:
                raw = stream.read(MAX_FILE + 1)
        except OSError:
            fail("snapshot_missing", "源码快照文件已丢失，请重新导入。", 409)
        if len(raw) > MAX_FILE or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            fail("snapshot_changed", "快照文件与保存的校验值不一致，请重新导入。", 409)
        try:
            files[path] = raw.decode("utf-8")
        except UnicodeDecodeError:
            fail("snapshot_changed", "快照文件编码已变化，请重新导入。", 409)
    return build_architecture(snapshot_id, row["name"], files)
