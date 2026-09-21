"""Static source observations only. Never import or execute the scanned project."""

import ast
from pathlib import PurePosixPath
from uuid import uuid4

from .models import EvidenceRef, FolderCard


def evidence_for(path: str, text: str, snapshot_id, card_id) -> list[EvidenceRef]:
    lines = text.splitlines()
    locations: list[tuple[int, int, str | None]] = []
    if path.endswith(".py"):
        try:
            tree = ast.parse(text)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    locations.append((node.lineno, min(node.end_lineno or node.lineno, node.lineno + 7), node.name))
                elif (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                      and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"
                      and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq)
                      and isinstance(node.test.comparators[0], ast.Constant)
                      and node.test.comparators[0].value == "__main__"):
                    locations.append((node.lineno, min(node.end_lineno or node.lineno, node.lineno + 7), "__main__ guard"))
            # Also show actual flow connections, including those inside functions.
            for node in ast.walk(tree):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.RShift):
                    locations.append((node.lineno, node.end_lineno or node.lineno, "operator >>"))
        except (SyntaxError, ValueError, RecursionError):
            pass
    elif PurePosixPath(path).name.lower() in {"readme.md", "readme.txt", "pyproject.toml", "package.json", "requirements.txt"}:
        start = next((i for i, line in enumerate(lines, 1) if line.strip()), None)
        if start:
            locations.append((start, min(len(lines), start + 7), None))
    result = []
    for start, end, symbol in locations[:12]:
        excerpt = "\n".join(lines[start - 1:end])
        if len(excerpt) > 4000:
            continue
        result.append(EvidenceRef(id=uuid4(), folder_card_id=card_id, snapshot_id=snapshot_id,
                                  file_path=path, line_start=start, line_end=end, symbol=symbol, excerpt=excerpt))
    return result


def scan(files: dict[str, bytes], snapshot_id) -> list[FolderCard]:
    directories = {"."}
    for path in files:
        directories.update(str(p) for p in PurePosixPath(path).parents)
    cards = []
    hints = {"utils": "辅助函数", "docs": "项目文档", "tests": "自动化测试", "test": "测试"}
    for directory in sorted(directories):
        card_id = uuid4()
        children = [p for p in sorted(files) if str(PurePosixPath(p).parent) == directory]
        evidence = [ref for path in children for ref in evidence_for(path, files[path].decode("utf-8"), snapshot_id, card_id)]
        symbols = [f"{ref.file_path}: {ref.symbol}" for ref in evidence if ref.symbol and ref.symbol != "operator >>"]
        description = f"快照中此目录直接包含 {len(children)} 个保留文件。"
        if symbols:
            description += "静态源码定义或入口条件：" + "；".join(symbols[:5]) + "。"
        elif evidence:
            description += "可从下列 README 或配置片段核对项目线索。"
        else:
            description += "尚无足够的定义、README 或配置证据说明其功能职责，待核实。"
        hint = hints.get(PurePosixPath(directory).name)
        cards.append(FolderCard(id=card_id, snapshot_id=snapshot_id, path=directory,
                                title="项目根目录" if directory == "." else directory,
                                description=description, claim_type="fact" if evidence else "unverified",
                                inference=f"仅按目录名推测，可能存放{hint}；实际职责需结合引用和调用关系核实。" if hint else None,
                                evidence_refs=evidence))
    return cards
