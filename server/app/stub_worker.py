"""A real subprocess producing fixed fixtures. No model client or network library."""
import argparse
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--dir', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--language', choices=['zh', 'en'], required=True)
parser.add_argument('--topics', type=int, required=True)
parser.add_argument('--scenario', choices=['success', 'failure', 'slow'], required=True)
args = parser.parse_args()
files = sorted(p.relative_to(args.dir).as_posix() for p in Path(args.dir).rglob('*') if p.is_file())
print('替身进程：只验证任务与产物，不调用真实模型。', flush=True)
for stage in ('FetchRepo', 'IdentifyAbstractions', 'AnalyzeRelationships', 'OrderChapters', 'WriteChapters', 'CombineTutorial'):
    print('REPOLENS_STAGE:' + stage, flush=True)
    time.sleep(0.35 if args.scenario != 'slow' else 5)
    if args.scenario == 'failure' and stage == 'AnalyzeRelationships':
        print('替身错误：模拟生成失败。', flush=True)
        raise SystemExit(23)
output = Path(args.output) / 'project'
output.mkdir(parents=True)
heading = '替身验证结果' if args.language == 'zh' else 'Stub verification result'
(output / 'index.md').write_text(f'# {heading}\n\n**固定输出，不是真实模型分析。**\n\n参数：{args.language} / {args.topics} 个主题\n\n读取 {len(files)} 个已校验的输入文件。\n\n[第一章](01-introduction.md)\n\n<script>window.__unsafeMarkdown = true</script>\n\n[危险链接](javascript:alert(1))\n\n![不加载远程图片](https://example.com/tracking.png)\n', encoding='utf-8')
(output / '01-introduction.md').write_text('# 固定章节\n\n此章节仅用于验证 Markdown 预览、下载和历史重开。\n\n- 不调用模型\n- 不执行输入源码\n', encoding='utf-8')
# Intentional bad citation exercises the unverified path without inventing evidence.
(output / 'folder-claims.json').write_text(json.dumps({'claims': [{'folder_path': '.', 'description': '固定替身职责说明。', 'references': [{'file_path': 'missing.py', 'line_start': 1, 'line_end': 2, 'quote': 'not present'}]}]}, ensure_ascii=False), encoding='utf-8')
print('替身产物已写入。', flush=True)
