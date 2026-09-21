# OpenRouter 配置与一次小测试

2026-09-21。本轮选择 OpenRouter + `deepseek/deepseek-v4-flash`，22:16已通过一次短请求，见 [实际验证](../evidence/m3/openrouter-precheck.md)；此测试不等于 PocketFlow 步骤 7 真实流程验收。

## 1. 只需填写本机密钥

已创建根目录下的 **`server/.env`**，文件权限 0600，Git 忽略。前三项已填好，只在 `OPENROUTER_API_KEY=` 后粘贴自己的 OpenRouter Key 并保存，不添加空格、注释或多余文字。不要把真实文件或密钥发到聊天、提交 Git。

```dotenv
LLM_PROVIDER=OPENROUTER
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
OPENROUTER_BASE_URL=https://openrouter.ai/api
OPENROUTER_API_KEY=
```

可在 [OpenRouter 密钥页面](https://openrouter.ai/settings/keys) 创建项目专用 Key。OpenRouter Key 用于调用所选模型，不需要另办 DeepSeek Key。

地址这里故意不带 `/v1`：当前上游适配方式与测试工具会追加 `/v1/chat/completions`，完整请求地址为 `https://openrouter.ai/api/v1/chat/completions`。SDK 常见的 baseURL `/api/v1` 不适用于这个变量约定。

配置检查器只读这四个字段，不运行 shell、不展开变量；同名进程环境变量优先于文件，包括空值。可用 `--env-file /绝对路径/配置文件` 指定其他文件，默认固定 `server/.env`，与工作目录无关。文件有值只代表已填写，不代表密钥有效或余额充足。

## 2. 简单验证

在 **server/** 执行（也可填写完成后让 Codex 执行）：

```bash
.venv/bin/python -m app.model_check
.venv/bin/python -m app.model_check --smoke
```

- 第一条：只检查本机配置，显示服务商、模型、密钥是否存在，**不发请求，不显示密钥**。缺配置退出码为2。
- 第二条：缺密钥时不发网络请求；配置齐全才发送一次固定短代码解释请求，输出上限256 token，30秒网络超时，不读取仓库文件。
- 不自动重试、不自动换模型；按低价排序，并限制路由单价≤$0.10/M 输入、≤$0.25/M 输出，禁用提供商 fallback。若没有满足限制的服务商，会失败而不会悄悄使用更贵的路由。
- 返回 status=passed 仅表示接口返回了完整文本（finish_reason=stop）；需要阅读短回答核对基本质量。length 等截断状态为 incomplete，不视作成功。
- 401／402／429分别报告鉴权失败／余额不足／限流，不打印服务端原始错误体；不会自动充值。
- 每次显式 `--smoke` 的脱敏报告写入被忽略的 `var/model-checks/`，包含实际返回模型、token用量和API报告的费用（缺失则为null，不编造费用）。它不创建 SQLite PocketFlow 任务。

## 3. 本次价格比较

以下来自本次直接读取的 [OpenRouter 官方 models API](https://openrouter.ai/api/v1/models)，单位为美元／百万token。网页缓存与实时API、不同供应商可能有差异；优惠会变化，本表是选型快照，不保证未来成交价格。

| 模型 ID | 输入 | 输出 | 示例10,000输入＋2,000输出 |
|---|---:|---:|---:|
| `deepseek/deepseek-v4-flash` | $0.05852 | $0.11704 | $0.00081928 |
| `qwen/qwen3-30b-a3b-instruct-2507` | $0.04815 | $0.19305 | $0.00086760 |
| `z-ai/glm-4.7-flash` | $0.06050 | $0.40000 | $0.00140500 |
| `deepseek/deepseek-v3.2` | $0.26900 | $0.40000 | $0.00349000 |

因此本轮先用 DeepSeek V4 Flash：在上述假定输入／输出比例下最低，输出价格也低于本表其他候选。Qwen 的输入单价更低，在更偏重输入的请求中可能反而更省。这不是全平台最低价格榜，也不是模型质量评测。

本表不包含实际多阶段任务的重复输入、可能的推理token与充值费用；完整 PocketFlow 会请求多次，不能直接套用为整次生成价格。官方模型页当前有促销路由，优惠变化后本测试的价格上限可能阻止请求，应先核对原因，不自动提高上限。

来源：[DeepSeek V4 Flash](https://openrouter.ai/deepseek/deepseek-v4-flash)、[GLM 4.7 Flash](https://openrouter.ai/z-ai/glm-4.7-flash)、[Qwen3 30B](https://openrouter.ai/qwen/qwen3-30b-a3b-instruct-2507)、[OpenRouter 请求格式](https://openrouter.ai/docs/quickstart)、[供应商价格限制](https://openrouter.ai/docs/guides/routing/provider-selection)。

## 4. 与页面运行的关系

`app/model_config.py` 与 `app/model_check.py` 负责配置检查和独立短请求；真实任务现在通过相同配置读取器调用受控 PocketFlow 入口。启动后台时显式设置 `REPOLENS_ENABLE_REAL_RUN=1`，然后在页面选择“真实 PocketFlow”并点击“启动真实任务”。默认仍为替身，保存 Key 不会自行运行。

页面显示所选模型和密钥是否已配置；实际请求次数、返回模型、用量和费用写入运行记录。仅分析固定 PocketFlow 快照的 utils、中文、最多3主题，每次失败不自动重试；具体上限见 [07 任务说明](07-task-runner.md)。缺少 Key 时禁用真实启动；修改本机文件后点击“重新读取”更新配置状态。完整任务验收见 [M3 实际记录](../evidence/m3/acceptance.md)，短请求通过本身不代表完整任务通过。
