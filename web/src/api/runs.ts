import { request } from './projects'
export interface Artifact { id: string; run_id: string; path: string; size_bytes: number; sha256: string }
export interface Run { id: string; snapshot_id: string; mode: 'stub' | 'pocketflow'; status: 'queued' | 'running' | 'cancelling' | 'cancelled' | 'succeeded' | 'failed' | 'interrupted'; stage: string; language: string; topics: number; scope: string; scenario: string; created_at: string; model_provider: string | null; model_name: string | null; model_usage: string | null; error: string | null; exit_code: number | null; artifacts: Artifact[] }
export interface RunParameters { mode?: 'stub' | 'pocketflow'; snapshot_id: string; language: 'zh' | 'en'; topics: number; scope: string; scenario: 'success' | 'failure' | 'slow' }
export interface Logs { offset: number; next_offset: number; content: string; finished: boolean }
export const active = (run?: Run) => !!run && ['queued', 'running', 'cancelling'].includes(run.status)
export const getRuns = (snapshot: string, offset = 0, signal?: AbortSignal) => request<{items: Run[]; total: number}>(`/runs?${new URLSearchParams({snapshot_id:snapshot,offset:String(offset)})}`, {signal})
export const getRun = (id: string, signal?: AbortSignal) => request<Run>(`/runs/${id}`, {signal})
export const createRun = (parameters: RunParameters) => request<Run>('/runs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(parameters)})
export const cancelRun = (id: string) => request<Run>(`/runs/${id}/cancel`, {method:'POST'})
export const getLogs = (id: string, offset: number, signal?: AbortSignal) => request<Logs>(`/runs/${id}/logs?offset=${offset}`, {signal})
export const getArtifact = (runId: string, id: string, signal?: AbortSignal) => request<{path:string;content:string;mode:string}>(`/runs/${runId}/artifacts/${id}`, {signal})
export const artifactLink = (runId: string, id: string) => `/api/runs/${runId}/artifacts/${id}?download=true`

export interface RunnerConfiguration {
  real_enabled: boolean; real_ready: boolean;
  model: { provider?: string; model?: string; api_key_configured: boolean; configuration_complete: boolean; missing: string[] };
}
export const getRunnerConfiguration = (signal?: AbortSignal) => request<RunnerConfiguration>('/runner', {signal})
export function runLabel(run: Run): string {
  const labels = {queued:'排队中',running:run.mode==='stub'?'替身处理中':'真实生成中',cancelling:'正在取消',cancelled:'已取消',succeeded:run.mode==='stub'?'替身完成':'真实生成完成',failed:'任务失败',interrupted:'后台中断'}
  return labels[run.status]
}
