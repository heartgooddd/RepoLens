import { stages } from '../demo/pocketflow'
import type { RunState } from '../types'

export function RunProgress({ run }: { run: RunState }) {
  if (run.status === 'idle') return <p className="muted">还没有运行记录。选好参数后，可以开始一次演示。</p>
  const completed = run.status === 'success' ? stages.length : run.step
  return <ol className="progress-list" aria-label="模拟运行进度">
    {stages.map((stage, index) => <li className={index < completed ? 'done' : index === completed ? 'current' : ''} key={stage}>
      <span aria-hidden="true">{index < completed ? '✓' : index + 1}</span>
      <span>{stage}</span>
      <small>{index < completed ? '演示完成' : index === completed ? run.status === 'running' ? '模拟中' : run.status === 'error' ? '模拟失败' : '已停止' : '等待'}</small>
    </li>)}
  </ol>
}

export function RunLogs({ run }: { run: RunState }) {
  if (run.status === 'idle') return null
  const visible = run.status === 'success' ? stages.length : run.step + 1
  return <details className="run-logs"><summary>查看模拟日志</summary>
    <pre>{[
      '[演示] 载入预置 PocketFlow 样本；未读取仓库。',
      ...stages.slice(0, visible).map(stage => `[演示] ${stage}`),
      run.status === 'success' ? '[演示] 预置内容已就绪；未调用模型，未写入文件。' : run.status === 'error' ? '[演示] 模拟服务超时，用于展示失败反馈。' : run.status === 'stopped' ? '[演示] 已停止模拟。' : '[演示] 浏览器正在模拟阶段进度。',
    ].join('\n')}</pre>
  </details>
}
