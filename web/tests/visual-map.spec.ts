import { expect, test } from '@playwright/test'

const projectId = '22222222-2222-4222-8222-222222222222'
const snapshotId = '33333333-3333-4333-8333-333333333333'
const pocketFlowCommit = '05b24cbbb0fe409c5e23c9791f0342f07524ffdc'
const evidence = { id: '55555555-5555-4555-8555-555555555555', file_path: 'README.md', line_start: 1, line_end: 3, symbol: null, excerpt: '# RepoLens\n\n开源 AI 项目拆解与学习平台工作区。' }

test('演示用简介、六站加工线和文件夹在体系中的位置解释项目', async ({ page }) => {
  await page.goto('/#/workspace')
  await expect(page.getByRole('heading', { name: 'PocketFlow 项目地图' })).toBeVisible()
  await expect(page.locator('.project-identity')).toContainText('代码库教程生成器')
  await expect(page.locator('.stage-track li')).toHaveCount(6)
  await expect(page.locator('.stage-track')).toContainText('简介＋关系线')
  await expect(page.locator('.stage-track')).toContainText('index.md＋各章')
  await page.getByRole('button', { name: /utils\/ · 工具间/ }).click()
  await expect(page.locator('.story-role')).toContainText('抓取 GitHub 或本地文件')
  await expect(page.locator('.story-role')).toContainText('由 nodes.py 调用')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('真实仓库按源码证据分层并能沿模块引用进入详情', async ({ page }) => {
  const folder = (path: string, id: string) => ({ id, snapshot_id: snapshotId, path, title: path === '.' ? '项目根目录' : path, description: '静态扫描目录。', claim_type: 'fact', inference: null, evidence_refs: path === '.' ? [evidence] : [] })
  const module = (id: string, title: string, kind: string, path: string, confidence: string) => ({ id, title, role: `${title} 保留的源码位置。`, kind, paths: [path], evidence: [], confidence, file_count: 1 })
  await page.route(`**/api/projects/${projectId}`, route => route.fulfill({ json: {
    project: { id: projectId, name: 'RepoLens', source_type: 'github', source_label: 'https://github.com/heartgooddd/RepoLens', created_at: '2026-09-28T00:00:00Z' },
    snapshots: [{ id: snapshotId, revision: 'git:' + 'a'.repeat(40), commit_sha: 'a'.repeat(40), created_at: '2026-09-28T00:00:00Z',
      files: [
        { path: 'README.md', size_bytes: 50, sha256: 'a'.repeat(64) },
        { path: 'web/src/App.tsx', size_bytes: 60, sha256: 'b'.repeat(64) },
        { path: 'web/src/Other.tsx', size_bytes: 30, sha256: 'f'.repeat(64) },
        { path: 'web/src/components/Card.tsx', size_bytes: 55, sha256: 'c'.repeat(64) },
        { path: 'server/app/main.py', size_bytes: 70, sha256: 'd'.repeat(64) },
        { path: 'docs/guide.md', size_bytes: 80, sha256: 'e'.repeat(64) },
      ],
      folder_cards: [folder('.', '1'), folder('web', '2'), folder('web/src', '3'), folder('web/src/components', '4'), folder('server', '5'), folder('server/app', '6'), folder('docs', '7')],
    }],
  } }))
  await page.route(`**/api/snapshots/${snapshotId}/architecture`, route => route.fulfill({ json: {
    snapshot_id: snapshotId, project_name: 'RepoLens', summary: '让新人看懂一个开源项目的结构和源码关系。',
    summary_source: { file_path: 'README.md', line_start: 3, line_end: 3, excerpt: '让新人看懂一个开源项目的结构和源码关系。' },
    modules: [
      module('folder:.', '项目根目录', 'other', '.', 'unknown'),
      module('folder:web', 'web', 'interface', 'web', 'inferred'),
      module('folder:web/src', 'web/src', 'interface', 'web/src', 'inferred'),
      module('folder:web/src/components', 'web/src/components', 'interface', 'web/src/components', 'inferred'),
      module('folder:server', 'server', 'core', 'server', 'inferred'),
      module('folder:docs', 'docs', 'docs', 'docs', 'inferred'),
      module('file:web/src/App.tsx', 'web/src/App.tsx', 'entry', 'web/src/App.tsx', 'observed'),
      module('file:web/src/Other.tsx', 'web/src/Other.tsx', 'interface', 'web/src/Other.tsx', 'observed'),
      module('file:web/src/components/Card.tsx', 'web/src/components/Card.tsx', 'interface', 'web/src/components/Card.tsx', 'observed'),
    ],
    connections: [{ from_id: 'file:web/src/App.tsx', to_id: 'file:web/src/components/Card.tsx', kind: 'imports', label: '源码导入', evidence: [{ file_path: 'web/src/App.tsx', line_start: 1, line_end: 1, excerpt: "import { Card } from './components/Card'" }] }],
    coverage: { retained_files: 6, inspected_source_files: 4, folders: 7, resolved_imports: 1, unresolved_local_imports: 0 }, limitations: [],
  } }))
  await page.route(`**/api/snapshots/${snapshotId}/source**`, route => {
    const path = new URL(route.request().url()).searchParams.get('path') || 'README.md'
    return route.fulfill({ json: { path, sha256: 'b'.repeat(64), line_start: 1, line_end: 2, total_lines: 2, content: 'export const App = () => <Card />' } })
  })
  await page.goto(`/#/projects/${projectId}`)
  await page.locator(".snapshot-legacy > summary").click()
  await expect(page.locator('.project-identity')).toContainText('让新人看懂一个开源项目的结构和源码关系。')
  await expect(page.locator('.architecture-module')).toHaveCount(5)
  await expect(page.locator('.reading-trail')).toContainText('web/src/App.tsx')
  await expect(page.locator('.reading-trail')).toContainText('web/src/components/Card.tsx')
  await expect(page.locator('.architecture-relations')).toContainText('web/src/App.tsx')
  await expect(page.locator('.architecture-relations')).toContainText('web/src/components/Card.tsx')
  await page.getByRole('button', { name: '查看 web 的作用' }).click()
  await expect(page.locator('.story-role')).toContainText('可能负责用户界面或接口层')
  await expect(page.locator('.snapshot-neighbors')).toContainText('web/src/App.tsx')
  await expect(page.locator('.source-preview')).toHaveCount(0)
  await page.locator('.zone-interface .zone-more').click()
  await expect(page.locator('.architecture-relations .relation-line')).toHaveCount(1)
  await page.getByRole('button', { name: '查看 web/src 的作用' }).click()
  await expect(page.locator('.snapshot-neighbors')).toContainText('web/src/components')
  await page.locator('.architecture-relations').getByRole('button', { name: 'web/src/App.tsx' }).click()
  await expect(page.locator('.story-role')).toContainText('web/src/App.tsx 的作用')
  await expect(page.locator('.source-preview')).toContainText('App.tsx')
  await page.locator('.repository-files').getByRole('button', { name: /Other.tsx/ }).click()
  await expect(page.locator('.story-role')).toContainText('web/src/Other.tsx 的作用')
  await expect(page.locator('.source-preview')).toContainText('Other.tsx')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('固定 PocketFlow GitHub 版本复用六阶段图并能定位真实源码', async ({ page }) => {
  const files = ['main.py', 'flow.py', 'nodes.py', 'utils/crawl_local_files.py', 'docs/design.md'].map(path => ({ path, size_bytes: 80, sha256: 'a'.repeat(64) }))
  const folder = (path: string, id: string) => ({ id, snapshot_id: snapshotId, path, title: path, description: '静态扫描目录。', claim_type: 'unverified', inference: null, evidence_refs: [] })
  await page.route(`**/api/projects/${projectId}`, route => route.fulfill({ json: {
    project: { id: projectId, name: 'PocketFlow-Tutorial-Codebase-Knowledge', source_type: 'github', source_label: 'https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge', created_at: '2026-09-28T00:00:00Z' },
    snapshots: [{ id: snapshotId, revision: `git:${pocketFlowCommit}`, commit_sha: pocketFlowCommit, created_at: '2026-09-28T00:00:00Z', files,
      folder_cards: [folder('.', '1'), folder('utils', '2'), folder('docs', '3')] }],
  } }))
  await page.route(`**/api/snapshots/${snapshotId}/source**`, route => {
    const path = new URL(route.request().url()).searchParams.get('path') || 'main.py'
    return route.fulfill({ json: { path, sha256: 'a'.repeat(64), line_start: 1, line_end: 2, total_lines: 2, content: 'def main():\n    return 42' } })
  })
  await page.goto(`/#/projects/${projectId}`)
  await page.locator(".snapshot-legacy > summary").click()
  await expect(page.locator('.project-identity')).toContainText('基于 Pocket Flow 框架构建')
  await expect(page.locator('.stage-track li')).toHaveCount(6)
  await page.getByRole('button', { name: '查看 main.py 的作用' }).click()
  await expect(page.getByRole('heading', { name: 'main.py / 程序入口' })).toBeVisible()
  await expect(page.locator('.story-role')).toContainText('交给 flow.py 的运行上下文')
  await expect(page.locator('.repository-files').getByRole('button', { name: /main.py/ })).toHaveAttribute('aria-pressed', 'true')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
