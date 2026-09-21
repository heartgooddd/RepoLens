# PocketFlow 固定入口与独立依赖环境

核对日期：2026-09-21。本目录只放 RepoLens 的安装说明和锁文件；上游源码继续保留在 `upstream/pocketflow-codebase-knowledge/`，没有修改或复制进产品代码。

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

## 步骤 6 的执行边界

- 页面只调用 RepoLens 固定替身入口 `app/stub_worker.py`，使用 **server/.venv**，不加载模型 SDK。替身会实际创建子进程、读取校验后的输入副本、输出固定 Markdown。
- `app/pocketflow_adapter.py` 已准备固定 `main.py` 参数数组，核对 Commit 和被跟踪的 Python／依赖／许可证文件。上游独立环境仅做了依赖校验和 `main.py --help` 入口加载，**没有真实生成请求**。
- 没有 `REPOLENS_RUNNER_MODE` 或 `REPOLENS_MODEL` 配置开关；设置密钥不会启用真实执行。步骤 7 需显式接通真实适配器、阶段解析和模型配置，再做一次授权的小范围验收。
- 上游 `call_llm.py` 支持 Gemini 配置与通用服务商环境变量，但服务商、实际模型和可用密钥本步未确定。不要照搬上游旧的默认预览模型名作为可用性保证。
- 上游会记录请求／响应、使用缓存并自动加载 `.env`。适配器预备 `--no-cache`；进程在独立运行目录工作，禁用 dotenv 自动加载，日志目录指向运行目录。当前替身环境不继承任何模型密钥、云凭据、代理或 PYTHONPATH。真实模式接入时必须只传入已选服务商需要的变量并核对日志内容。
- 虚拟环境隔离的是 Python 依赖，不是操作系统沙箱。当前只运行固定、核查过的入口；输入快照当作文本读取，不执行上传项目脚本。Windows 进程控制未适配。
