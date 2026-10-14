import type { ArchitectureConnection } from '../api/projects'
import type { ExplorerFile } from '../api/online'

export type ProjectModule = {
  id: string; title: string; lane: number; files: ExplorerFile[]; loaded: number;
  internal: ArchitectureConnection[];
}
export type ModuleLink = { from: string; to: string; references: ArchitectureConnection[] }

// Group the complete directory, not just the files already read. IDs stay stable as
// source batches arrive. Labels describe naming conventions, not verified behavior.
function moduleLocation(path: string): { id: string; title: string; lane: number } {
  const parts = path.split('/'), dirs = parts.slice(0, -1)
  const names: Record<string, [string, number]> = {
    pages: ['页面', 0], views: ['页面', 0], components: ['界面组件', 0], ui: ['界面组件', 0],
    api: ['接口', 1], routes: ['路由', 1], services: ['业务服务', 1], core: ['核心逻辑', 1],
    models: ['数据模型', 1], data: ['数据', 1], db: ['数据存储', 1], storage: ['数据存储', 1],
    utils: ['通用工具', 2], helpers: ['辅助工具', 2], hooks: ['状态与逻辑复用', 1],
    tests: ['测试验证', 2], test: ['测试验证', 2], __tests__: ['测试验证', 2],
    docs: ['项目文档', 2], evidence: ['验证记录', 2], notes: ['项目笔记', 2], 'delivery-tests': ['交付测试', 2], scripts: ['工程脚本', 2], config: ['配置', 2], '.github': ['自动化配置', 2],
  }
  // A parent domain owns its descendants, e.g. docs/api stays documentation.
  const known = dirs.findIndex(dir => Object.hasOwn(names, dir.toLowerCase()))
  if (known >= 0) {
    const [title, lane] = names[dirs[known].toLowerCase()]
    return { id: 'dir:' + dirs.slice(0, known + 1).join('/'), title, lane }
  }
  if (!dirs.length) {
    if (/^(main|index|__main__|cli)\.(py|[cm]?[jt]sx?)$/i.test(path)) return { id: 'root:entry', title: '启动入口', lane: 0 }
    if (/^(flow|workflow)\.(py|[cm]?[jt]sx?)$/i.test(path)) return { id: 'root:flow', title: '流程编排', lane: 1 }
    if (/\.(py|[cm]?[jt]sx?|go|rs|java|rb|php|cpp|c|h)$/i.test(path)) return { id: 'root:source', title: '根目录源码', lane: 1 }
    return { id: 'root:project', title: '项目说明与配置', lane: 2 }
  }
  // Keep application infrastructure together; named domains above remain
  // separate. Unknown nested folders should not turn an overview into a tree.
  const first = dirs[0].toLowerCase()
  const frontend = ['web', 'frontend', 'client'].includes(first)
  const backend = ['server', 'backend'].includes(first)
  const id = dirs.slice(0, ['src', 'app', 'lib', 'packages', 'apps'].includes(first) ? 2 : 1).join('/')
  return { id: 'dir:' + id, title: frontend ? '前端应用' : backend ? '服务端逻辑' : '源码模块', lane: frontend ? 0 : 1 }
}

export function projectOverview(files: ExplorerFile[], links: ArchitectureConnection[]) {
  const byId = new Map<string, ProjectModule>(), byPath = new Map<string, string>()
  for (const file of files) {
    const location = moduleLocation(file.path)
    if (!byId.has(location.id)) byId.set(location.id, { ...location, files: [], loaded: 0, internal: [] })
    const module = byId.get(location.id)!
    module.files.push(file)
    module.loaded += Number(file.loaded)
    byPath.set(file.path, location.id)
  }
  const aggregated = new Map<string, ModuleLink>()
  for (const link of links) {
    if (link.kind === 'contains' || !link.from_id.startsWith('file:') || !link.to_id.startsWith('file:')) continue
    const from = byPath.get(link.from_id.slice(5)), to = byPath.get(link.to_id.slice(5))
    if (!from || !to) continue
    if (from === to) { byId.get(from)!.internal.push(link); continue }
    const key = JSON.stringify([from, to])
    if (!aggregated.has(key)) aggregated.set(key, { from, to, references: [] })
    aggregated.get(key)!.references.push(link)
  }
  const modules = [...byId.values()].sort((a, b) => a.lane - b.lane || a.id.localeCompare(b.id))
  modules.forEach(module => module.files.sort((a, b) => a.path.localeCompare(b.path)))
  return { modules, links: [...aggregated.values()], byPath }
}
export const modulePath = (module: ProjectModule) => module.id.startsWith('root:') ? '根目录' : module.id.slice(4)
