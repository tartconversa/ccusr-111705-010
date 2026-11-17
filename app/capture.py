"""使用真实 Chromium 浏览公开目录；详情与预览另由业务采集流程处理。"""
from playwright.sync_api import sync_playwright
from urllib.parse import urlsplit

def read_catalog(origin):
    parts = urlsplit(origin)
    if parts.hostname not in ('127.0.0.1', 'localhost') or parts.scheme != 'http':
        raise ValueError('只允许本地演练来源')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(origin, wait_until='domcontentloaded')
            if not page.locator('main').count():
                raise ValueError('来源目录未加载')
            items = page.locator('.card').evaluate_all('(nodes) => nodes.map(n => ({id:n.dataset.key,name:n.querySelector("h2").textContent,summary:n.querySelector("p").textContent,href:n.querySelector("a").getAttribute("href")}))')
            return [{'source':page.url, **item} for item in items]
        finally:
            browser.close()
