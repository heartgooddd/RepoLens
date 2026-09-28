import type { FolderCard, RunParameters, SourceFile } from '../types'

export const snapshot = '05b24cbbb0fe409c5e23c9791f0342f07524ffdc'
export const stages = ['获取仓库文件', '识别核心抽象', '分析关系', '安排章节', '撰写章节', '合并教程']

// Fixed excerpts selected from the local upstream snapshot; no runtime scanning.
const main: SourceFile = {
  path: 'main.py', purpose: '命令行参数与流程启动', line: 40,
  excerpt: '    parser = argparse.ArgumentParser(description="Generate a tutorial for a GitHub codebase or local directory.")\n\n    # Create mutually exclusive group for source\n    source_group = parser.add_mutually_exclusive_group(required=True)\n    source_group.add_argument("--repo", help="URL of the public GitHub repository.")\n    source_group.add_argument("--dir", help="Path to local directory.")',
}
const flow: SourceFile = {
  path: 'flow.py', purpose: '连接六个处理阶段', line: 24,
  excerpt: '    fetch_repo >> identify_abstractions\n    identify_abstractions >> analyze_relationships\n    analyze_relationships >> order_chapters\n    order_chapters >> write_chapters\n    write_chapters >> combine_tutorial',
}
const nodes: SourceFile = {
  path: 'nodes.py', purpose: '实现各阶段的处理逻辑', line: 22,
  excerpt: 'class FetchRepo(Node):\n    def prep(self, shared):\n        repo_url = shared.get("repo_url")\n        local_dir = shared.get("local_dir")\n        project_name = shared.get("project_name")',
}

export const folders: FolderCard[] = [
  { id: 'root', label: '项目总览', title: 'PocketFlow / 项目总览', description: '把仓库源码整理为适合初学者阅读的 Markdown 教程。入口、流程和节点实现各有分工，可以从这三个文件开始阅读。', files: [main, flow, nodes], next: '先读 main.py 的输入参数，再沿 flow.py 查看处理顺序。' },
  { id: 'utils', label: 'utils / 辅助能力', title: 'utils / 辅助能力', description: '集中处理仓库文件抓取和模型调用等支撑工作。下方列出参与生成流程的关键文件。', files: [
    { path: 'utils/crawl_local_files.py', purpose: '读取本地项目文件', line: 6, excerpt: 'def crawl_local_files(\n    directory,\n    include_patterns=None,\n    exclude_patterns=None,\n    max_file_size=None,\n    use_relative_paths=True,\n):' },
    { path: 'utils/crawl_github_files.py', purpose: '读取 GitHub 仓库文件', line: 11, excerpt: 'def crawl_github_files(\n    repo_url, \n    token=None, \n    max_file_size: int = 1 * 1024 * 1024,  # 1 MB\n    use_relative_paths: bool = False,' },
    { path: 'utils/call_llm.py', purpose: '模型调用与缓存', line: 128, excerpt: 'def call_llm(prompt: str, use_cache: bool = True) -> str:\n    # Log the prompt\n    logger.info(f"PROMPT: {prompt}")\n\n    # Check cache if enabled\n    if use_cache:' },
  ], next: '在 nodes.py 中查看这些辅助函数由哪些节点调用。' },
  { id: 'docs', label: 'docs / 样书与设计', title: 'docs / 样书与设计', description: '保存设计说明、文档站点索引与已发布的教程示例。它供人阅读和展示，不在 main.py 启动的生成流程中；新的生成结果默认写入 output/。', files: [
    { path: 'docs/design.md', purpose: '需求与流程设计说明', line: 7, excerpt: '# System Design: Codebase Knowledge Builder\n\n> Please DON\'T remove notes for AI\n\n## Requirements' },
  ], next: '将 design.md 的流程说明与 flow.py 的节点连接对照阅读。' },
  { id: 'main', label: 'main.py', title: 'main.py / 程序入口', description: '接收仓库或本地目录、语言和输出位置等参数，准备共享数据并启动教程生成流程。', files: [main], next: '了解输入后，继续阅读 flow.py 中的 create_tutorial_flow。' },
  { id: 'flow', label: 'flow.py', title: 'flow.py / 流程编排', description: '按顺序连接六个节点：获取文件、识别抽象、分析关系、安排章节、撰写章节和合并教程。', files: [flow], next: '到 nodes.py 查看每个节点怎样准备输入、处理任务和传递结果。' },
  { id: 'nodes', label: 'nodes.py', title: 'nodes.py / 节点实现', description: '实现六个处理节点。每个节点负责流程中的一项任务，并通过共享数据把结果交给下一步。', files: [nodes], next: '从 FetchRepo 开始，追踪它如何调用 utils 中的文件抓取函数。' },
]

const chapters = {
  zh: [
    ['从入口开始', 'main.py 接收仓库或本地目录等参数，准备共享数据，再启动教程生成流程。阅读入口可以先弄清楚项目需要什么输入。'],
    ['理解流程编排', 'flow.py 将六个节点按顺序连接。各节点的输出继续交给后续阶段，最终汇总为教程。'],
    ['找到具体实现', 'nodes.py 包含各处理节点的实现。可以从 FetchRepo 开始，把节点使用的输入和它传递的结果一起阅读。'],
    ['认识辅助能力', 'utils 包含本地文件抓取、GitHub 文件抓取以及模型调用相关代码。它们支撑节点完成实际工作。'],
    ['对照设计文档', 'docs/design.md 说明预期输入、输出和处理流程。将这些设计与入口和节点代码对照，可以发现需要进一步核实的细节。'],
  ],
  en: [
    ['Start with the entry point', 'main.py accepts a repository or local directory, prepares shared data, and starts the tutorial flow. Read the entry point to understand the required inputs.'],
    ['Understand the flow', 'flow.py connects six processing nodes in sequence. Their outputs pass through subsequent stages to form a tutorial.'],
    ['Find the implementation', 'nodes.py contains the processing nodes. Start with FetchRepo and follow its inputs and the data it passes on.'],
    ['Explore supporting utilities', 'utils contains local and GitHub file crawling and model-call helpers used by the processing nodes.'],
    ['Compare the design', 'docs/design.md describes intended inputs, outputs, and flow. Compare it with the source code to identify details that need further verification.'],
  ],
}

export function getDemoChapters(parameters: RunParameters) {
  return chapters[parameters.language].slice(0, parameters.topics)
}

export function sourceUrl(file: SourceFile) {
  return `https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge/blob/${snapshot}/${file.path}#L${file.line}`
}
