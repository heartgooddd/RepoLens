# M3 步骤 7：真实运行验收记录（阻塞，未通过）

日期：2026-09-21。检查起点为 `bfad80bb7436c634155e204eb63e187db0925305`，分支 `feat/m3-pocketflow-runner`，开始时工作区干净。

**初次预检结论（历史状态）：模型配置不齐全，真实执行接入也尚未完成。本次没有创建真实任务、没有发送模型请求，没有新的真实生成产物；M3 不标记完成，不执行 G3 合并。** 按用户“配置仍缺失时只记录已完成验证和阻塞点”的要求，本次仅修改文档并按 G2 保存。

## 后续配置准备（同日更新）

用户已选 OpenRouter，模型根据实时价格先选 DeepSeek V4 Flash；本机配置文件与一次短请求检查器已准备，见 [本轮记录](openrouter-precheck.md)。下面的表格保留初次预检时状态。后续于22:16完成本机Key读取和一次 OpenRouter 真实短请求，见 [结果](openrouter-precheck.md)；缺密钥阻塞已解除，真实 PocketFlow 接入与完整流程验收仍待完成。

## 1. 配置检查（仅状态，不含密钥）

检查范围：本次执行命令继承的环境、RepoLens 根目录和 server 的常见本机配置文件、固定上游目录的 `.env`；同时读取运行中的后台 `/api/runner` 与实际配置／执行代码。没有读取其他应用的凭据库，也没有将其他工具的登录状态当作本项目模型授权。环境变量存在不表示已被后台读取或通过联网鉴权。

| 项目 | 实际状态 |
|---|---|
| 服务商选择 `LLM_PROVIDER` | 未设置；未确定 RepoLens 实跑使用哪个服务 |
| Anthropic 模型／地址变量 | `ANTHROPIC_MODEL`、`ANTHROPIC_BASE_URL` 有值；本次不记录值，未确认是本项目的选定配置 |
| Anthropic API Key | `ANTHROPIC_API_KEY` 未设置 |
| Gemini | `GEMINI_API_KEY`、`GEMINI_MODEL`、`GEMINI_PROJECT_ID`、`GEMINI_LOCATION` 未设置 |
| Google 凭据候选 | `GOOGLE_API_KEY`、`GOOGLE_APPLICATION_CREDENTIALS` 未设置；未尝试隐式云登录 |
| OpenAI 配置候选 | `OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_BASE_URL` 未设置 |
| 本机配置文件 | 根目录 `.env`／`.env.local`、`server/.env`／`.env.local`、`server/pocketflow/.env`、固定上游 `.env` 均不存在 |
| 后台运行模式 | `GET /api/runner` 返回 `mode=stub`、`real_enabled=false`、超时180秒 |
| 后台模型配置读取 | `Settings.from_env()` 只读取数据目录；没有实际模型配置读取入口，`.env.example` 仅模板 |
| 实际模型 | **未选定、未调用**；不能用上游默认值或环境中孤立的模型变量填写真实运行记录 |

本步未调用模型鉴权／测试接口，不判断任何服务商当前是否可用。添加一个 `.env` 或设置密钥不会自动将现有后台改为真实模式。

## 2. 本次已完成的只读验证

- 分支仍为 `feat/m3-pocketflow-runner`；main 仍在 `180e50dc11ac43e86275d59d4899b441fbf11df1`。
- PocketFlow HEAD：`05b24cbbb0fe409c5e23c9791f0342f07524ffdc`；上游工作区干净；调用 `verify_upstream()` 核对已跟踪的 Python、依赖、许可证文件通过。
- `server/pocketflow/.venv/bin/python -m pip check` 返回 `No broken requirements found`。
- 后台任务接口可读。用 **SQLite 只读连接** 与 GET 接口核对步骤 6 的旧替身任务 `f8190626-c5ad-4b43-8a4a-6f25d932bd89`：mode=stub、status=succeeded、scope=utils、language=zh、topics=3，一致。
- 对该旧任务的4个已登记产物逐一比较磁盘字节数、SHA-256、API 返回哈希及正文，全部一致。本次检查时数据库只有2条 stub 任务，没有 pocketflow 模式任务。
- 这些验证只说明**既有替身历史可读取且文件一致**，不能充当真实模型输出或本次浏览器真实流程验收。旧截图、44项后台和16项浏览器通过记录见 [步骤 6](step-6-check.md)；本次没有重新执行这些测试，也没有将旧截图作为真实实跑截图。

执行命令包括：

```bash
# RepoLens 根目录
git status --short --branch
git log -1 --format='%H %s'
git rev-parse main
git -C upstream/pocketflow-codebase-knowledge rev-parse HEAD
git -C upstream/pocketflow-codebase-knowledge status --porcelain
curl --fail --silent http://127.0.0.1:8000/api/runner

# server/ 目录
pocketflow/.venv/bin/python -m pip check
```

配置检查使用 Python 在内存中读取指定变量／文件，仅输出存在与非空布尔值；没有输出变量值。历史读回使用 `.venv/bin/python`，对固定旧 run ID 做 GET 和 `sqlite3.connect(...?mode=ro, uri=True)`，仅输出模式、状态与比较结果，没有写入数据库。

## 3. 阻塞点与尚未验收的内容

1. **用户配置（已解除）：**已选 OpenRouter／DeepSeek V4 Flash，本机Key已读取并通过一次短请求。初次预检缺配置的情况已解决。
2. **实现接入：**`runner.py` 仍固定调用 `stub_command()`；`pocketflow_command()` 目前只用于入口准备／help 检查。需要实现模型配置读取与缺配置报错、受限传递凭据、真实入口调用、真实阶段解析、实际模型记录、真实结果页面标签，以及职责提示词调用／结果登记。该项是代码工作，不能靠用户填密钥解决。
3. **真实验收：**页面启动、阶段日志、Markdown 与数据库／文件一致性，以及真实模式缺密钥、执行失败、取消、历史重开均未通过本次验收。固定替身对这些生命周期行为的既有验证不能代替提供商与真实入口验证。

## 4. 继续条件

- 服务商、模型与本机Key已配置，短请求已通过；不需要再次索要密钥。
- 在当前分支完成上述代码接入，先用无网络夹具检查缺配置、失败和取消路径，再重新检查配置状态。
- 满足条件后，使用当前授权范围从页面启动**一次**真实任务：固定 PocketFlow 已登记快照、仅 utils、中文、最多3个主题。PocketFlow 一次任务可能包含多次模型调用；不因持续报错自动新建任务或反复重试。
- 原始日志、缓存和结果留在 `var/`；筛选不含凭据的真实证据后更新本文件。真实流程通过才执行 G2／G3 合并 M3。
