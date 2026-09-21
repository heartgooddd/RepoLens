# OpenRouter 配置准备与简单验证状态

日期：2026-09-21；在 `feat/m3-pocketflow-runner` 继续，起点 `1c2d5ce`。

- 用户选择 OpenRouter，委托从 DeepSeek／GLM 等国内模型中选择较低价模型，并确认本机 Key 尚未保存，要求创建配置文件。
- 已通过无鉴权的官方 `/api/v1/models` 查询模型目录与价格，选择 `deepseek/deepseek-v4-flash`。这只验证公开模型记录存在，不证明用户的 Key／账户可调用。比较与来源见 [配置说明](../../docs/08-openrouter-setup.md)。
- 已创建被忽略的 `server/.env`，服务商／模型／地址已填，API Key 初始留空；权限检查为 `-rw-------`。只提交无密钥 `.env.example`。
- 增加本机配置读取与 `python -m app.model_check`；显式 `--smoke` 才能发一次短请求，缺配置不请求，不自动重试或提高价格上限。
- `server/.venv/bin/python -m pytest -q tests/test_model_check.py`：**9项通过**。使用本地 MockTransport，不进行真实模型请求；覆盖配置读取、环境优先级、缺Key不联网、错误地址拒绝、单次输出／价格限制、鉴权／余额／限流失败不重试、密钥不出现在报告。
- 本机 `python -m app.model_check` 实际返回 blocked，missing仅为 OPENROUTER_API_KEY，authentication_verified=false。此处为配置文件创建后的检查时点；后续填写不自动视为鉴权已验证。
- 本次尚未发送带密钥的模型请求，没有真实生成结果或费用记录。用户填好 Key 后再执行一次 `--smoke`，保存实际回答／模型／token／费用及检查结果。
- 页面仍为替身模式。OpenRouter 连通性与 PocketFlow 完整真实运行分别验收，M3 仍未完成，不合并 main。


## 实际短请求验证通过（2026-09-21 22:16，Asia/Shanghai）

用户保存密钥后执行：

```bash
# server/ 目录
.venv/bin/python -m app.model_check
.venv/bin/python -m app.model_check --smoke
```

- 本机配置检查返回 ready，api_key_configured=true，configuration_complete=true；没有显示密钥。
- 显式执行一次真实 OpenRouter 请求，检查器退出码0、status=passed、finish_reason=stop，未重试、未自动换模型。
- 请求与实际返回模型均为 `deepseek/deepseek-v4-flash`。
- 测试输入只包含人工编写的 `def add(a, b): return a + b` 短函数，要求中文一句话解释；没有上传项目源码。
- 实际回答：“定义了一个名为 `add` 的函数，接收两个参数并返回它们的和。”与源码可见行为一致；这仅是一次基础连通性／简单回答检查，不是代码分析质量评测。
- 输入34 token、输出18 token、合计52 token；API报告费用为 **$0.0000039886**，不是估算，也不代表完整 PocketFlow 任务价格。
- 原始脱敏报告留在 `var/model-checks/`；筛选后的实际字段保存于 [openrouter-smoke.json](openrouter-smoke.json)。检查时间为 `2026-09-21T14:16:35.887483+00:00`。
- 现在已确认本次Key与所选模型可调用，之前的缺密钥阻塞已解除。下一步仍需完成真实 PocketFlow 入口、阶段日志、页面结果接入，并验收 utils／中文／最多3个主题任务。本轮没有创建该任务或合并 M3。
