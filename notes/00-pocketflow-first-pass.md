# PocketFlow Codebase Knowledge 第一轮解析计划

## 来源快照

- 官方仓库：https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge
- 本地目录：`../upstream/pocketflow-codebase-knowledge/`
- Commit：`05b24cbbb0fe409c5e23c9791f0342f07524ffdc`
- 许可证：MIT
- 当前状态：仅完成静态阅读，未安装依赖、未执行仓库脚本、未填入 API Key。

## 为什么先拆它

这是一个规模较小、入口明确的代码库分析管线，适合作为 RepoLens 的第一份端到端样本。它能帮助我们看清“仓库摄取—抽象识别—关系分析—章节排序—批量写作—合并输出”的完整链路，同时也容易识别 RepoLens 需要补足的证据、安全和学习闭环。

## 已确认的主流程

```text
main.py
  ↓ 初始化 shared state
FetchRepo
  ↓ files
IdentifyAbstractions
  ↓ abstractions
AnalyzeRelationships
  ↓ relationships
OrderChapters
  ↓ chapter_order
WriteChapters
  ↓ chapters
CombineTutorial
  ↓ final_output_dir
```

## 推荐阅读顺序

1. `README.md`：产品目标、输入方式和输出形态。
2. `docs/design.md`：作者设计意图与节点职责。
3. `main.py`：命令行参数、过滤规则和全局共享状态。
4. `flow.py`：六个节点的串联顺序、重试设置。
5. `nodes.py`：逐节点分析输入、处理、Prompt、校验和输出。
6. `utils/crawl_local_files.py` 与 `utils/crawl_github_files.py`：仓库摄取和过滤边界。
7. `utils/call_llm.py`：模型适配、缓存、密钥和错误处理。

## 第一轮要回答的问题

1. 哪些数据来自源码事实，哪些结论来自 LLM 推断？
2. 六个节点的输入输出契约是什么，是否可以单独重跑？
3. 某一步产生错误时，错误如何传播到最终教程？
4. 当前输出能否回到具体文件、符号和代码位置？
5. 仓库抓取、Prompt 输入和本地运行分别有什么安全风险？
6. 哪些模块可以直接依赖，哪些应该提取思想后重写？

## RepoLens 的改进实验

- 为每条架构结论增加 `commit + file + symbol + line` 证据。
- 把结论标记为“源码事实 / 模型推断 / 运行验证”。
- 为每一步保存中间产物，支持断点恢复和人工修正。
- 输出 5 个关键文件的阅读路线，而不是一次生成整本教程。
- 增加一个需要用户启动或修改小模块的复现任务。

## 下一步动作

先静态拆完 `main.py → flow.py → nodes.py`，生成节点输入输出表和一张错误传播图；确认后再决定是否在隔离环境安装依赖并运行小型样本。
