import { test, expect } from '@playwright/test'

const jobId = '11111111-1111-4111-8111-111111111111'
const projectId = '22222222-2222-4222-8222-222222222222'
const snapshotId = '33333333-3333-4333-8333-333333333333'
const commit = '05b24cbbb0fe409c5e23c9791f0342f07524ffdc'
const repositoryUrl = 'https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge'

const baseJob = {
  id: jobId, repository_url: repositoryUrl, canonical_url: repositoryUrl,
  repository_key: 'the-pocket/pocketflow-tutorial-codebase-knowledge', commit_sha: commit,
  project_id: null, snapshot_id: null, cache_hit: false, skipped_count: 2,
  error_code: null, error_message: null, created_at: '2026-09-21T00:00:00Z', updated_at: '2026-09-21T00:00:00Z',
}

test('公开 GitHub URL 显示真实进度、固定 Commit 并进入同一快照地图', async ({ page }) => {
  let reads = 0
  const stages = [
    { status: 'running', stage: 'resolving', progress: 10 },
    { status: 'running', stage: 'downloading', progress: 35 },
    { status: 'running', stage: 'extracting', progress: 60 },
    { status: 'running', stage: 'saving', progress: 90 },
    { status: 'succeeded', stage: 'complete', progress: 100, project_id: projectId, snapshot_id: snapshotId },
  ]
  await page.route('**/api/github-imports', route => route.fulfill({ status: 202, json: { ...baseJob, status: 'queued', stage: 'queued', progress: 0 } }))
  await page.route(`**/api/github-imports/${jobId}`, route => route.fulfill({ json: { ...baseJob, ...stages[Math.min(reads++, stages.length - 1)] } }))
  await page.route(`**/api/projects/${projectId}`, route => route.fulfill({ json: {
    project: { id: projectId, name: 'PocketFlow-Tutorial-Codebase-Knowledge', source_type: 'github', source_label: repositoryUrl, created_at: '2026-09-21T00:00:00Z', updated_at: '2026-09-21T00:00:00Z' },
    snapshots: [{ id: snapshotId, project_id: projectId, revision: `git:${commit}`, commit_sha: commit, storage_path: `snapshots/${snapshotId}`, created_at: '2026-09-21T00:00:00Z',
      files: [{ path: 'main.py', size_bytes: 28, sha256: 'a'.repeat(64) }],
      folder_cards: [{ id: '44444444-4444-4444-8444-444444444444', snapshot_id: snapshotId, path: '.', title: '项目根目录', description: '真实远程源码。', claim_type: 'fact', inference: null, evidence_refs: [] }],
    }],
  } }))
  await page.route(`**/api/snapshots/${snapshotId}/source**`, route => route.fulfill({ json: { path: 'main.py', sha256: 'a'.repeat(64), line_start: 1, line_end: 2, total_lines: 2, content: 'def main():\n    return 42' } }))

  await page.goto('/')
  await page.getByLabel('GitHub 仓库地址').fill(repositoryUrl)
  await page.getByRole('button', { name: '读取公开仓库' }).click()
  await expect(page.getByRole('status')).toContainText('解析仓库与默认分支')
  await expect(page.getByRole('status')).toContainText('下载固定 Commit')
  await expect(page.getByRole('status')).toContainText(commit.slice(0, 12))
  await expect(page).toHaveURL(new RegExp(`#\/projects\/${projectId}$`))
  await expect(page.getByRole('heading', { name: 'PocketFlow-Tutorial-Codebase-Knowledge 项目地图' })).toBeVisible()
  await expect(page.getByText(commit, { exact: true })).toBeVisible()
  await expect(page.getByText(repositoryUrl, { exact: true })).toBeVisible()
  await expect(page.getByText('扫描与运行共用此快照', { exact: false })).toBeVisible()
})

test('GitHub 限流错误保持在首页且可以修改 URL 重试', async ({ page }) => {
  await page.route('**/api/github-imports', route => route.fulfill({ status: 202, json: { ...baseJob, status: 'queued', stage: 'queued', progress: 0 } }))
  await page.route(`**/api/github-imports/${jobId}`, route => route.fulfill({ json: { ...baseJob, status: 'failed', stage: 'error', progress: 100, error_code: 'github_rate_limited', error_message: 'GitHub API 已限流，请等待额度恢复或在本机配置 Token。' } }))
  await page.goto('/')
  await page.getByLabel('GitHub 仓库地址').fill(repositoryUrl)
  await page.getByRole('button', { name: '读取公开仓库' }).click()
  await expect(page.getByRole('alert')).toContainText('GitHub API 已限流')
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByLabel('GitHub 仓库地址')).toBeEnabled()
})
