import { useState } from 'react'
import { getDemoChapters, snapshot } from '../demo/pocketflow'
import type { RunState } from '../types'
import { RunLogs, RunProgress } from './RunProgress'

export function ResultView({ run }: { run: RunState }) {
  const [chapter, setChapter] = useState(0)
  if (run.status !== 'success') return <div className="main-content result-state">
    <span className="state-symbol" aria-hidden="true">{run.status === 'error' ? '!' : run.status === 'running' ? '◌' : '◇'}</span>
    <h2>{run.status === 'idle' ? '还没有演示结果' : run.status === 'running' ? '演示正在进行' : run.status === 'error' ? '这次演示未完成' : '演示已停止'}</h2>
    <p className="muted">{run.status === 'idle' ? '在运行窗口选择参数并开始演示，完成后这里会展示预置导览。' : run.status === 'error' ? '模拟服务在分析关系阶段超时。可以在运行窗口重试成功情境。' : run.status === 'stopped' ? '本次没有结果，可以调整参数后重新演示。' : '浏览器正在模拟六个处理阶段，没有发起真实模型请求。'}</p>
    <a className="secondary" href="#run-panel" onClick={event => { event.preventDefault(); document.getElementById('run-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }}>前往运行窗口 ↓</a>
    {run.status !== 'idle' && <><RunProgress run={run} /><RunLogs run={run} /></>}
  </div>

  const chapters = getDemoChapters(run.parameters)
  const active = Math.min(chapter, chapters.length - 1)
  return <>
    <div className="main-top">
      <div className="eyebrow">TUTORIAL PREVIEW / DEMO</div>
      <div className="folder-title-row result-title"><h2>项目导览</h2><span className="tag amber">预置演示结果</span></div>
      <p className="folder-description">以下为人工编写的预置章节，仅随表单选择切换展示，未实际生成教程或写入文件。</p>
      <dl className="result-meta"><div><dt>语言</dt><dd>{run.parameters.language === 'zh' ? '中文' : 'English'}</dd></div><div><dt>主题</dt><dd>{chapters.length} 个</dd></div><div><dt>来源版本</dt><dd>{snapshot.slice(0, 7)}</dd></div></dl>
    </div>
    <div className="main-content">
      <nav className="chapter-nav" aria-label="演示章节">{chapters.map(([title], index) => <button key={title} className={active === index ? 'active' : ''} aria-pressed={active === index} onClick={() => setChapter(index)}>0{index + 1} / {title}</button>)}</nav>
      <article className="chapter" lang={run.parameters.language === 'zh' ? 'zh-CN' : 'en'}><span className="eyebrow">CHAPTER 0{active + 1}</span><h3>{chapters[active][0]}</h3><p>{chapters[active][1]}</p></article>
      <div className="evidence-card"><b>继续核对源码</b><p>切回“文件夹说明”查看具体文件和行号。演示完成不表示代码已经运行验证。</p></div>
      <RunLogs run={run} />
    </div>
  </>
}
