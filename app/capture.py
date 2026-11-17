"""使用真实 Chromium 浏览公开目录；详情与预览另由业务采集流程处理。"""
from playwright.sync_api import sync_playwright
from urllib.parse import urlsplit
from .domain import interpret_card, interpret_entry

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
            return [{'source':page.url, **item, 'catalog_fact':interpret_card(item)} for item in items]
        finally:
            browser.close()

def read_detail_entry(origin, item_id, selection=None):
    parts = urlsplit(origin)
    if parts.hostname not in ('127.0.0.1', 'localhost') or parts.scheme != 'http':
        raise ValueError('local origins only')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(origin, wait_until='domcontentloaded')
            card = page.locator(f'.card[data-key="{item_id}"]')
            if card.count() != 1:
                raise ValueError('card identity is not unique')
            catalog = {'id': item_id, 'summary': card.locator('p').inner_text()}
            card.locator('a').click()
            if page.locator('main').get_attribute('data-key') != item_id:
                raise ValueError('detail identity differs from catalog')
            if selection is not None:
                page.locator('#category').select_option(selection)
            catalog_fact = interpret_card(catalog)
            entry_signal = {'category': page.locator('#category').input_value(), 'draft': page.locator('#draft-state').inner_text(), 'application': page.locator('main').get_attribute('data-key')}
            return {'id': item_id, 'source': page.url, 'catalog_fact': catalog_fact,
                    'opening_summary': page.locator('#summary').inner_text(),
                    'detail_fact': interpret_entry(catalog_fact, entry_signal)}
        finally:
            browser.close()
