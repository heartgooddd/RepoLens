import { expect, test as base } from '@playwright/test'
import type { Page, TestInfo } from '@playwright/test'

const test = base.extend({
  page: async ({ page }, use) => {
    const errors: string[] = []
    const externalRequests: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
    page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:5174')) externalRequests.push(request.url()) })
    await use(page)
    expect(errors, '浏览器控制台与运行时错误').toEqual([])
    expect(externalRequests, '不应发起站外请求（本地 API 使用同源代理）').toEqual([])
  },
})

async function openSample(page: Page) {
  await page.goto('/')
  await page.getByRole('link', { name: '进入 PocketFlow 示例工作台' }).click()
  await expect(page.getByRole('heading', { name: 'PocketFlow 项目地图' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '一张图看懂源码怎样变成教程' })).toBeVisible()
}

async function openRunPanel(page: Page) {
  const trigger = page.getByRole('button', { name: /试着生成项目导览/ })
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await trigger.click()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('heading', { name: '运行窗口', exact: true })).toBeVisible()
}

async function expectNoOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

async function capture(page: Page, testInfo: TestInfo, name: string) {
  // Capture the same scroll position so sticky navigation is not misplaced in full-page images.
  await page.evaluate(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
    document.querySelector('.run-panel')?.scrollTo({ top: 0, behavior: 'instant' })
  })
  await page.mouse.move(0, 0)
  await page.screenshot({ path: testInfo.outputPath(name), fullPage: true })
}

test('输入页、文件夹证据、空结果与导航', async ({ page }, testInfo) => {
  await page.goto('/')
  await expect(page.getByText('本地工作区 · 真实快照')).toBeVisible()
  await expect(page.getByLabel('GitHub 仓库地址')).toBeEnabled()
  await expect(page.getByRole('button', { name: '读取公开仓库' })).toBeDisabled()
  await expectNoOverflow(page)
  await capture(page, testInfo, 'home.png')
  await page.getByRole('link', { name: '进入 PocketFlow 示例工作台' }).click()
  await expect(page.getByRole('heading', { name: 'PocketFlow 项目地图' })).toBeVisible()
  await expect(page.getByRole('region', { name: '项目名称与简介' })).toContainText('Markdown 入门教程')
  await expect(page.getByRole('heading', { name: '一张图看懂源码怎样变成教程' })).toBeVisible()
  await expect(page.getByRole('region', { name: '源码片段' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '运行窗口', exact: true })).toHaveCount(0)
  await capture(page, testInfo, 'workspace.png')
  await page.getByRole('button', { name: '运行结果', exact: true }).click()
  await expect(page.getByRole('heading', { name: '还没有演示结果' })).toBeVisible()
  await capture(page, testInfo, 'empty.png')
  await page.getByRole('button', { name: 'main.py', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'main.py / 程序入口' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'main.py', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('region', { name: '源码片段' })).toHaveCount(0)
  await page.getByRole('button', { name: 'main.py 命令行参数与流程启动' }).click()
  await expect(page.getByRole('region', { name: '源码片段' })).toContainText('ArgumentParser')
  await expectNoOverflow(page)
  await expect(page.getByRole('link', { name: '在 GitHub 查看这个版本' })).toHaveAttribute('href', /05b24cbbb0fe409c5e23c9791f0342f07524ffdc\/main.py#L40/)
  await page.getByRole('button', { name: 'docs / 样书与设计' }).click()
  await expect(page.getByRole('heading', { name: 'docs / 样书与设计' })).toBeVisible()
  await expect(page.getByRole('region', { name: '源码片段' })).toHaveCount(0)
  await expectNoOverflow(page)
  await page.getByRole('link', { name: '返回输入页' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toContainText('先看懂它')
  await page.goBack()
  await expect(page.getByRole('heading', { name: 'PocketFlow 项目地图' })).toBeVisible()
})

test('成功演示保留参数快照并切换章节', async ({ page }, testInfo) => {
  await openSample(page)
  await page.getByRole('button', { name: 'flow.py', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'flow.py / 流程编排' })).toBeVisible()
  await openRunPanel(page)
  await page.getByLabel('输出语言').selectOption('en')
  await page.getByLabel('最大主题数').selectOption('5')
  await page.getByRole('button', { name: '开始演示运行' }).click()
  await expect(page.getByRole('status')).toHaveText('模拟处理中')
  await expect(page.getByLabel('输出语言')).toBeDisabled()
  await page.getByRole('button', { name: '运行结果', exact: true }).click()
  await expect(page.getByRole('heading', { name: '演示正在进行' })).toBeVisible()
  await capture(page, testInfo, 'processing.png')
  await expect(page.getByRole('status')).toHaveText('演示完成')
  await page.getByRole('button', { name: '查看演示结果' }).click()
  await expect(page.getByText('预置演示结果')).toBeVisible()
  await expect(page.getByRole('navigation', { name: '演示章节' }).getByRole('button')).toHaveCount(5)
  await page.getByRole('button', { name: '05 / Compare the design' }).click()
  await expect(page.getByRole('heading', { name: 'Compare the design' })).toBeVisible()
  await capture(page, testInfo, 'result.png')
  await page.getByLabel('输出语言').selectOption('zh')
  await page.getByLabel('最大主题数').selectOption('3')
  await expect(page.locator('.result-meta')).toContainText('English')
  await expect(page.locator('.result-meta')).toContainText('5 个')
  await expectNoOverflow(page)
  await page.getByRole('button', { name: '清空本次演示' }).click()
  await expect(page.getByRole('heading', { name: '还没有演示结果' })).toBeVisible()
  await page.getByRole('button', { name: '开始演示运行' }).click()
  await expect(page.getByRole('status')).toHaveText('演示完成')
  await expect(page.getByRole('navigation', { name: '演示章节' }).getByRole('button')).toHaveCount(3)
  await expect(page.getByRole('heading', { name: '从入口开始' })).toBeVisible()
})

test('失败情境、重试和停止不会留下过期结果', async ({ page }, testInfo) => {
  await openSample(page)
  await openRunPanel(page)
  await page.getByLabel('演示情境').selectOption('failure')
  await page.getByRole('button', { name: '开始演示运行' }).click()
  await expect(page.getByRole('status')).toHaveText('演示失败')
  await page.getByRole('button', { name: '运行结果', exact: true }).click()
  await expect(page.getByRole('heading', { name: '这次演示未完成' })).toBeVisible()
  await capture(page, testInfo, 'failure.png')
  await page.getByRole('button', { name: '重试成功演示' }).click()
  await expect(page.getByLabel('演示情境')).toHaveValue('success')
  await page.getByRole('button', { name: '停止演示' }).click()
  await expect(page.getByRole('status')).toHaveText('演示已停止')
  await page.waitForTimeout(1200)
  await expect(page.getByRole('status')).toHaveText('演示已停止')
  await expect(page.getByText('预置演示结果')).toHaveCount(0)
  await page.getByRole('button', { name: '重新演示' }).click()
  await expect(page.getByRole('status')).toHaveText('演示完成')
  await page.getByRole('link', { name: '返回输入页' }).click()
  await page.getByRole('link', { name: '进入 PocketFlow 示例工作台' }).click()
  await openRunPanel(page)
  await expect(page.getByRole('status')).toHaveText('尚未开始')
})

test('响应式导航和键盘入口', async ({ page }, testInfo) => {
  await page.goto('/#/workspace')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: '跳到主要内容' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('main')).toBeFocused()
  await expect(page.getByRole('heading', { name: 'PocketFlow 项目地图' })).toBeVisible()
  if (testInfo.project.name === 'narrow') {
    await page.getByRole('navigation', { name: '工作台区域导航' }).getByRole('button', { name: '运行窗口' }).click()
    await expect(page.getByRole('heading', { name: '运行窗口', exact: true })).toBeInViewport()
    await page.getByRole('navigation', { name: '工作台区域导航' }).getByRole('button', { name: '解释与结果' }).click()
    await expect(page.getByRole('button', { name: '位置与源码', exact: true })).toBeInViewport()
  }
  for (const width of [320, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await expectNoOverflow(page)
  }
})
