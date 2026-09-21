import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import { artifactLink, getArtifact } from '../api/runs'
import type { Run } from '../api/runs'

export function TaskResult({run,onBack}:{run:Run;onBack:()=>void}) {
  const files=run.artifacts.filter(a=>a.path.endsWith('.md'))
  const [selected,setSelected]=useState(files.find(a=>a.path.endsWith('/index.md'))?.id||files[0]?.id||'')
  const [content,setContent]=useState('')
  const [claims,setClaims]=useState<Array<{description:string;claim_type:string;note:string}>>([])
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
    <h2>替身验证结果</h2><p className="muted">任务 {run.id} · {run.scope} · {run.language} · {run.topics} 个主题<br/>固定输出，不代表真实模型分析或项目运行成功。</p>
    <nav className="chapter-nav" aria-label="任务产物">{files.map(file=><button className={selected===file.id?'active':''} key={file.id} onClick={()=>setSelected(file.id)}>{file.path.split('/').at(-1)}</button>)}</nav>
    {error?<p role="alert" className="error-note">{error}</p>:<article className="generated-markdown" aria-label="生成 Markdown 预览">
      <Markdown skipHtml components={{
        img:({alt})=><span className="muted">[图片未加载：{alt}]</span>,
        a:({href,children})=>{
          const selectedFile=files.find(a=>a.id===selected)
          const base=selectedFile?.path.slice(0,selectedFile.path.lastIndexOf('/')+1)||''
          const local=files.find(a=>a.path===base+(href||'').split('#')[0])
          return local?<button className="text-button" onClick={()=>setSelected(local.id)}>{children}</button>:<span>{children}（外部链接未启用）</span>
        },
      }}>{content}</Markdown>
    </article>}
    {selected&&<a className="secondary" href={artifactLink(run.id,selected)} download>下载当前 Markdown</a>}
    <div className="evidence-card"><b>职责补充 · 替身引用校验</b>{claims.map((claim,i)=><p key={i}>{claim.claim_type==='unverified'?'待核实':'推断'}：{claim.description} {claim.note}</p>)}</div>
  </div>
}
