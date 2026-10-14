import { useEffect, useRef, useState } from 'react'
import { openOnline } from '../api/online'
import { getGitHubImport, startGitHubImport } from '../api/projects'
import type { GitHubImportJob } from '../api/projects'

const labels: Record<GitHubImportJob['stage'], string> = {
  queued: '等待后台读取', resolving: '解析仓库与默认分支', downloading: '下载固定 Commit',
  extracting: '校验归档路径并读取源码', scanning: '静态扫描同一快照', saving: '保存快照与项目地图',
  complete: '远程快照已就绪', error: '远程导入失败', interrupted: '后台中断',
}

const wait = (milliseconds: number) => new Promise(resolve => window.setTimeout(resolve, milliseconds))

export function GitHubImportForm() {
  const [url, setUrl] = useState('')
  const [mode, setMode] = useState<'online' | 'snapshot'>('online')
  const [job, setJob] = useState<GitHubImportJob>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true); setError(''); setJob(undefined)
    try {
      if (mode === 'online') {
        const result = await openOnline(url)
        if (alive.current) window.location.hash = `/online/${result.id}`
        return
      }
      let current = await startGitHubImport(url)
      if (alive.current) setJob(current)
      while (current.status === 'queued' || current.status === 'running') {
        await wait(180)
        current = await getGitHubImport(current.id)
        if (alive.current) setJob(current)
      }
      if (current.status === 'succeeded' && current.project_id) {
        if (alive.current) window.location.hash = `/projects/${current.project_id}`
      } else {
        setError(current.error_message || '远程导入未完成，请重试。')
      }
    } catch (error) {
      if (alive.current) setError(error instanceof Error ? error.message : '远程导入失败，请重试。')
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  return <form onSubmit={event => void submit(event)}>
    <div className="online-mode-choice"><label><input type="radio" name="read-mode" checked={mode === 'online'} disabled={busy} onChange={() => setMode('online')} />在线浏览 · 不保存源码</label><label><input type="radio" name="read-mode" checked={mode === 'snapshot'} disabled={busy} onChange={() => setMode('snapshot')} />保存快照 · 可离线重开</label></div>
    <label className="input-label" htmlFor="repository">GitHub 仓库地址</label>
    <div className="input-shell">
      <input id="repository" type="url" required disabled={busy} value={url} onChange={event => setUrl(event.target.value)}
        placeholder="https://github.com/owner/repo" aria-describedby="import-note" />
      <button type="submit" disabled={busy || !url.trim()}>{busy ? '正在读取…' : mode === 'online' ? '在线解析仓库' : '读取公开仓库'}</button>
    </div>
    <p className="home-tip" id="import-note">{mode === 'online' ? '先显示文件目录，再按需读取关键源码。不下载仓库归档，不写入本地快照。' : '固定默认分支的 Commit，下载受限归档并保存快照，可用于历史重开与已登记任务。'}</p>
    {busy && mode === 'online' && <p className="home-tip" role="status">正在确认公开仓库版本并读取文件目录…</p>}
    {job && !error && <div className="github-progress" role="status" aria-live="polite">
      <div><strong>{labels[job.stage]}</strong><span>{job.progress}%</span></div>
      <progress max="100" value={job.progress}>{job.progress}%</progress>
      <p>{job.commit_sha ? `固定版本 ${job.commit_sha.slice(0, 12)}` : '正在向 GitHub 查询不可变版本…'}{job.cache_hit ? ' · 已复用本机源码快照' : ''}</p>
    </div>}
    {error && <p role="alert" className="error-note github-error">{error}</p>}
  </form>
}
