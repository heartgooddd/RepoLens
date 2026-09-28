import { useState } from 'react'
import { folders, snapshot } from '../demo/pocketflow'
import type { FolderId, RunParameters } from '../types'
import { FolderMap } from '../components/FolderMap'
import { FolderDetail } from '../components/FolderDetail'
import { RunPanel } from '../components/RunPanel'
import { ResultView } from '../components/ResultView'
import { DemoOverview } from '../components/ProjectVisuals'
import { useDemoRun } from '../hooks/useDemoRun'

export function WorkspacePage() {
  const [selected, setSelected] = useState<FolderId>('root')
  const [view, setView] = useState<'folder' | 'result'>('folder')
  const [runExpanded, setRunExpanded] = useState(false)
  const [parameters, setParameters] = useState<RunParameters>({ language: 'zh', topics: 3, scenario: 'success' })
  const { run, start, stop, reset } = useDemoRun()
  const folder = folders.find(item => item.id === selected)!
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  const selectFolder = (id: FolderId, jump = false) => {
    setSelected(id); setView('folder')
    if (jump || window.matchMedia('(max-width: 760px)').matches) scrollTo('folder-detail')
  }

  return <main className="wrap" id="main-content" tabIndex={-1}>
    <div className="page-heading">
      <div><div className="eyebrow">PROJECT WORKSPACE / DEMO</div></div>
      <div className="source-pill"><span className="dot" /><strong>演示样本</strong><span>· {snapshot.slice(0, 7)}</span></div>
    </div>
    <DemoOverview selected={selected} onSelect={id => selectFolder(id, true)} />
    <nav className="mobile-jump" aria-label="工作台区域导航"><button onClick={() => scrollTo('folder-map')}>文件夹</button><button onClick={() => scrollTo('folder-detail')}>解释与结果</button><button onClick={() => { setRunExpanded(true); requestAnimationFrame(() => scrollTo('run-section')) }}>运行窗口</button></nav>
    <div className="workspace focus-workspace">
      <FolderMap selected={selected} onSelect={id => selectFolder(id)} />
      <section className="panel main-panel" id="folder-detail" aria-label="项目说明与结果">
        <nav className="view-switch" aria-label="详情视图"><button aria-pressed={view === 'folder'} onClick={() => setView('folder')}>位置与源码</button><button aria-pressed={view === 'result'} onClick={() => setView('result')}>运行结果{run.status === 'success' && <span className="result-dot" />}</button></nav>
        {view === 'folder' ? <FolderDetail key={selected} folder={folder} onSelect={id => selectFolder(id)} /> : <ResultView key={run.status} run={run} />}
      </section>
    </div>
    <section className="run-drawer" id="run-section"><button type="button" className="run-drawer-trigger" aria-expanded={runExpanded} onClick={() => setRunExpanded(value => !value)}><span><small>04 / 可选体验</small><strong>试着生成项目导览</strong><em>理解项目结构后，再体验参数、进度与结果</em></span><b>{runExpanded ? '收起 ↑' : '展开运行体验 ↓'}</b></button>
      {runExpanded && <RunPanel parameters={parameters} run={run} onChange={setParameters} onStart={() => start(parameters)} onStop={stop} onReset={reset} onResult={() => { setView('result'); scrollTo('folder-detail') }} onRetry={() => { const next: RunParameters = { ...parameters, scenario: 'success' }; setParameters(next); start(next) }} />}
    </section>
    <p className="footnote">演示数据 · 说明与源码片段按固定版本整理 · 表单、进度和结果均为浏览器内演示。</p>
  </main>
}
