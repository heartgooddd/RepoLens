import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import { artifactLink, getArtifact } from '../api/runs'
import type { Run } from '../api/runs'

export function TaskResult({run,onBack}:{run:Run;onBack:()=>void}) {
  const real=run.mode==='pocketflow'
  const usage=run.model_usage?JSON.parse(run.model_usage) as {call_count:number;cost_usd:number|null}:null
  const files=run.artifacts.filter(a=>a.path.endsWith('.md'))
  const [selected,setSelected]=useState(files.find(a=>a.path.endsWith('/index.md'))?.id||files[0]?.id||'')
  const [content,setContent]=useState('')
  const [claims,setClaims]=useState<Array<{description:string;claim_type:string;note:string;references?:Array<{file_path:string;line_start:number|null;line_end:number|null;quote:string;matched:boolean}>}>>([])
  const [error,setError]=useState('')
  useEffect(()=>{
    const controller=new AbortController();setContent('');setError('')
    if(selected)getArtifact(run.id,selected,controller.signal).then(data=>setContent(data.content)).catch(error=>{if(!controller.signal.aborted)setError(error.message)})
    const artifact=run.artifacts.find(a=>a.path.endsWith('/verified-claims.json'))
    if(artifact)getArtifact(run.id,artifact.id,controller.signal).then(data=>setClaims(JSON.parse(data.content))).catch(error=>{if(!controller.signal.aborted)setError(error.message)})
    return ()=>controller.abort()
  },[run.id,run.artifacts,selected])
  return <div className="main-content task-result">
    <button className="text-button" onClick={onBack}>返回文件夹说明</button>
    <h2>{real?'PocketFlow 生成结果':'替身验证结果'}</h2><p className="muted">任务 {run.id} · {run.scope} · {run.language} · {run.topics} 个主题<br/>{real?`实际模型：${run.model_name}。生成说明属于模型推断，请结合源码核对。`:'固定输出，不代表真实模型分析或项目运行成功。'}</p>
    {usage&&<p className="muted">模型调用 {usage.call_count} 次 · API报告费用 {usage.cost_usd===null?'未返回':`$${usage.cost_usd.toFixed(8)}`}</p>}
    <nav className="chapter-nav" aria-label="任务产物">{files.map(file=><button className={selected===file.id?'active':''} key={file.id} onClick={()=>setSelected(file.id)}>{file.path.split('/').at(-1)}</button>)}</nav>
    {error?<p role="alert" className="error-note">{error}</p>:<article className="generated-markdown" aria-label="生成 Markdown 预览">
      <Markdown skipHtml components={{
        img:({alt})=><span className="muted">[图片未加载：{alt}]</span>,
        a:({href,children})=>{
          const selectedFile=files.find(a=>a.id===selected)
          const base=selectedFile?.path.slice(0,selectedFile.path.lastIndexOf('/')+1)||''
          let relative=''
          try{relative=decodeURIComponent((href||'').split('#')[0]).replace(/^\.\//,'')}catch{/* invalid link remains disabled */}
          const local=files.find(a=>a.path===base+relative)
          return local?<button className="text-button" onClick={()=>setSelected(local.id)}>{children}</button>:<span>{children}（外部链接未启用）</span>
        },
      }}>{content}</Markdown>
    </article>}
    {selected&&<a className="secondary" href={artifactLink(run.id,selected)} download>下载当前 Markdown</a>}
    <div className="evidence-card"><b>职责补充 · {real?'模型引用校验':'替身引用校验'}</b>{claims.map((claim,i)=><div key={i}><p>{claim.claim_type==='unverified'?'待核实':'推断'}：{claim.description} {claim.note}</p>{claim.references?.map((ref,j)=><details key={j}><summary>{ref.file_path} · L{ref.line_start}–{ref.line_end} · {ref.matched?'引用匹配':'待核实'}</summary><pre>{ref.quote}</pre></details>)}</div>)}</div>
  </div>
}
