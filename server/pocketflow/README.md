# PocketFlow 固定入口与独立依赖环境

核对日期：2026-09-21。本目录放 RepoLens 的安装说明、锁文件和受控适配入口 worker.py；上游源码继续保留在 `upstream/pocketflow-codebase-knowledge/`，没有修改或复制进产品代码。

## 来源核对

| 项目 | 本机结果 |
|---|---|
| origin | https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge.git |
| Commit | `05b24cbbb0fe409c5e23c9791f0342f07524ffdc` |
| 工作区 | `git status --porcelain` 为空 |
| 许可证 | MIT，Copyright (c) 2025 Zachary Huang；原文保留在上游 `LICENSE` |
| 固定入口 | 上游 `main.py`；本地目录参数 `--dir`，输出 `--output`，语言 `--language`，主题数 `--max-abstractions` |
| 流程 | `flow.py` 连接 `nodes.py` 六个节点；模型调用在 `utils/call_llm.py` |
| Python | macOS Apple Silicon / Python 3.14.6 |

## 安装与复查

以下在 **server/** 执行；与 FastAPI 的 `server/.venv/` 分开：

```bash
python3.14 -m venv pocketflow/.venv
pocketflow/.venv/bin/python -m pip install -r pocketflow/requirements.lock
pocketflow/.venv/bin/python -m pip check
```

已有环境不必再次创建。完整锁文件来自本次隔离环境的 `pip freeze`，保留全部传递依赖，未包含包哈希。本次首次解析使用固定上游 Commit 的 `requirements.txt`；之后按锁文件复现。

| 上游要求 | 实际安装 |
|---|---|
| pocketflow >= 0.0.1 | 0.0.3 |
| pyyaml >= 6.0 | 6.0.3 |
| requests >= 2.28.0 | 2.34.2 |
| gitpython >= 3.1.0 | 3.1.62 |
| google-cloud-aiplatform >= 1.25.0 | 2.1.3 |
| google-genai >= 1.9.0 | 2.24.0 |
| python-dotenv >= 1.0.0 | 1.2.3 |
| pathspec >= 0.11.0 | 1.1.1 |

`pip check` 已通过。以下核对命令在根目录执行：

```bash
git -C upstream/pocketflow-codebase-knowledge remote get-url origin
git -C upstream/pocketflow-codebase-knowledge rev-parse HEAD
git -C upstream/pocketflow-codebase-knowledge status --porcelain
```

## 步骤 7 的执行边界

- 替身模式仍调用 `app/stub_worker.py`，使用后台环境，无模型请求。
- 真实模式先核对固定 Commit 和被跟踪的 Python／依赖／许可证文件，通过隔离环境运行 `worker.py`，再以 `runpy` 调用原始 `main.py`。不修改上游源码。
- 适配器覆盖节点的模型函数，使用已有 HTTPX 0.28.1 调用 OpenRouter；禁用上游重试、缓存、原始模型日志函数和 dotenv 自动加载。节点执行前打印阶段，章节完成后调用 `server/app/prompts/folder-responsibility-v1.md`。
- 修正上游小主题数提示“top 5-3”，校验返回主题不超过请求值。真实参数当前固定 utils、中文、最多3主题。
- `REPOLENS_ENABLE_REAL_RUN=1` 开启后台真实入口；还须页面明确选择并点击启动。密钥从 `server/.env` 读取，经 stdin 传子进程，不放 argv 或运行文件；原始响应与用量保存在被忽略的 `var/runs/`。
- 每次模型请求只尝试一次，最多7次调用，失败不会自动重跑。上限和 API 见 [任务说明](../../docs/07-task-runner.md)。实际证据见 [M3 验收](../../evidence/m3/acceptance.md)。
- 虚拟环境隔离的是依赖，不是操作系统沙箱；输入快照只作文本读取，不执行上传脚本。当前仅本机、单进程；Windows 未适配。
