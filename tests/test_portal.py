import unittest
from playwright.sync_api import sync_playwright
from test_browser import BrowserBaselineTest
from app.site import DATA

class PortalInteractionTest(BrowserBaselineTest):
    def test_browser_business_interaction(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(self.origin + "detail?id=" + DATA["items"][0]["id"], wait_until="domcontentloaded")
                page.locator('#category').select_option('食饮');self.assertEqual(page.locator('#draft-state').inner_text(),'材料待核对');page.locator('#draft').click();self.assertEqual(page.locator('#draft-state').inner_text(),'草稿：食饮')
            finally:
                browser.close()
