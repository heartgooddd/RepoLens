# 已登记操作配方与隔离运行

M5 在 M3 已真实验收的 PocketFlow worker 上增加版本化配方、服务端参数模式和 macOS 文件访问限制。正式注册表目前只有 `pocketflow-tutorial@1`。真实支持依据见 [M3 实跑](../evidence/m3/acceptance.md)；本阶段离线运行与沙箱证据见 [M5 验收](../evidence/m5/acceptance.md)。

## 使用与接口

按根 README 启动前后端，在 PocketFlow 固定版本项目的运行窗口选择已登记操作，再选择真实运行。表单来自 `GET /api/recipes` 的参数模式，页面显示环境状态、隔离方式和超时。后台不开启真实模式、模型配置不完整、入口/依赖不匹配、平台缺少隔离能力或输入版本不支持时，不能启动真实配方。

```http
GET /api/recipes
```

返回 `items`；每项包含 `id/version/name/verification`、`entry`、`environment`、Pydantic JSON Schema `parameters`、`input`、`working_directory`、`timeout_seconds/max_timeout_seconds`、`stop`、`artifacts`、`requires_model/network`、`isolation`、`ready/unavailable_reasons`。不返回绝对主机路径、命令数组或密钥。

```json
{
  "recipe_id": "pocketflow-tutorial",
  "snapshot_id": "已登记的快照 UUID",
  "parameters": {"scope": "utils", "language": "zh", "topics": 3}
}
```

以上 JSON 发送到 `POST /api/runs`。`topics` 是严格整数 1–3，不能传字符串或布尔值；其余参数当前固定为 `utils` 和 `zh`。省略参数时使用配方默认值。未知配方返回 404，额外字段、越界参数和不支持的输入返回 422；运行环境或隔离能力不就绪返回 409。成功创建返回 201，复用已校验模型结果返回 200 和 `X-RepoLens-Result-Cache: hit`。

迁移 006 增加 `recipe_id/recipe_version/parameters_json/isolation_kind`。既有记录保持可读；空配方字段显示旧版固定入口。新记录保留规范化参数，不受表单或注册表以后变化影响。结果缓存同时绑定 snapshot、配方 ID/版本/全部参数、模型、提示词等；源码快照缓存规则不变。

旧 `mode=pocketflow` 请求作为兼容入口，映射到同一配方并执行相同校验和沙箱策略。旧 `mode=stub` 是明确标识的固定诊断程序；没有用户命令执行能力，也不在正式配方清单中。

## 文件与执行边界

| 内容 | 谁决定 | 运行权限 |
|---|---|---|
| 固定解释器、worker、参数数组 | `server/app/recipes/` 的可信产品代码 | 可执行；页面无法改成上传文件 |
| 已验证 PocketFlow `.py` | 固定 Commit 的 Git 文件清单和内容校验 | 只读；未跟踪 Python 文件、`.env` 不获授权 |
| 被分析快照 | `snapshot_id` 对应的已登记文件及哈希 | 复制到本次 `input/`，沙箱内只读 |
| 输出与临时数据 | 本次运行目录的指定子目录 | 只允许写 `output/`、`home/`、`tmp/`、`model-data/`、`provider-logs/` |
| SQLite、其他快照/任务、主机私人文件 | 后台保管 | worker 不获内容读写权限 |

`isolation.py` 生成 deny-default Seatbelt 策略，授权固定 Python 环境、系统运行库、OpenSSL 动态库/证书和配方声明的读取范围。为 Python 导入和系统加载器允许目录条目及主机路径元数据读取；这不授予未列入清单文件的内容读取权限。进程 cwd 固定为本次运行目录，环境不继承主机密钥、代理或 `PYTHONPATH`。模型密钥仍经 stdin 交付。

PocketFlow 配方允许出站网络，当前不做域名级防火墙；模型客户端固定请求 OpenRouter。非网络配方必须声明 `network=False`。运行时不调用 Git 拉取代码；GitPython 的启动探测被关闭，源码导入与运行分开。

能力自检真实验证输入读取、输出写入及范围外读写/输入修改被拒绝；只存在二进制文件或返回退出码 0 不算通过。非 macOS、二进制缺失或自检失败时返回 `isolation_unavailable`，不降级。macOS 系统手册已将 `sandbox-exec` 标为 deprecated，本阶段仅验收当前 macOS，本地发行前须继续核对可用性。

运行由独立进程组和父进程监督器管理。取消或超时先 SIGTERM，等待 0.2 秒再 SIGKILL；入口正常退出也清理同组残留进程。默认和最大超时均为 900 秒，网页不能覆盖；失败保留退出码，不发布成功产物。超时必须主动终止进程，不能只取消等待，参见 [Python 子进程说明](https://docs.python.org/3/library/subprocess.html#subprocess.Popen.communicate)。

新配方必须保证子进程留在受管进程组内；当前方案不接入会 `setsid`、双重 fork 或委托外部守护进程的项目。Seatbelt 文件权限会继承到后代，但进程组停止并不保证清理由目标自行脱离进程组的守护进程。任意不可信程序、CPU/内存/磁盘配额和跨平台执行均不在本阶段支持范围内。

产物必须来自本次 `output/`，默认必需 `project/index.md`，允许 `.md/.json`，最多 32 文件、单文件 512 KiB、总量 4 MiB。后台先检查整个输出树，拒绝软链接、硬链接、特殊文件、越界路径和未声明类型，然后读取职责文件及登记哈希。当前限制是在收集产物时检查，不是运行时磁盘配额。

## 新增一份配方

新增真实项目之前，先确认项目目标、来源、许可证、固定 Commit、可复现安装方式和具体入口；明确它需要哪些网络/文件能力、输出什么，以及是否产生脱离进程组的后台进程。源码导入本身不会触发登记。

1. 在独立的运行环境安装并锁定依赖；入口放产品适配目录或已审查的固定上游位置，不指向 `var/snapshots/`。实现依赖版本、入口 Commit 和文件内容检查。
2. 新建 `server/app/recipes/<action>.py`。用严格 Pydantic 模型定义参数，`extra='forbid'`；目前表单支持字符串、整数、枚举与单值约束。后台约定可选 `scope` 表示已登记目录，默认 `.`；`language/topics` 属于现有教程兼容字段。

```python
from pydantic import BaseModel, ConfigDict, Field

class Parameters(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    scope: str = Field(default='.', title='分析范围')
    limit: int = Field(default=3, ge=1, le=10, title='条目上限')

def command(source, output, parameters):
    return [str(PYTHON), '-B', '-u', str(ENTRY),
            '--input', str(source), '--output', str(output),
            '--limit', str(parameters['limit'])]
```

这里的 `PYTHON`、`ENTRY` 必须在同一模块定义为经过审查的固定路径。命令工厂仅由服务端调用；不接受用户命令、shell 模板、任意 cwd 或环境字典。首版配方协议限定 Python 参数数组 `[python, -B, -u, entry, ...]`。

3. 按 `recipes/pocketflow.py` 的完整实例创建 `ActionRecipe`：填写独立 ID/版本、名称、验证说明、来源 Commit、入口/环境文档路径、参数模型、命令工厂、`runtime_ready`、`read_paths`、输入版本规则、是否调用模型、网络、超时/上限、停止宽限与产物契约。无需另写生命周期运行器。当前 Markdown 结果面板适配教程型产物；新增其他产物类型时应同步扩展展示及其测试。
4. 先在测试应用的 `runner.recipes` 注入 `public=False` 配方。`test_second_code_registered_recipe_uses_its_own_parameters_and_entry` 提供完整最小示例；它只证明独立参数与入口能通过同一个运行器，不能证明真实项目支持。
5. 编写未知配方/参数拒绝、输入与入口分离、范围外访问拒绝、子进程停止、超时、退出码、产物链接/大小/类型测试。运行：

```bash
server/.venv/bin/python -m pytest -q server/tests/test_recipes.py server/tests/test_isolation.py
server/.venv/bin/python -m pytest -q server/tests
cd web
npm run build
npm run test:e2e
```

6. 取得该具体真实操作的运行授权后做小范围实跑，保存来源、参数、退出码、日志、真实产物和页面读回证据。真实验证通过后才设 `public=True`、加入 `recipes/__init__.py` 正式清单，并更新支持范围。涉及新模型或费用时另行确认范围；M3 授权不自动扩展到新项目。
7. 入口、依赖、参数语义、提示词、隔离或产物契约变化时提升配方版本，并重跑验证，防止旧结果被新配方复用。

当前新增配方机制和隔离测试只扩展开发能力；已真实支持的第三方项目仍只有已验收的 PocketFlow 教程入口。
