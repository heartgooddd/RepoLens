import { test, expect } from '@playwright/test'
import { modulePath, projectOverview } from '../src/components/project-overview'
import type { ArchitectureConnection } from '../src/api/projects'

const files = (paths: string[], loaded = false) => paths.map(path => ({ path, loaded, size_bytes: 10 }))
const edge = (from: string, to: string): ArchitectureConnection => ({
  from_id: `file:${from}`, to_id: `file:${to}`, kind: 'imports', label: 'imports',
  evidence: [{ file_path: from, line_start: 2, line_end: 2, excerpt: `import ${to}` }],
})

test('full directory groups stay stable as source arrives, including nested documentation', () => {
  const paths = ['web/src/pages/Home.tsx', 'web/src/api/client.ts', 'docs/api/guide.md', 'server/app/main.py', 'README.md']
  const before = projectOverview(files(paths), [])
  const after = projectOverview(files(paths, true), [edge(paths[0], paths[1])])
  expect(before.modules.map(module => module.id)).toEqual(after.modules.map(module => module.id))
  expect(before.modules.reduce((n, module) => n + module.files.length, 0)).toBe(paths.length)
  expect(before.modules.every(module => module.loaded === 0)).toBe(true)
  expect(after.modules.every(module => module.loaded === module.files.length)).toBe(true)
  expect(before.modules.find(module => modulePath(module) === 'docs')?.files[0].path).toBe('docs/api/guide.md')
})

test('module arrows aggregate evidence, preserve direction and exclude containment and unavailable targets', () => {
  const paths = ['src/pages/A.tsx', 'src/pages/B.tsx', 'src/api/client.ts']
  const ab = edge(paths[0], paths[2]), bb = edge(paths[1], paths[2]), reverse = edge(paths[2], paths[0])
  const result = projectOverview(files(paths, true), [ab, bb, reverse, edge(paths[0], paths[1]), edge(paths[0], 'absent.ts'), { ...ab, kind: 'contains' }])
  expect(result.links).toHaveLength(2)
  expect(result.links[0].references).toEqual([ab, bb])
  expect(result.links[1].from).toBe(result.links[0].to)
  expect(result.links[1].to).toBe(result.links[0].from)
  expect(result.modules.find(module => modulePath(module) === 'src/pages')?.internal).toHaveLength(1)
})

test('unknown and special directory names do not collide with root modules or object prototypes', () => {
  const paths = ['main.py', '@entry/file.py', 'root:entry/file.py', 'constructor/file.py', '__proto__/file.py']
  const result = projectOverview(files(paths), [])
  expect(result.modules).toHaveLength(5)
  expect(result.byPath.size).toBe(paths.length)
  expect(new Set(result.byPath.values()).size).toBe(5)
  expect(projectOverview([], []).modules).toEqual([])
})
