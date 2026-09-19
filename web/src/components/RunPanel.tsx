import type { RunParameters, RunState } from '../types'
import { RunLogs, RunProgress } from './RunProgress'

interface Props {
  parameters: RunParameters
  run: RunState
  onChange: (parameters: RunParameters) => void
  onStart: () => void
  onStop: () => void
  onReset: () => void
  onResult: () => void
  onRetry: () => void
}

const statusLabels = { idle: '尚未开始', running: '模拟处理中', success: '演示完成', error: '演示失败', stopped: '演示已停止' }

export function RunPanel({ parameters, run, onChange, onStart, onStop, onReset, onResult, onRetry }: Props) {
  const running = run.status === 'running'
  return <aside className="panel run-panel" id="run-panel" aria-label="运行窗口">
    <div className="panel-pad">
      <div className="run-header"><h2 className="small-title">运行窗口</h2><span className="tag amber">仅演示</span></div>
      <h3 className="run-title">生成项目导览</h3>
      <p className="run-subtitle">在这里体验参数、进度与结果。全部由浏览器模拟，不调用后台或模型。</p>
      <form onSubmit={event => { event.preventDefault(); onStart() }}>
        <fieldset disabled={running}>
          <legend className="sr-only">演示运行参数</legend>
          <div className="field"><span className="field-label">分析来源</span><div className="value">PocketFlow · 固定演示样本</div></div>
          <div className="field"><label htmlFor="language">输出语言</label><select id="language" value={parameters.language} onChange={event => onChange({ ...parameters, language: event.target.value as RunParameters['language'] })}><option value="zh">中文</option><option value="en">English</option></select></div>
          <div className="field"><label htmlFor="topics">最大主题数</label><select id="topics" value={parameters.topics} onChange={event => onChange({ ...parameters, topics: Number(event.target.value) as RunParameters['topics'] })}><option value="3">3 个 · 快速了解</option><option value="5">5 个 · 详细浏览</option></select></div>
          <div className="field"><label htmlFor="scenario">演示情境</label><select id="scenario" value={parameters.scenario} onChange={event => onChange({ ...parameters, scenario: event.target.value as RunParameters['scenario'] })}><option value="success">成功 · 查看预置结果</option><option value="failure">失败 · 模拟服务超时</option></select></div>
          <button className="primary run-button" type="submit">{running ? '正在模拟…' : run.status === 'idle' ? '开始演示运行 →' : '重新演示 →'}</button>
        </fieldset>
      </form>
      {running && <button className="secondary full-width" onClick={onStop}>停止演示</button>}
      <p className="run-foot">不消耗模型额度；刷新或返回输入页会清空本次演示。</p>
    </div>
    <div className={`status status-${run.status}`}>
      <p className="status-line" role="status"><span aria-hidden="true" />{statusLabels[run.status]}</p>
      <RunProgress run={run} />
      {run.status === 'success' && <button className="secondary full-width" onClick={onResult}>查看演示结果 ↗</button>}
      {run.status === 'error' && <><p className="error-note">模拟在“分析关系”阶段超时。这是预设失败情境，可切换为成功演示继续体验。</p><button className="secondary full-width" onClick={onRetry}>重试成功演示</button></>}
      {run.status === 'stopped' && <p className="muted">已取消浏览器计时。可以调整参数后重新开始。</p>}
      <RunLogs run={run} />
      {run.status !== 'idle' && !running && <button className="text-button reset-button" onClick={onReset}>清空本次演示</button>}
    </div>
  </aside>
}
