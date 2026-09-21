import { useEffect, useState } from 'react'
import type { Snapshot } from '../api/projects'
import { active, cancelRun, createRun, getLogs, getRun, getRuns } from '../api/runs'
import type { Run, RunParameters } from '../api/runs'

const labels: Record<Run['status'], string> = {queued:'排队中', running:'替身处理中', cancelling:'正在取消', cancelled:'已取消', succeeded:'替身完成', failed:'任务失败', interrupted:'后台中断'}
const stages: Record<string,string> = {queued:'等待启动', preparing:'校验快照', FetchRepo:'读取文件', IdentifyAbstractions:'提取主题', AnalyzeRelationships:'分析关系', OrderChapters:'排列章节', WriteChapters:'写入章节', CombineTutorial:'整理产物', complete:'完成'}

export function TaskPanel({snapshot, onResult}: {snapshot:Snapshot; onResult:(run:Run)=>void}) {
  const [parameters,setParameters]=useState<RunParameters>({snapshot_id:snapshot.id, language:'zh',topics:3,scope:snapshot.folder_cards.some(c=>c.path==='utils')?'utils':'.',scenario:'success'})
  const [history,setHistory]=useState<Run[]>([])
  const [total,setTotal]=useState(0)
  const [selected,setSelected]=useState('')
  const [run,setRun]=useState<Run>()
  const [logs,setLogs]=useState('')
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const [retry,setRetry]=useState(0)
  const [loaded,setLoaded]=useState(false)
  useEffect(()=>{
    const controller=new AbortController()
    getRuns(snapshot.id,0,controller.signal).then(data=>{setHistory(data.items);setTotal(data.total);setSelected(current=>current||data.items[0]?.id||'');setLoaded(true)}).catch(error=>{if(!controller.signal.aborted)setError(error.message)})
    return ()=>controller.abort()
  },[snapshot.id,retry])
  useEffect(()=>{
    if(!selected) return
    const controller=new AbortController()
    let timer: ReturnType<typeof setTimeout>
    let offset=0
    setRun(undefined);setLogs('');setError('')
    async function poll(){
      try {
        const current=await getRun(selected,controller.signal)
        const chunk=await getLogs(selected,offset,controller.signal)
        if(controller.signal.aborted)return
        setRun(current);setHistory(items=>items.map(item=>item.id===current.id?current:item))
        setLogs(text=>(text+chunk.content).slice(-200000)); offset=chunk.next_offset
        if(active(current)||chunk.content)timer=setTimeout(poll,500)
      } catch(error){if(!controller.signal.aborted){setError(error instanceof Error?error.message:'任务读取失败');timer=setTimeout(poll,2000)}}
    }
    void poll()
    return ()=>{controller.abort();clearTimeout(timer)}
  },[selected,retry])
  async function start(){
    setBusy(true);setError('')
    try{const next=await createRun(parameters);setHistory(items=>[next,...items]);setTotal(value=>value+1);setSelected(next.id)}catch(error){setError(error instanceof Error?error.message:'启动失败')}finally{setBusy(false)}
  }
  async function cancel(){
    if(!run)return
    setBusy(true)
    try{setRun(await cancelRun(run.id))}catch(error){setError(error instanceof Error?error.message:'取消失败')}finally{setBusy(false)}
  }
  return <aside className="panel run-panel" id="run-panel" aria-label="真实项目运行窗口"><div className="panel-pad">
    <div className="run-header"><h2 className="small-title">运行窗口</h2><span className="tag amber">替身验证 · 无模型</span></div>
    <h3 className="run-title">生成项目导览</h3><p className="run-subtitle">真实任务进程与本机保存，输出为固定测试内容。当前不发送模型请求。</p>
    <fieldset disabled={busy||active(run)||!loaded}>
      <div className="field"><label htmlFor="task-scope">分析范围</label><select id="task-scope" value={parameters.scope} onChange={e=>setParameters({...parameters,scope:e.target.value})}>{snapshot.folder_cards.map(c=><option key={c.id} value={c.path}>{c.path==='.'?'整个快照':c.path}</option>)}</select></div>
      <div className="field"><label htmlFor="task-language">任务语言</label><select id="task-language" value={parameters.language} onChange={e=>setParameters({...parameters,language:e.target.value as 'zh'|'en'})}><option value="zh">中文</option><option value="en">English</option></select></div>
      <div className="field"><label htmlFor="task-topics">核心主题数</label><select id="task-topics" value={parameters.topics} onChange={e=>setParameters({...parameters,topics:Number(e.target.value)})}>{[1,3,5,10].map(n=><option key={n} value={n}>{n}</option>)}</select></div>
      <div className="field"><label htmlFor="task-scenario">替身验证情境</label><select id="task-scenario" value={parameters.scenario} onChange={e=>setParameters({...parameters,scenario:e.target.value as RunParameters['scenario']})}><option value="success">成功</option><option value="failure">失败</option><option value="slow">慢速（用于取消验证）</option></select></div>
      <button className="primary full-width" onClick={()=>void start()}>启动替身任务</button>
    </fieldset>
    {error&&<p role="alert" className="error-note">{error} <button className="text-button" onClick={()=>{setError('');setRetry(v=>v+1)}}>重新读取</button></p>}
    {run&&<div className={`task-state state-${run.status}`}>
      <p role="status"><strong>{labels[run.status]}</strong> · {stages[run.stage]||run.stage}</p>
      <p className="muted">本次参数：{run.scope} · {run.language} · {run.topics} 个主题</p>
      {run.error&&<p className="error-note">{run.error}</p>}
      {active(run)&&<button className="secondary full-width" disabled={busy||run.status==='cancelling'} onClick={()=>void cancel()}>取消任务</button>}
      {run.status==='succeeded'&&<button className="primary full-width" onClick={()=>onResult(run)}>查看替身结果</button>}
      <details className="run-logs" open><summary>任务日志（持久化）</summary><pre aria-label="后台任务日志">{logs||'等待日志…'}</pre></details>
    </div>}
    <div className="field"><label htmlFor="run-history">运行历史</label><select id="run-history" value={selected} disabled={busy} onChange={e=>setSelected(e.target.value)}><option value="">选择历史任务</option>{history.map(item=><option key={item.id} value={item.id}>{labels[item.status]} · {new Date(item.created_at).toLocaleTimeString()} · {item.id.slice(0,6)}</option>)}</select></div>
    {history.length<total&&<button className="text-button" onClick={()=>void getRuns(snapshot.id,history.length).then(data=>setHistory(items=>[...items,...data.items])).catch(error=>setError(error.message))}>加载更多历史</button>}
    <a className="text-button" href="#/workspace">打开 M1 浏览器演示</a>
    <div className="snapshot-meta"><h3>输入快照</h3><code>{snapshot.id}</code><p>{snapshot.files.length} 个文件 · {snapshot.commit_sha?.slice(0,12)||'上传内容快照'}</p></div>
  </div></aside>
}
