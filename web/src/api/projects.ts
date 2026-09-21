export interface Evidence { id: string; file_path: string; line_start: number; line_end: number; symbol: string | null; excerpt: string }
export interface Card { id: string; path: string; title: string; description: string; claim_type: 'fact' | 'inference' | 'unverified'; inference: string | null; evidence_refs: Evidence[] }
export interface SourceFile { path: string; size_bytes: number; sha256: string }
export interface Snapshot { id: string; revision: string; commit_sha: string | null; created_at: string; files: SourceFile[]; folder_cards: Card[] }
export interface Project { id: string; name: string; source_type: string; source_label: string; created_at: string }
export interface Detail { project: Project; snapshots: Snapshot[] }
export interface ProjectList { items: (Project & { snapshot_count: number })[]; total: number; offset: number; limit: number }
export interface SourceSlice { path: string; sha256: string; line_start: number; line_end: number; total_lines: number; content: string }
export interface ImportResult { detail: Detail; skipped_count: number; note: string }
export interface GitHubImportJob {
  id: string; repository_url: string; canonical_url: string; repository_key: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'interrupted';
  stage: 'queued' | 'resolving' | 'downloading' | 'extracting' | 'scanning' | 'saving' | 'complete' | 'error' | 'interrupted';
  progress: number; commit_sha: string | null; project_id: string | null; snapshot_id: string | null;
  cache_hit: boolean; skipped_count: number; error_code: string | null; error_message: string | null;
  created_at: string; updated_at: string;
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  try {
    const response = await fetch(`/api${path}`, { ...options, signal: options.signal ?? AbortSignal.timeout(60000) })
    const data = await response.json().catch(() => null)
    if (!response.ok) throw new Error(data?.detail?.message ?? (typeof data?.detail === 'string' ? data.detail : `请求失败（${response.status}），请确认后台已启动。`))
    return data as T
  } catch (error) {
    if (error instanceof TypeError) throw new Error('无法连接后台，请按 README 启动服务后重试。')
    throw error
  }
}
export const projects = (offset = 0, signal?: AbortSignal) => request<ProjectList>(`/projects?offset=${offset}`, { signal })
export const project = (id: string, signal?: AbortSignal) => request<Detail>(`/projects/${encodeURIComponent(id)}`, { signal })
export const source = (id: string, path: string, start: number, signal?: AbortSignal) => request<SourceSlice>(`/snapshots/${id}/source?${new URLSearchParams({ path, start: String(start), limit: '80' })}`, { signal })
export const importBuiltin = () => request<ImportResult>('/projects/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source: 'builtin' }) })
export const startGitHubImport = (repositoryUrl: string) => request<GitHubImportJob>('/github-imports', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repository_url: repositoryUrl }),
})
export const getGitHubImport = (id: string, signal?: AbortSignal) => request<GitHubImportJob>(`/github-imports/${encodeURIComponent(id)}`, { signal })

const excludedDirs = new Set(['.git', '.hg', '.svn', 'node_modules', '.venv', 'venv', 'dist', 'build', '.next', '__pycache__', '.pytest_cache', 'coverage', '.ssh', '.aws', 'var'])
const excludedNames = new Set(['.ds_store', '.npmrc', '.pypirc', 'credentials', 'credentials.json', 'secrets.json', 'id_rsa', 'id_ed25519'])
const extensions = new Set(['py', 'md', 'txt', 'rst', 'json', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'js', 'jsx', 'ts', 'tsx', 'css', 'html', 'sql', 'sh', 'gitignore', 'lock', 'csv'])
function allowed(path: string) {
  const parts = path.toLowerCase().split('/')
  const name = parts.at(-1)!
  return !parts.slice(0, -1).some(p => excludedDirs.has(p)) && !excludedNames.has(name) && !name.startsWith('.env') && !/secret|credential|\.(pem|key|p12|pfx|sqlite3|db)$/.test(name)
    && (extensions.has(name.split('.').at(-1)!) || ['license', 'readme', 'dockerfile', 'makefile', '.gitignore'].includes(name))
}
export async function importDirectory(selected: File[], progress: (message: string) => void): Promise<ImportResult> {
  if (!selected.length) throw new Error('目录为空或未选择文件，请选择包含源码的目录。')
  const retained = selected.filter(file => allowed(file.webkitRelativePath || file.name))
  if (!retained.length) throw new Error('过滤后没有可扫描的文本文件，请选择包含源码的目录。')
  if (retained.length > 500 || retained.reduce((sum, f) => sum + f.size, 0) > 8 * 1024 * 1024) throw new Error('项目超过 500 个文件或 8 MiB 限制，请缩小目录。')
  if (retained.some(f => f.size > 1024 * 1024)) throw new Error('单文件超过 1 MiB 限制，请移除大文件后重试。')
  const files = []
  for (const file of retained) {
    const path = file.webkitRelativePath ? file.webkitRelativePath.split('/').slice(1).join('/') : file.name
    const bytes = new Uint8Array(await file.arrayBuffer())
    let binary = ''
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192))
    files.push({ path, content_base64: btoa(binary) })
    progress(`正在读取文件 ${files.length} / ${retained.length}…`)
  }
  progress('正在上传、静态扫描并保存快照…')
  const result = await request<ImportResult>('/projects/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source: 'upload', name: selected[0].webkitRelativePath.split('/')[0] || '本地项目', files }) })
  return { ...result, skipped_count: result.skipped_count + selected.length - retained.length }
}
