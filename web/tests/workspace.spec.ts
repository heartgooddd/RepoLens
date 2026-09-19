import { expect, test as base } from '@playwright/test'
import type { Page } from '@playwright/test'

const test = base.extend({
  page: async ({ page }, use) => {
    const errors: string[] = []
    const externalRequests: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
    page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:5174')) externalRequests.push(request.url()) })
    await use(page)
    expect(errors, '浏览器控制台与运行时错误').toEqual([])
    expect(externalRequests, '演示期间不应发起外部请求').toEqual([])
  },
})

async function openSample(page: Page) {
  await page.goto('/')
  await page.getByRole('link', { name: '进入 PocketFlow 示例工作台' }).click()
  await expect(page.getByRole('heading', { name: 'PocketFlow 项目地图' })).toBeVisible()
}

async function expectNoOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

test('输入页、文件夹证据、空结果与导航', async ({ page }, testInfo) => {
  await page.goto('/')
  await expect(page.getByText('演示模式 · 不调用模型')).toBeVisible()
  await expect(page.getByLabel('GitHub 仓库地址')).toBeDisabled()
  await expectNoOverflow(page)
  await page.screenshot({ path: testInfo.outputPath('home.png'), fullPage: true })
  await page.getByRole('link', { name: '进入 PocketFlow 示例工作台' }).click()
  await expect(page.getByRole('heading', { name: 'PocketFlow 项目地图' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('workspace.png'), fullPage: true })
  await page.getByRole('button', { name: '运行结果', exact: true }).click()
  await expect(page.getByRole('heading', { name: '还没有演示结果' })).toBeVisible()
  await page.getByRole('button', { name: 'main.py', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'main.py / 程序入口' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'main.py', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'main.py 命令行参数与流程启动' }).click()
  await expect(page.getByRole('region', { name: '源码片段' })).toContainText('ArgumentParser')
  await expect(page.getByRole('link', { name: '在 GitHub 查看这个版本' })).toHaveAttribute('href', /05b24cbbb0fe409c5e23c9791f0342f07524ffdc\/main.py#L40/)
  await page.getByRole('button', { name: 'docs / 设计文档' }).click()
  await expect(page.getByRole('heading', { name: 'docs / 设计文档' })).toBeVisible()
  await expect(page.getByRole('region', { name: '源码片段' })).toHaveCount(0)
  await expectNoOverflow(page)
  await page.getByRole('link', { name: '返回输入页' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toContainText('先看懂它')
  await page.goBack()
  await expect(page.getByRole('heading', { name: 'PocketFlow 项目地图' })).toBeVisible()
})

test('成功演示保留参数快照并切换章节', async ({ page }, testInfo) => {
  await openSample(page)
  await page.getByLabel('输出语言').selectOption('en')
  await page.getByLabel('最大主题数').selectOption('5')
  await page.getByRole('button', { name: '开始演示运行' }).click()
  await expect(page.getByRole('status')).toHaveText('模拟处理中')
  await expect(page.getByLabel('输出语言')).toBeDisabled()
  await page.getByRole('button', { name: '运行结果', exact: true }).click()
  await expect(page.getByRole('heading', { name: '演示正在进行' })).toBeVisible()
  await expect(page.getByRole('status')).toHaveText('演示完成')
  await page.getByRole('button', { name: '查看演示结果' }).click()
  await expect(page.getByText('预置演示结果')).toBeVisible()
  await expect(page.getByRole('navigation', { name: '演示章节' }).getByRole('button')).toHaveCount(5)
  await page.getByRole('button', { name: '05 / Compare the design' }).click()
  await expect(page.getByRole('heading', { name: 'Compare the design' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('result.png'), fullPage: true })
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
  await page.getByLabel('演示情境').selectOption('failure')
  await page.getByRole('button', { name: '开始演示运行' }).click()
  await expect(page.getByRole('status')).toHaveText('演示失败')
  await page.getByRole('button', { name: '运行结果', exact: true }).click()
  await expect(page.getByRole('heading', { name: '这次演示未完成' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('failure.png'), fullPage: true })
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
    await expect(page.getByRole('button', { name: '文件夹说明', exact: true })).toBeInViewport()
  }
  for (const width of [320, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    await expectNoOverflow(page)
  }
})
