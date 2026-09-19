import { useState } from 'react'
import { snapshot, sourceUrl, stages } from '../demo/pocketflow'
import type { FolderCard, SourceFile } from '../types'

export function FolderDetail({ folder }: { folder: FolderCard }) {
  const [source, setSource] = useState<SourceFile | null>(null)
  return <>
    <div className="main-top">
      <div className="breadcrumbs">PocketFlow / <strong>{folder.id === 'root' ? '项目总览' : folder.id}</strong></div>
      <div className="folder-title-row"><h2>{folder.title}</h2><span className="tag">源码线索</span></div>
      <p className="folder-description">{folder.description}</p>
    </div>
    <div className="main-content">
      <div className="section-heading"><h3>关键文件与入口</h3><span className="section-note">点击查看源码片段</span></div>
      {folder.files.map(file => <button key={file.path} className={`file-card ${source?.path === file.path ? 'selected' : ''}`} aria-expanded={source?.path === file.path} aria-controls="source-preview" onClick={() => setSource(source?.path === file.path ? null : file)}>
        <b>{file.path}</b><small>{file.purpose} ↗</small>
      </button>)}
      <div id="source-preview">
        {source && <section className="source-preview" aria-label="源码片段">
          <div className="section-heading"><h3>{source.path}:{source.line}</h3><button className="text-button" onClick={() => setSource(null)}>收起源码</button></div>
          <pre aria-label="带行号的预置源码">{source.excerpt.split('\n').map((line, index) => <span className="code-line" key={index}><span className="line-number" aria-hidden="true">{source.line + index}</span><code>{line || ' '}</code></span>)}</pre>
          <a href={sourceUrl(source)} target="_blank" rel="noreferrer">在 GitHub 查看这个版本 ↗</a>
        </section>}
      </div>
      <div className="evidence-card"><b>解释依据 · {snapshot.slice(0, 7)}</b><p>说明与片段按固定版本人工整理，当前页面未自动扫描源码；这些线索不代表实际运行验证。</p></div>
      <div className="next-reading"><span className="mini-label">建议下一步</span><p>{folder.next}</p></div>
      <div className="divider" />
      <div className="section-heading"><h3>项目生成流程</h3><span className="section-note">6 个阶段 · 设计示意</span></div>
      <ol className="flow-grid">{stages.map((stage, index) => <li className="flow-card" key={stage}><span className="flow-num">0{index + 1}</span><b>{stage}</b></li>)}</ol>
    </div>
  </>
}
