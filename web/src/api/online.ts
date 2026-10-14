import { request } from './projects'
import type { Architecture, SourceSlice } from './projects'

export interface ExplorerFile { path: string; size_bytes: number; loaded: boolean }
export interface OnlineProject {
  id: string; name: string; repository_url: string; commit_sha: string;
  files: ExplorerFile[]; excluded_count: number; loaded_count: number;
  architecture: Architecture; warnings: string[];
}
export const openOnline = (repository_url: string, signal?: AbortSignal) => request<OnlineProject>('/online', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repository_url }), signal,
})
export const onlineProject = (id: string, signal?: AbortSignal) => request<OnlineProject>(`/online/${id}`, { signal })
export const readOnline = (id: string, paths: string[] = []) => request<OnlineProject>(`/online/${id}/read`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paths }),
})
export const onlineSource = (id: string, path: string, start: number, signal?: AbortSignal) => request<SourceSlice>(
  `/online/${id}/source?${new URLSearchParams({ path, start: String(start), limit: '80' })}`, { signal })
